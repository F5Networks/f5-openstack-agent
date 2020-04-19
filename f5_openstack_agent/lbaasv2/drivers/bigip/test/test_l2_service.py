#!/usr/bin/env python
# coding=utf-8
# Copyright (c) 2017,2018, F5 Networks, Inc.
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

import mock
import pytest

from mock import Mock
from mock import patch

from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    _get_tunnel_name
from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    L2ServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper


@pytest.fixture
def bigips():
    return [mock.MagicMock()]


@pytest.fixture
def l2_service():
    driver = mock.MagicMock()
    driver.conf = mock.MagicMock()
    driver.conf.vlan_binding_driver = None
    return L2ServiceBuilder(driver, False)


@pytest.fixture
def service():
    return {
        u"listeners": [{
            u"admin_state_up": True,
            u"connection_limit": -1,
            u"default_pool_id": None,
            u"default_tls_container_id": None,
            u"description": u"",
            u"id": u"5108c2fe-29bd-4e5b-94de-99034c561a15",
            u"l7_policies": [],
            u"loadbalancer_id": u"75e9326d-67ec-42b7-9647-3fc1c51c0091",
            u"name": u"listener2",
            u"operating_status": u"ONLINE",
            u"protocol": u"HTTPS",
            u"protocol_port": 443,
            u"provisioning_status": u"ACTIVE",
            u"sni_containers": [],
            u"tenant_id": u"980e3f914f3e40359c3c2d9470fb2e8a"
        }],
        u'loadbalancer': {
            u'admin_state_up': True,
            u'description': u'',
            u'gre_vteps': [u'201.0.162.1',
                           u'201.0.160.1',
                           u'201.0.165.1'],
            u'id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
            u'listeners': [
                {u'id': u'e3af03f4-d3df-4c9b-b3dd-8002f133d5bf'}],
            u'name': u'',
            u'network_id': u'cdf1eb6d-9b17-424a-a054-778f3d3a5490',
            u'operating_status': u'ONLINE',
            u'pools': [
                {u'id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52'}],
            u'provider': u'f5networks',
            u'provisioning_status': u'ACTIVE',
            u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd',
            u'vip_address': u'172.16.101.3',
            u'vip_port': {u'admin_state_up': True,
                          u'allowed_address_pairs': [],
                          u'binding:host_id':
                              u'host-164.int.lineratesystems.com:16ea1e',
                          u'binding:profile': {},
                          u'binding:vif_details': {},
                          u'binding:vif_type': u'binding_failed',
                          u'binding:vnic_type': u'normal',
                          u'created_at': u'2016-10-24T21:17:30',
                          u'description': None,
                          u'device_id': u'0bd0b8ff-1c51-5061-b0c4',
                          u'device_owner': u'F5:lbaasv2',
                          u'dns_name': None,
                          u'extra_dhcp_opts': [],
                          u'fixed_ips': [
                              {u'ip_address': u'172.16.101.3',
                               u'subnet_id': u'81f42a8a-fc98-4281-8de4'}],
                          u'id': u'38a13e5c-6863-4537-80a3',
                          u'mac_address': u'fa:16:3e:94:65:0c',
                          u'name': u'loadbalancer-d5a0396e-e862',
                          u'network_id': u'cdf1eb6d-9b17-424a',
                          u'security_groups': [u'df88afdb-2bc6-4621'],
                          u'status': u'DOWN',
                          u'tenant_id': u'd9ed216f67f04a84bf8fd',
                          u'updated_at': u'2016-10-24T21:17:31'},
            u'vip_port_id': u'38a13e5c-6863-4537-80a3-c788d5f0c9ce',
            u'vip_subnet_id': u'81f42a8a-fc98-4281-8de4-2b946e931457',
            u'vxlan_vteps':
                ['192.168.130.136', '192.168.130.20', '192.168.130.131',
                 '192.168.130.8', '192.168.130.7', '192.168.130.46',
                 '192.168.130.48', '192.168.130.12', '192.168.130.47',
                 '192.168.130.106', '192.168.130.115', '192.168.130.99',
                 '192.168.130.116', '192.168.130.44', '192.168.130.118',
                 '192.168.130.109', '192.168.130.28', '192.168.130.40',
                 '192.168.130.127', '192.168.130.100', '192.168.130.41',
                 '192.168.130.105', '192.168.130.124', '192.168.130.138',
                 '192.168.130.111', '192.168.130.31', '192.168.130.137',
                 '192.168.130.22', '192.168.130.135', '192.168.130.62',
                 '192.168.130.45', '192.168.130.140', '192.168.130.113',
                 '192.168.130.84', '192.168.130.121', '192.168.130.88',
                 '192.168.130.42', '192.168.130.39', '192.168.130.114',
                 '192.168.130.57', '192.168.130.38', '192.168.130.101',
                 '192.168.130.110', '192.168.130.126']},
        u'members': [{u'address': u'10.2.2.3',
                      u'admin_state_up': True,
                      u'id': u'1e7bfa17-a38f-4728-a3a7-aad85da69712',
                      u'name': u'',
                      u'network_id': u'cdf1eb6d-9b17-424a-a054-778f3d3a5490',
                      u'operating_status': u'ONLINE',
                      u'pool_id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
                      u'protocol_port': 8080,
                      u'provisioning_status': u'ACTIVE',
                      u'subnet_id': u'81f42a8a-fc98-4281-8de4-2b946e931457',
                      u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd',
                      u'port': {'mac_address': 'fa:16:3e:0d:fa:c8'},
                      u'vxlan_vteps': ['192.168.130.59'],
                      u'weight': 1},
                     {u'address': u'10.2.2.4',
                      u'admin_state_up': True,
                      u'id': u'1e7bfa17-a38f-4728-a3a7-aad85da69714',
                      u'name': u'',
                      u'network_id': u'cdf1eb6d-9b17-424a-a054-778f3d3a5490',
                      u'operating_status': u'ONLINE',
                      u'pool_id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
                      u'protocol_port': 8080,
                      u'provisioning_status': u'ACTIVE',
                      u'subnet_id': u'81f42a8a-fc98-4281-8de4-2b946e931457',
                      u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd',
                      u'port':  {'mac_address': 'fa:16:3e:0d:fa:c6'},
                      u'vxlan_vteps': ['192.168.130.60'],
                      u'weight': 1}],
        u'networks': {
            u'cdf1eb6d-9b17-424a-a054-778f3d3a5490': {
                'status': 'ACTIVE',
                'subnets': ['82b3db18-e97d-4288-81ab-12b04758f595'],
                'name': 'lifecycle', 'provider:physical_network': None,
                'admin_state_up': True,
                'tenant_id': 'd1cae4d1238243419b3894ecea85c4aa', 'mtu': 1500,
                'router:external': False, 'vlan_transparent': None,
                'shared': False, 'provider:network_type': 'vxlan',
                'id': 'b2efb43c-60a7-4032-be03-b3ccb2990c03',
                'provider:segmentation_id': 5218
            }
        },
        u'pools': [{u'admin_state_up': True,
                    u'description': u'',
                    u'healthmonitor_id': u'70fed03a-efc4-460a-8a21',
                    u'id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
                    u'l7_policies': [],
                    u'lb_algorithm': u'ROUND_ROBIN',
                    u'listeners':[
                        {u'id': '5108c2fe-29bd-4e5b-94de-99034c561a15'}],
                    u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d59',
                    u'name': u'',
                    u'operating_status': u'ONLINE',
                    u'partition': 'Test_d9ed216f67f04a84bf8fd97c155855cd',
                    u'protocol': u'HTTP',
                    u'provisioning_status': u'ACTIVE',
                    u'session_persistence': None,
                    u'sessionpersistence': None,
                    u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd'}],
    }


class Test_L2ServiceBuilder(object):
    """Performs tests against L2ServiceBuilder

    The beginning variable assignments should reflect the items that should be
    rotated back to their original values in code-space in the teardown()
    method.  All items that are manipulated to mocks initially should be
    performed in a fixture method when repeated.
    """

    @pytest.fixture(autouse=True)
    def create_self(self, request):
        """Creates a 'blank' L2ServiceBuilder instance in self

        This method is executed for every test method during runtime.
        """
        request.addfinalizer(self.teardown)

        # create our fake driver object...
        self.driver = Mock()
        self.driver.conf = Mock()
        force_false = ['vlan_binding_driver']
        list_vars = ['f5_external_physical_mappings']
        for item in force_false:
            setattr(self.driver.conf, item, False)
        for item in list_vars:
            setattr(self.driver.conf, item, list())

        # set our mocks...
        self.system_helper = Mock()
        self.network_helper = Mock()
        self.service_model_adopter = Mock()
        self.f5_global_routed_mode = Mock()
        args = [self.driver, self.f5_global_routed_mode]

        NetworkHelper = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l2_service.'
                'NetworkHelper')
        ServiceModelAdapter = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l2_service.'
                'ServiceModelAdapter')
        SystemHelper = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l2_service.'
                'SystemHelper')
        with patch(SystemHelper, self.system_helper, create=True):
            with patch(ServiceModelAdapter, self.service_model_adopter,
                       create=True):
                with patch(NetworkHelper, self.network_helper, create=True):
                    self.l2_service_builder = L2ServiceBuilder(*args)

    def test__init__(self):
        """tests the target's __init__ method"""
        # tests based on basic object creation from self.create_self():
        assert self.l2_service_builder.driver is self.driver, \
            "Driver provisioning test"
        assert self.l2_service_builder.conf is self.driver.conf, \
            "Dirver conf provisioning test"
        assert self.l2_service_builder.f5_global_routed_mode is \
            self.f5_global_routed_mode, \
            "f5_global_routed_mode provisioning test"
        self.system_helper.assert_called_once_with()
        self.network_helper.assert_called_once_with()
        self.service_model_adopter.assert_called_once_with(self.driver.conf)

        # further tests needed:
        # add tests for...
        #   - f5_external_physical_mappings assignment test
        #   - vlan_binding_driver assignment/importation test
        # Suggest a refactor for implementing the above in unit tests...

    def teardown(self):
        """Tears down the code space variables returning code state."""
        pass

    def test_is_common_network(self):
        """Tests the target's is_common_network() method"""
        target = self.l2_service_builder
        network = {"shared": True, "id": "foodogzoo", "router:external": True,
                   }
        setattr(target.conf, "f5_common_external_networks", True)
        setattr(target.conf, "common_network_ids", ['foodogzoo'])
        setattr(target.conf, "f5_common_networks", True)
        # network['shared'] condition
        assert target.is_common_network(network), "shared test"
        # self.conf.f5_common_networks condition
        network['shared'] = False
        assert target.is_common_network(network), "f5_common_networks test"
        # self.conf.f5_common_external_networks condition
        setattr(target.conf, "f5_common_networks", False)
        assert target.is_common_network(network), \
            "f5_common_external_networks test"
        setattr(target.conf, "f5_common_external_networks", False)
        target.conf.common_network_ids.pop()
        assert not target.is_common_network(network), \
            "f5_common_external_networks negative test"
        setattr(target.conf, "f5_common_external_networks", True)
        assert target.is_common_network(network), \
            "f5_common_network_ids negative test"
        target.conf.f5_common_network_ids.push('foodogzoo')
        network['router:external'] = False
        assert not target.is_common_network(network), \
            "network['reouter:external'] negative test"
        del network['router:external']
        assert not target.is_common_network(network), \
            "No 'reouter:external' network 'negative' test"

    def test_create_fdb_records(self, l2_service, service):
        loadbalancer = service['loadbalancer']
        network_id = loadbalancer['network_id']
        loadbalancer['network'] = service['networks'][network_id]
        members = list()
        for member in service['members']:
            network_id = member['network_id']
            member['network'] = service['networks'][network_id]
            members.append(member)

        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)

        # two networks, two sets of records
        assert len(tunnel_records) == 1

        # vxlan records has lb and two members
        tunnel_name = _get_tunnel_name(members[0]['network'])
        assert tunnel_name == 'tunnel-vxlan-5218'
        vxlan_records = tunnel_records[tunnel_name]['records']
        assert len(vxlan_records) == (len(loadbalancer.get('vxlan_vteps')) + 2)

    def test_empty_fdb_records(self, l2_service):
        loadbalancer = None
        members = list()
        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)

        # no records should be created
        assert len(tunnel_records) == 0

    def test_no_member_records(self, l2_service, service):
        loadbalancer = service['loadbalancer']
        network_id = loadbalancer['network_id']
        loadbalancer['network'] = service['networks'][network_id]

        members = list()
        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)

        # one network, one set of records
        assert len(tunnel_records) == 1

        tunnel_name = _get_tunnel_name(loadbalancer['network'])
        assert tunnel_name == 'tunnel-vxlan-5218'
        vxlan_records = tunnel_records[tunnel_name]['records']
        assert len(vxlan_records) == len(loadbalancer.get('vxlan_vteps'))

    def test_no_loadbalancer_records(self, l2_service, service):
        loadbalancer = None
        members = list()
        for member in service['members']:
            network_id = member['network_id']
            member['network'] = service['networks'][network_id]
            members.append(member)

        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)

        # two networks, two sets of records
        assert len(tunnel_records) == 1

        # vxlan records has both members
        tunnel_name = _get_tunnel_name(members[0]['network'])
        assert tunnel_name == 'tunnel-vxlan-5218'
        vxlan_records = tunnel_records[tunnel_name]['records']
        assert len(vxlan_records) == 2

    def test_add_fdb_entries(self, l2_service, service, bigips):
        loadbalancer = service['loadbalancer']
        network_id = loadbalancer['network_id']
        loadbalancer['network'] = service['networks'][network_id]
        members = list()
        for member in service['members']:
            network_id = member['network_id']
            member['network'] = service['networks'][network_id]
            members.append(member)

        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'network_helper.NetworkHelper') as mock_helper:

            l2_service.network_helper = mock_helper
            l2_service.add_fdb_entries(bigips, loadbalancer, members)
            assert l2_service.network_helper.add_fdb_entries.called

    def test_delete_fdb_entries(self, l2_service, service, bigips):
        loadbalancer = service['loadbalancer']
        network_id = loadbalancer['network_id']
        loadbalancer['network'] = service['networks'][network_id]
        members = list()
        for member in service['members']:
            network_id = member['network_id']
            member['network'] = service['networks'][network_id]
            members.append(member)

        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'network_helper.NetworkHelper') as mock_helper:
            l2_service.network_helper = mock_helper
            l2_service.delete_fdb_entries(bigips, loadbalancer, members)
            assert l2_service.network_helper.delete_fdb_entries.called

    def test_network_helper_add_fdb_entries(self, l2_service, service, bigips):
        # add first member fdb entry
        loadbalancer = None
        members = list()
        member = service['members'][0]
        network_id = member['network_id']
        member['network'] = service['networks'][network_id]
        members.append(member)

        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)

        network_helper = NetworkHelper()
        tunnel = mock.MagicMock()
        tunnel.records_s.records.exists = mock.MagicMock(return_value=False)

        bigip = bigips[0]
        bigip.tm.net.fdb.tunnels.tunnel.load = mock.MagicMock(
            return_value=tunnel)
        network_helper.add_fdb_entries(bigip, fdb_entries=tunnel_records)

        # expect to modify with first member's VTEP and MAC addr
        tunnel.records_s.records.create.assert_called_with(
            name='fa:16:3e:0d:fa:c8', endpoint='192.168.130.59')

        # add second member fdb entry
        members = list()
        member = service['members'][1]
        network_id = member['network_id']
        member['network'] = service['networks'][network_id]
        members.append(member)

        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)
        network_helper.add_fdb_entries(bigip, fdb_entries=tunnel_records)

        # expect to modify with second member's VTEP and MAC addr
        tunnel.records_s.records.create.assert_called_with(
            name='fa:16:3e:0d:fa:c6', endpoint='192.168.130.60')

    def test_network_helper_delete_fdb_entries(
            self, l2_service, service, bigips):
        # delete member fdb entry
        loadbalancer = None
        members = list()
        member = service['members'][1]
        network_id = member['network_id']
        member['network'] = service['networks'][network_id]
        members.append(member)

        tunnel_records = l2_service.create_fdb_records(loadbalancer, members)

        network_helper = NetworkHelper()
        tunnel = mock.MagicMock()
        tunnel.exists = mock.MagicMock(return_value=True)

        tunnel_record = mock.MagicMock()
        tunnel.records_s.records.load = mock.MagicMock(
            return_value=tunnel_record)
        tunnel.records_s.records.exist = mock.MagicMock(return_value=True)

        bigip = bigips[0]
        bigip.tm.net.fdb.tunnels.tunnel.load = mock.MagicMock(
            return_value=tunnel)
        network_helper.delete_fdb_entries(bigip, fdb_entries=tunnel_records)

        # expect to delete
        tunnel_record.delete.assert_called()
