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

import json
import logging
import pytest
import requests

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.service_reader import LoadbalancerReader
from ..testlib.resource_validator import ResourceValidator
from ..conftest import get_relative_path
from ..conftest import Resource4TestTracker

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    # ./f5-openstack-agent/test/functional/neutronless/conftest.py
    relative = get_relative_path()
    snat_pool_json = str("{}/test/functional/testdata/"
                         "service_requests/snat_pool_common_networks.json")
    neutron_services_filename = (snat_pool_json.format(relative))
    return (json.load(open(neutron_services_filename)))


@pytest.fixture(scope="module")
def bigip():

    return BigIpClient(pytest.symbols.bigip_floating_ips[0],
                       pytest.symbols.bigip_username,
                       pytest.symbols.bigip_password)


@pytest.fixture
def fake_plugin_rpc(services):

    rpcObj = FakeRPCPlugin(
        [services['loadbalancer'], services['listener'], services['pool'],
         services['member'], services['delete_member'],
         services['delete_listener'], services['delete_loadbalancer'],
         services['cleanup0'], services['cleanup1']
         ])  # expected is list

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


def test_tenant(track_bigip_cfg, bigip, services, icd_config,
                 icontrol_driver):
    """Test creating and deleting SNAT pools with common network listener.

    The test procedure is testing that the needed items as follows:
        - Test non-Common (tenant)
            - Pools
            - Pool Member
            - Virtual Address
            - Virtual Services
    """
    env_prefix = icd_config['environment_prefix']
    validator = ResourceValidator(bigip, env_prefix)

    # enable our config to be common_networks:
    icontrol_driver.conf.f5_common_networks = True

    expected_chain = ['loadbalancer', 'listener', 'pool', 'member']
    with Resource4TestTracker(services, icontrol_driver, expected_chain) as \
            bigip_handler:
        bigip_handler.deploy_next()
        lb_reader = LoadbalancerReader(bigip_handler.state)
        folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
        assert bigip.folder_exists(folder)

        # validate SNAT pool created in tenant partition with one member for LB
        snat_pool_name = folder
        snat_pool_folder = folder
        lb_snat_name = '/Common/snat-traffic-group-local-only-{0}_0'
        # we expect to a member as a snat-traffic-group-local-only for each sub
        expected_members = map(lambda x: (lb_snat_name.format(x)),
                               bigip_handler.state['subnets'].keys())
        validator.assert_snatpool_valid(
            snat_pool_name, snat_pool_folder, expected_members)

        # create listener
        bigip_handler.deploy_next()
        listener = bigip_handler.state['listeners'][0]
        validator.assert_virtual_valid(listener, folder)

        # create pool
        bigip_handler.deploy_next()
        pool = bigip_handler.state['pools'][0]
        validator.assert_pool_valid(pool, folder)

        # create member
        bigip_handler.deploy_next()

        # Test member:
        member = bigip_handler.state['members'][0]
        validator.assert_member_valid(pool, member, folder)
        expected_members = map(lambda x: (lb_snat_name.format(x)),
                               bigip_handler.state['subnets'].keys())
        validator.assert_snatpool_valid(snat_pool_name, snat_pool_folder,
                                        expected_members)

        # delete pool
        bigip_handler.destroy_previous()
        bigip_handler.destroy_previous()
        validator.assert_pool_deleted(pool, None, folder)

        # delete listener
        bigip_handler.destroy_previous()
        validator.assert_virtual_deleted(listener, folder)

        # delete loadbalancer - good samaritan...
        bigip_handler.cleanup()

        # validate everything (including SNAT ppols) removed
        assert not bigip.folder_exists(folder)


@pytest.mark.skip(reason=str("Route domain and snatpool Common handling "
                             "not done yet"))
def test_common_owned_objs(track_bigip_cfg, bigip, services, icd_config,
                           icontrol_driver):
    """Tests that route domain and snatpool objects are in Common

    This test simply validates whether or not the snatpool and route domain are
    present in the common partition rather than only in the tenant.
    """
    # enable our config to be common_networks:
    icontrol_driver.conf.f5_common_networks = True
    env_prefix = icd_config['environment_prefix']
    validator = ResourceValidator(bigip, env_prefix)

    expected_chain = ['loadbalancer', 'listener', 'pool', 'member']
    with Resource4TestTracker(services, icontrol_driver, expected_chain) as \
            bigip_handler:
        bigip_handler.deploy_next()
        folder = 'Common'

        # Once the route domain change to common has been implemented, this
        # naming schema may change:
        lb_reader = LoadbalancerReader(bigip_handler.state)
        rd_name = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
        assert bigip.resource_exists(ResourceType.route_domain, folder)
        rd = bigip.get_resource(ResourceType.route_domain, rd_name,
                                partition=folder)

        assert rd, "Route domain on /{} was not created!".format(folder)
        # no need to be the good samaritan... let the object clean things up...

    # assert that we're clean...
    assert not bigip.folder_exists(folder)
