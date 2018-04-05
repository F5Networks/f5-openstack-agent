# Copyright (c) 2016-2018, F5 Networks, Inc.
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

# from f5.utils.testutils.registrytools import order_by_weights
# from f5.utils.testutils.registrytools import register_device
# from icontrol.exceptions import iControlUnexpectedHTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver


AGENT_LB_DEL_ORDER = {'/mgmt/tm/ltm/virtual/': 1,
                      '/mgmt/tm/ltm/pool': 2,
                      'mgmt/tm/ltm/node/': 3,
                      'monitor': 4,
                      'virtual-address': 5,
                      'mgmt/tm/net/self/': 6,
                      '/mgmt/tm/net/fdb': 7,
                      'mgmt/tm/net/tunnels/tunnel/': 8,
                      'mgmt/tm/net/tunnels/vxlan/': 9,
                      'mgmt/tm/net/tunnels/gre': 10,
                      'mgmt/tm/net/vlan': 11,
                      'route': 12,
                      '/mgmt/tm/ltm/snatpool': 13,
                      '/mgmt/tm/ltm/snat-translation': 14,
                      '/mgmt/tm/net/route-domain': 15,
                      '/mgmt/tm/sys/folder': 16}


@pytest.fixture(scope='module')
def makelogdir(request):
    logtime = '%0.0f' % time.time()
    dirname = os.path.dirname(request.module.__file__)
    modfname = request.module.__name__
    logdirname = os.path.join(dirname, 'logs', modfname, logtime)
    os.makedirs(logdirname)
    return logdirname


def _get_nolevel_handler(logname):
    rootlogger = logging.getLogger()
    for h in rootlogger.handlers:
        rootlogger.removeHandler(h)
    rootlogger.setLevel(logging.INFO)
    fh = logging.FileHandler(logname)
    fh.setLevel(logging.INFO)
    rootlogger.addHandler(fh)
    return fh


def remove_elements(bigip):
    """Do this in a way that we do not need to rely on others' code...

    We wish to remove all objects off of the bigip.
    """
    ignore_names = [u'/', u'Common', u'Drafts', u'http-tunnel',
                    u'socks-tunnel', u'selfip.internal', u'selfip.external',
                    u'selfip.tunnel', u'selfip.ha', u'vxlan', u'vxlan-gpe',
                    u'vxlan-ovsdb', u'gre', u'nvgre', u'0', u'']

    def remove_all_fdbs():
        for t in bigip.tm.net.fdb.tunnels.get_collection():
            if t.name not in ignore_names:
                t.modify(records=[])

    def remove_all_of_type(bigip_obj_type):
        items = bigip_obj_type.get_collection()
        for item in items:
            my_name = item.name.replace('/', '')
            if my_name not in ignore_names:
                item.delete()

    before_tunnels = [
        bigip.tm.ltm.virtuals,
        bigip.tm.ltm.virtual_address_s,
        bigip.tm.ltm.snatpools,
        bigip.tm.net.selfips,
        bigip.tm.net.arps]
    after_tunnels = [
        bigip.tm.net.tunnels.tunnels,
        bigip.tm.net.tunnels.vxlans,
        bigip.tm.net.tunnels.gres,
        bigip.tm.net.route_domains,
        bigip.tm.sys.folders]
    for obj_type in before_tunnels:
        remove_all_of_type(obj_type)
    remove_all_fdbs()
    for obj_type in after_tunnels:
        remove_all_of_type(obj_type)


def setup_neutronless_test(request, bigip, makelogdir, vlan=False):
    # pretest_snapshot = frozenset(register_device(bigip))

    logname = os.path.join(makelogdir, request.function.__name__)
    loghandler = _get_nolevel_handler(logname)
    remove_elements(bigip)

    def remove_test_created_elements():
        # posttest_registry = register_device(bigip)
        # created = frozenset(posttest_registry) - pretest_snapshot
        remove_elements(bigip)
        rootlogger = logging.getLogger()
        rootlogger.removeHandler(loghandler)

    request.addfinalizer(remove_test_created_elements)
    return loghandler


@pytest.fixture
def configure_icd():
    class ConfFake(object):
        '''minimal fake config object to replace oslo with controlled params'''
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    def _icd(icd_config):
        mock_rpc_plugin = mock.MagicMock()
        mock_rpc_plugin.get_port_by_name.return_value =\
            [{'fixed_ips': [{'ip_address': '10.2.2.134'}]}]
        icontroldriver = iControlDriver(ConfFake(icd_config),
                                        registerOpts=False)
        icontroldriver.plugin_rpc = mock_rpc_plugin
        return icontroldriver
    return _icd
