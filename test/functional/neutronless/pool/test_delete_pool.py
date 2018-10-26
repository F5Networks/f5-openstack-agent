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
                     '../../testdata/service_requests/delete_pool.json')
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


def test_single_pool(track_bigip_cfg, bigip, services, icd_config,
                     icontrol_driver):
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)
    validator = ResourceValidator(bigip, env_prefix)

    # create loadbalancer on lb_subnet (membes will be on different subnet)
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

    # create member on member_subnet (different subnet than LB)
    service = service_iter.next()
    member = service['members'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_member_valid(pool, member, folder)

    # create second member on member_subnet
    service = service_iter.next()
    member = service['members'][1]
    icontrol_driver._common_service_handler(service)
    validator.assert_member_valid(pool, member, folder)

    # delete pool without first deleting members
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_deleted(pool, member, folder)

    # delete listener
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_deleted(listener, folder)

    # delete loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)

    # if folder still exists, agent failed to fully clean up network objects
    assert not bigip.folder_exists(folder)
