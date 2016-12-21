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

from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter


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
        u'listener': {u'admin_state_up': True,
                      u'connection_limit': -1,
                      u'default_pool_id':
                          u'67a89f9a-b172-4e75-b583-46f09451face',
                      u'default_tls_container_id': None,
                      u'description': u'',
                      u'id': u'5bd3f2bd-80ba-43f4-849e-679bf19641e2',
                      u'l7_policies': [
                          {u'id': u'd23fed66-0927-4de4-ae9d-da9799c42269'}],
                      u'loadbalancer_id':
                          u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
                      u'name': u'',
                      u'operating_status': u'ONLINE',
                      u'protocol': u'HTTP',
                      u'protocol_port': 80,
                      u'provisioning_status': u'ACTIVE',
                      u'sni_containers': [],
                      u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd'}
    }


class TestServiceAdapter(object):

    def test_vs_http_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        # should have http and oneconnect but not fastL4
        vs = adapter.get_virtual(service)
        assert '/Common/http' in vs['profiles']
        assert '/Common/oneconnect' in vs['profiles']
        assert '/Common/fastL4' not in vs['profiles']

    def test_vs_https_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        # should have http and oneconnect but not fastL4
        service['listener']['protocol'] = 'HTTPS'
        vs = adapter.get_virtual(service)
        assert '/Common/http' in vs['profiles']
        assert '/Common/oneconnect' in vs['profiles']
        assert '/Common/fastL4' not in vs['profiles']

    def test_vs_tcp_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        service['listener']['protocol'] = 'TCP'
        vs = adapter.get_virtual(service)

        # should have fastL4 but not http and oneconnect
        assert '/Common/http' not in vs['profiles']
        assert '/Common/oneconnect' not in vs['profiles']
        assert '/Common/fastL4' in vs['profiles']

    def test_vs_terminated_https_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        # should have http and oneconnect but not fastL4
        service['listener']['protocol'] = 'TERMINATED_HTTPS'
        vs = adapter.get_virtual(service)
        assert '/Common/http' in vs['profiles']
        assert '/Common/oneconnect' in vs['profiles']
        assert '/Common/fastL4' not in vs['profiles']
