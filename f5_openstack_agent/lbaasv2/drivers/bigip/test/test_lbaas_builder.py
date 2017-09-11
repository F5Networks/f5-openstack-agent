# coding=utf-8
# Copyright 2014-2016 F5 Networks Inc.
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

import copy
import mock
import pytest

from requests import HTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder import \
    LBaaSBuilder

POOL_BLDR_PATH = 'f5_openstack_agent.lbaasv2.drivers.bigip.pool_service.' \
    'PoolServiceBuilder'


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
        u'networks': {
            'cdf1eb6d-9b17-424a-a054-778f3d3a5490': {
                "admin_state_up": True,
                "id": 'cdf1eb6d-9b17-424a-a054-778f3d3a5490',
                'mtu': 0,
                'name': 'foodogzoo',
                'provider:network_type': 'vxlan',
                'provider:physical_network': None,
                'router:external': False,
                'shared': True,
                'status': 'ACTIVE',
                'subnets': ['4dc7caad-f9a9-4050-914e-b60eb6cf8ef7'],
                'tenant_id': '980e3f914f3e40359c3c2d9470fb2e8a',
                'vlan_transparent': None,
                     }},
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
                          u'device_owner': u'network:f5lbaasv2',
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
            u'vxlan_vteps': []},
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
                      u'port': 'port',
                      u'weight': 1},
                     {u'address': u'10.2.2.4',
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
                      u'port': 'port',
                      u'weight': 1}],
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
                    u'protocol': u'HTTP',
                    u'provisioning_status': u'ACTIVE',
                    u'session_persistence': None,
                    u'sessionpersistence': None,
                    u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd'}],
    }


class MockHTTPError(HTTPError):
    def __init__(self, response_obj):
        self.response = response_obj


class MockHTTPErrorResponse409(HTTPError):
    def __init__(self):
        self.text = 'Conflict.'
        self.status_code = 409


class TestLbaasBuilder(object):
    """Test _assure_members in LBaaSBuilder"""
    @pytest.mark.skip(reason="Test is not valid without port object")
    def test_assure_members_deleted(self, service):
        """Test that delete method is called.

        When a member's pool is in PENDING_DELETE, a member should be
        deleted regardless of its status.
        """

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        pool_builder_mock = mock.MagicMock()
        delete_member_mock = mock.MagicMock()
        pool_builder_mock.delete_member = delete_member_mock
        builder.pool_builder = pool_builder_mock
        service['pools'][0]['provisioning_status'] = 'PENDING_DELETE'

        builder._assure_members(service, mock.MagicMock())
        assert delete_member_mock.called

    def test_assure_members_not_deleted(self, service):
        """Test that delete method is NOT called.

        When a member's pool is not in PENDING_DELETE, a member should be
        NOT be deleted if its status is something other than PENDING_DELETE.
        """
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        pool_builder_mock = mock.MagicMock()
        delete_member_mock = mock.MagicMock()
        pool_builder_mock.delete_member = delete_member_mock
        builder.pool_builder = pool_builder_mock

        builder._assure_members(service, mock.MagicMock())
        assert not delete_member_mock.called

    def test__get_pool_members(self, pool_member_service):
        '''Method will map members with their pool.'''

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        service = copy.deepcopy(pool_member_service)
        members = builder._get_pool_members(service, service['pool']['id'])
        assert len(members) == 2

        # Modify pool_id of both members, expect no members returned
        service['members'][0]['pool_id'] = 'test'
        service['members'][1]['pool_id'] = 'test'
        members = builder._get_pool_members(service, service['pool']['id'])
        assert members == []

    def test_assure_members_update_exception(self, service):
        """Test update_member exception and setting ERROR status.

        When LBaaSBuilder assure_members() is called and the member is
        updated, LBaaSBuilder must catch any exception from PoolServiceBuilder
        update_member() and set member provisioning_status to ERROR.
        """
        with mock.patch(POOL_BLDR_PATH + '.create_member') as mock_create:
            with mock.patch(POOL_BLDR_PATH + '.update_member') as mock_update:
                mock_create.side_effect = MockHTTPError(
                    MockHTTPErrorResponse409())
                mock_update.side_effect = MockHTTPError(
                    MockHTTPErrorResponse409())
                service['members'][0]['provisioning_status'] = 'PENDING_UPDATE'
                builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
                with pytest.raises(f5_ex.MemberUpdateException):
                    builder._assure_members(service, mock.MagicMock())
                    assert service['members'][0]['provisioning_status'] ==\
                        'ERROR'

    def test_assure_member_has_port(self, service):
        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'lbaas_builder.LOG') as mock_log:
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            builder._assure_members(service, mock.MagicMock())
            assert mock_log.warning.call_args_list == []

    def test_assure_member_has_no_port(self, service):
        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'lbaas_builder.LOG') as mock_log:
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            service['members'][0].pop('port', None)
            service['members'][1].pop('port', None)
            builder._assure_members(service, mock.MagicMock())
            assert \
                mock_log.warning.call_args_list == \
                [mock.call('Member definition does not include Neutron port'),
                 mock.call('Member definition does not include Neutron port')]

    def test_assure_member_has_one_port(self, service):
        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'lbaas_builder.LOG') as mock_log:
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            service['members'][0].pop('port', None)
            builder._assure_members(service, mock.MagicMock())
            assert \
                mock_log.warning.call_args_list == \
                [mock.call('Member definition does not include Neutron port')]

    def test_assure_member_has_two_ports(self, service):
        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'lbaas_builder.LOG') as mock_log:
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            builder._assure_members(service, mock.MagicMock())
            assert mock_log.warning.call_args_list == []

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_pool_create(
            self, mock_update, mock_create, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'PENDING_CREATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_pools_created(svc)
        builder._assure_pools_configured(svc)
        assert mock_create.called
        assert not mock_update.called

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_pool_update(
            self, mock_update, mock_create, service):
        '''update_pool should be called in pool builder on pool update'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'PENDING_UPDATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_pools_created(svc)
        builder._assure_pools_configured(svc)
        assert mock_update.called
        assert not mock_create.called

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_pool_active(
            self, mock_update, mock_create, service):
        '''create_pool should be called in pool builder with active pool'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_pools_created(svc)
        builder._assure_pools_configured(svc)
        assert not mock_update.called
        assert mock_create.called

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_pool_error(
            self, mock_update, mock_create, service):
        '''create_pool should be called in pool builder with errored pool'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ERROR'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_pools_created(svc)
        builder._assure_pools_configured(svc)
        assert not mock_update.called
        assert mock_create.called
