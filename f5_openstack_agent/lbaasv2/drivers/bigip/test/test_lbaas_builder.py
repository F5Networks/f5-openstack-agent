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

from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder import \
    LBaaSBuilder


import mock
import pytest


@pytest.fixture
def service():
    return {
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
                      u'weight': 1}],
        u'pools': [{u'admin_state_up': True,
                    u'description': u'',
                    u'healthmonitor_id': u'70fed03a-efc4-460a-8a21',
                    u'id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
                    u'l7_policies': [],
                    u'lb_algorithm': u'ROUND_ROBIN',
                    u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d59',
                    u'name': u'',
                    u'operating_status': u'ONLINE',
                    u'protocol': u'HTTP',
                    u'provisioning_status': u'PENDING_DELETE',
                    u'session_persistence': None,
                    u'sessionpersistence': None,
                    u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd'}],
    }


class TestLbaasBuilder(object):
    """Test _assure_members in LBaaSBuilder"""
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

        service['pools'][0]['provisioning_status'] = 'ACTIVE'
        builder._assure_members(service, mock.MagicMock())
        assert not delete_member_mock.called
