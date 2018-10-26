# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import \
    SystemHelper

import json
import logging
import os
import pytest
import requests

from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.service_reader import LoadbalancerReader
from ..testlib.resource_validator import ResourceValidator

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/test_purge_folder.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture(scope="module")
def bigip():

    return BigIpClient(pytest.symbols.bigip_floating_ips[0],
                       pytest.symbols.bigip_username,
                       pytest.symbols.bigip_password)


@pytest.fixture
def fake_plugin_rpc(services):

    rpcObj = FakeRPCPlugin(services)

    return rpcObj


@pytest.fixture
def icontrol_driver(icd_config, fake_plugin_rpc):
    class ConfFake(object):
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    icd = iControlDriver(ConfFake(icd_config),
                         registerOpts=False)

    icd.plugin_rpc = fake_plugin_rpc
    icd.connect()

    return icd


def test_purge_folder(track_bigip_cfg, bigip, services, icd_config,
                     icontrol_driver):
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)
    validator = ResourceValidator(bigip, env_prefix)

    # create loadbalancer
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)

    # create listener
    service = service_iter.next()
    listener = service['listeners'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_valid(listener, folder)

    # create pool
    service = service_iter.next()
    pool = service['pools'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool, folder)

    # create l7policy with l7rule attached to the above created
    # listener
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_policy_valid(listener, folder)

    sh = SystemHelper()
    sh.purge_folder_contents(bigip.bigip, folder)

    # delete folder and check that it does not exist
    sh.purge_folder(bigip.bigip, folder)
    assert not bigip.folder_exists(folder)

