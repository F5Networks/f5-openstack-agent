# coding=utf-8
# Copyright (c) 2017,2018, F5 Networks, Inc.
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

from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.service_reader import LoadbalancerReader
from ..testlib.resource_validator import ResourceValidator
from ..conftest import get_relative_path

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    # ./f5-openstack-agent/test/functional/neutronless/conftest.py
    relative = get_relative_path()
    snat_pool_json = str("{}/test/functional/testdata/"
                         "service_requests/snat_pool.json".format(relative))
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     snat_pool_json)
    )
    return (json.load(open(neutron_services_filename)))


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


def test_snat_common_network(track_bigip_cfg, bigip, services, icd_config,
                             icontrol_driver):
    """Test creating and deleting SNAT pools with common network listener.

    The test procedure is:
        - Assume a shared (common) network
        - Assume a separate non-shared tenant network
        - Create load balancer/listener on shared network
        - Expect that a SNAT pool is created in the tenant partition with a
          /Common member for LB subnet
        - Add pool and member, with member on separate tenant network.
        - Expect that the same SNAT pool now has an additional SNAT member for
          the pool member, referenced to member subnet.
        - Delete member and expect that SNAT pool only has member for original
          LB
        - Delete everything else and expect all network objects and tenant
          folder are deleted.
    """
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)
    validator = ResourceValidator(bigip, env_prefix)

    # create loadbalancer
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)

    # validate SNAT pool created in tenant partition with one member for LB
    expected_members = []
    snat_pool_name = folder
    snat_pool_folder = folder
    subnet_id = service['loadbalancer']['vip_subnet_id']
    lb_snat_name = '/Common/snat-traffic-group-local-only-{0}_0'.\
        format(subnet_id)
    expected_members.append(lb_snat_name)
    validator.assert_snatpool_valid(
        snat_pool_name, snat_pool_folder, expected_members)

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

    # create member
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # validate that SNAT pool now has two SNAT members, one for LB and one for
    # the pool member
    member = service['members'][0]
    member_subnet_id = member['subnet_id']
    member_snat_name = '/{0}/snat-traffic-group-local-only-{1}_0'.\
        format(folder, member_subnet_id)
    expected_members.append(member_snat_name)
    validator.assert_snatpool_valid(
        snat_pool_name, snat_pool_folder, expected_members)

    # delete member
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # validate that SNAT pool now only has one member for LB
    expected_members.pop()
    validator.assert_snatpool_valid(
        snat_pool_name, snat_pool_folder, expected_members)

    # delete pool
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_deleted(pool, None, folder)

    # delete listener
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_deleted(listener, folder)

    # delete loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)

    # validate everything (including SNAT ppols) removed
    assert not bigip.folder_exists(folder)

    # cleanup...
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
