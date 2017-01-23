# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import mock
import os
import pytest
import time

from f5.bigip import ManagementRoot
from f5.utils.testutils.registrytools import register_device
from f5.utils.testutils.registrytools import AGENT_LB_DEL_ORDER
from f5.utils.testutils.registrytools import order_by_weights
from icontrol.exceptions import iControlUnexpectedHTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver


@pytest.fixture
def bigip(request):
    bigip = ManagementRoot(pytest.symbols.bigip_ip,
                            pytest.symbols.bigip_username,
                            pytest.symbols.bigip_password)
    return bigip

@pytest.fixture
def bigip2(request):
    bigip2 = ManagementRoot(pytest.symbols.bigip2_ip,
                            pytest.symbols.bigip_username,
                            pytest.symbols.bigip_password)
    return bigip2

@pytest.fixture
def vcmp_uris(request):
    bigver = pytest.symbols.bigip_version
    uri_dict = {
        "vcmp_lb_uris":
            ["https://localhost/mgmt/tm/sys/folder/~TEST_"
             "128a63ef33bc4cf891d684fad58e7f2d?ver={}".format(bigver),
             "https://localhost/mgmt/tm/net/route-domain/~TEST_128a63ef33bc4c"
             "f891d684fad58e7f2d~TEST_128a63ef33bc4cf8"
             "91d684fad58e7f2d?ver={}".format(bigver),
             "https://localhost/mgmt/tm/net/fdb/tunnel/~TEST_128a63ef33bc4cf89"
             "1d684fad58e7f2d~disconnected_network?ver=11.5.0",
             "https://localhost/mgmt/tm/net/tunnels/tunnel/~TEST_128a63ef33bc4"
             "cf891d684fad58e7f2d~disconnected_network?ver={}".format(bigver),
             "https://localhost/mgmt/tm/net/vlan/~TEST_128a63ef33bc4cf891d684f"
             "ad58e7f2d~vlan-46?ver={}".format(bigver),
             "https://localhost/mgmt/tm/ltm/snat-translation/~TEST_128a63ef33b"
             "c4cf891d684fad58e7f2d~snat-traffic-group-local-only-ce69e293-56e"
             "7-43b8-b51c-01b91d66af20_0?ver={}".format(bigver),
             "https://localhost/mgmt/tm/ltm/snatpool/~TEST_128a63ef33bc4cf891d"
             "684fad58e7f2d~TEST_128a63ef33bc4cf891d684fad58e7f2d?"
             "ver={}".format(bigver),
             "https://localhost/mgmt/tm/net/self/~TEST_128a63ef33bc4cf891d684f"
             "ad58e7f2d~local-localhost.localdomain-ce69e293-56e7-43b8-b51c-01"
             "b91d66af20?ver={}".format(bigver),
             "https://localhost/mgmt/tm/ltm/virtual-address/~TEST_128a63ef33bc"
             "4cf891d684fad58e7f2d~TEST_50c5d54a-5a9e-4a80-9e74-8400a461a077?"
             "ver={}".format(bigver)
             ],
        "vcmp_listener_uris":
            ["https://localhost/mgmt/tm/ltm/virtual/~TEST_128a63ef33bc4cf891d6"
             "84fad58e7f2d~TEST_105a227a-cdbf-4ce3-844c-9ebedec849e9?"
             "ver={}".format(bigver)],
        "vcmp_cluster_uris":
        [
            "https://localhost/mgmt/tm/ltm/snat-translation/~TEST_128a63ef33bc"
            "4cf891d684fad58e7f2d~snat-traffic-group-1-ce69e293-56e7-43b8-b51c"
            "-01b91d66af20_0?ver={}".format(bigver),
            "https://localhost/mgmt/tm/ltm/snatpool/~TEST_128a63ef33bc4cf891d6"
            "84fad58e7f2d~TEST_128a63ef33bc4cf891d684fad58e7f2d?"
            "ver={}".format(bigver),
            "https://localhost/mgmt/tm/net/self/~TEST_128a63ef33bc4cf891d684fa"
            "d58e7f2d~local-localhost.localdomain-ce69e293-56e7-43b8-b51c-01b9"
            "1d66af20?ver={}".format(bigver),
            "https://localhost/mgmt/tm/net/self/~TEST_128a63ef33bc4cf891d684fa"
            "d58e7f2d~local-localhost.localdomain-ce69e293-56e7-43b8-b51c-01b9"
            "1d66af20?ver={}".format(bigver)]
    }
    return uri_dict


@pytest.fixture
def setup_bigip_devices(request, bigip, bigip2, vcmp_uris, makelogdir):
    lb_uris = set(vcmp_uris['vcmp_lb_uris'])
    listener_uris = set(vcmp_uris['vcmp_listener_uris'])
    cluster_uris = set(vcmp_uris['vcmp_cluster_uris'])

    class test_bigip(object):
        def __init__(self, device, pretest_snapshot):
            self.device = device
            self.pretest_snapshot = frozenset(pretest_snapshot)

    bigips = [test_bigip(bigip, register_device(bigip)),
              test_bigip(bigip2, register_device(bigip2))]
    logname = os.path.join(makelogdir, request.function.__name__)
    loghandler = _get_nolevel_handler(logname)

    def remove_test_created_elements():
        for bigip in bigips:
            posttest_registry = register_device(bigip.device)
            created = frozenset(posttest_registry) - bigip.pretest_snapshot
            remove_elements(bigip.device, created, vlan=True)

    rootlogger = logging.getLogger()
    rootlogger.removeHandler(loghandler)
    for bigip in bigips:
        try:
            remove_elements(
                bigip.device, lb_uris | listener_uris | cluster_uris,
                vlan=True)
        finally:
            rootlogger.info('removing pre-existing config on bigip {}'.format(
                bigip.device.hostname))
    request.addfinalizer(remove_test_created_elements)
    return loghandler
