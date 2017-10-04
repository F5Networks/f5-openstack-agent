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
import uuid

from mock import Mock


from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter


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

    @staticmethod
    @pytest.fixture
    def target():
        conf = Mock()
        conf.environment_prefix = 'pre-'
        target = ServiceModelAdapter(conf)
        return target

    @staticmethod
    @pytest.fixture
    def basic_service():
        tenant_id = str(uuid.uuid4())
        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.1%0'),
                'pools': [dict(id=str(uuid.uuid4()),
                               session_persistence=True)],
                'listener': dict(id=str(uuid.uuid4()),
                                 connection_limit=4,
                                 protocol='HTTPS',
                                 protocol_port='8080',
                                 admin_state_up=True)}

    def test_init_pool_name(self, target):
        partition = str(uuid.uuid4())
        network_id = str(uuid.uuid4())
        id = 'pre-pool'
        loadbalancer = dict(tenant_id=partition, network_id=network_id)
        pool = dict(id='pool')
        target.get_folder_name = Mock(return_value=partition)
        target.prefix = 'pre-'
        expected = dict(name=id, partition=partition)
        assert target.init_pool_name(loadbalancer, pool) == expected

    def test_get_virtual(self, target, basic_service):
        tenant_id = basic_service['loadbalancer']['tenant_id']
        target.get_folder_name = Mock(return_value=tenant_id)
        target.snat_mode = Mock(return_value=True)
        basic_service['pool'] = basic_service['pools'][0]
        vip = 'vip'
        target._map_virtual = Mock(return_value=vip)
        target._add_bigip_items = Mock()
        assert target.get_virtual(basic_service) == vip
        assert basic_service['pool']['session_persistence'] == \
            basic_service['listener']['session_persistence']
        assert basic_service['listener']['snat_pool_name'] == tenant_id
        target._map_virtual.assert_called_once_with(
            basic_service['loadbalancer'], basic_service['listener'],
            pool=basic_service['pool'])
        target._add_bigip_items.assert_called_once_with(
            basic_service['listener'], vip)

    def test_init_virtual_name(self, target, basic_service):
        listener = basic_service['listener']
        loadbalancer = basic_service['loadbalancer']
        tenant_id = loadbalancer['tenant_id']
        target.get_folder_name = Mock(return_value=tenant_id)
        target.prefix = 'pre-'
        name = target.prefix + listener['id']
        assert target._init_virtual_name(loadbalancer, listener) == \
            dict(name=name, partition=tenant_id)
        target.get_folder_name.assert_called_once_with(tenant_id)

    def test_init_virtual_name_with_pool(self, target, basic_service):
        loadbalancer = basic_service['loadbalancer']
        listener = basic_service['listener']
        pool = basic_service['pools'][0]
        target._init_virtual_name = Mock(return_value=dict())
        target.init_pool_name = Mock(return_value='pool')
        assert target._init_virtual_name_with_pool(
            loadbalancer, listener, pool) == dict(pool='pool')
        target._init_virtual_name.assert_called_once_with(
            loadbalancer, listener)
        target.init_pool_name.assert_called_once_with(
            loadbalancer, pool)

    def test_get_vip_default_pool(self, target, basic_service):
        pool = basic_service['pools'][0]
        basic_service['pool'] = pool
        loadbalancer = basic_service['loadbalancer']
        listener = basic_service['listener']
        vip = 'vip'
        target._init_virtual_name_with_pool = Mock(return_value=vip)
        assert vip == target.get_vip_default_pool(basic_service)
        target._init_virtual_name_with_pool.assert_called_once_with(
            loadbalancer, listener, pool=pool)

    def test_map_virtual(self, target, basic_service):
        pool = basic_service['pools'][0]
        loadbalancer = basic_service['loadbalancer']
        listener = basic_service['listener']
        description = 'description'
        target.get_resource_description = Mock(return_value=description)
        target._init_virtual_name_with_pool = Mock(return_value=dict())
        cx_limit = listener['connection_limit']
        proto_port = listener['protocol_port']
        vip_address = loadbalancer['vip_address'].replace('%0', '')
        listener['pool'] = pool
        expected = dict(
            destination=vip_address + ':' + proto_port, ipProtocol='tcp',
            connectionLimit=cx_limit, description=description, enabled=True,
            pool=pool)
        assert expected == target._map_virtual(
                loadbalancer, listener, pool=pool)

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

    def test_pool_member_weight_least_conns(self, pool_member_service):
        '''lb method changes if member has weight and lb method least conns.

        The pool's lb method should be set to 'ratio-least-connections-member'.
        '''

        adapter = ServiceModelAdapter(mock.MagicMock())

        pool = adapter.get_pool(pool_member_service)
        assert pool['loadBalancingMode'] == 'ratio-least-connections-member'

    def test_pool_member_weight_round_robin(self, pool_member_service):
        '''lb method changes if member has weight and lb method round robin

        The pool's lb method should be set to 'ratio-member'.
        '''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        srvc['pool']['lb_algorithm'] = 'ROUND_ROBIN'
        pool = adapter.get_pool(srvc)
        assert pool['loadBalancingMode'] == 'ratio-member'

    def test_pool_member_weight_source_ip(self, pool_member_service):
        '''lb method changes if member has weight and lb method source ip

        The pool's lb method should be set to 'least-connections-node'
        '''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        srvc['pool']['lb_algorithm'] = 'SOURCE_IP'
        pool = adapter.get_pool(srvc)
        assert pool['loadBalancingMode'] == 'least-connections-node'

    def test_pool_member_weight_bad_lb_method(self, pool_member_service):
        '''If lb method is bad and member has weight, lb is changed

        The pool's lb method should be set to 'ratio-member'
        '''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        srvc['pool']['lb_algorithm'] = 'ROUND_ROCK'
        pool = adapter.get_pool(srvc)
        assert pool['loadBalancingMode'] == 'ratio-member'

    def test_pool_member_weight_no_lb_method(self, pool_member_service):
        '''If lb method does not exist, no change is made.'''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        del srvc['pool']['lb_algorithm']
        pool = adapter.get_pool(srvc)
        assert 'loadBalancingMode' not in pool

    def test_pool_member_with_weight_deleted(self, pool_member_service):
        '''If lb method does not exist, no change is made.'''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        del srvc['pool']['lb_algorithm']
        pool = adapter.get_pool(srvc)
        assert 'loadBalancingMode' not in pool

    def test_pool_no_members_least_conns(self, pool_member_service):
        '''No members, lb method should be 'least-connections-member'.'''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        del srvc['members']
        pool = adapter.get_pool(srvc)
        assert pool['loadBalancingMode'] == 'least-connections-member'

    def test_pool_no_members_round_robin(self, pool_member_service):
        '''No members, lb method should be 'round-robin'.'''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        del srvc['members']
        srvc['pool']['lb_algorithm'] = 'ROUND_ROBIN'
        pool = adapter.get_pool(srvc)
        assert pool['loadBalancingMode'] == 'round-robin'

    def test_pool_no_members_source_ip(self, pool_member_service):
        '''No members, lb method should be 'least-connections-node'.'''

        adapter = ServiceModelAdapter(mock.MagicMock())
        srvc = copy.deepcopy(pool_member_service)
        del srvc['members']
        srvc['pool']['lb_algorithm'] = 'SOURCE_IP'
        pool = adapter.get_pool(srvc)
        assert pool['loadBalancingMode'] == 'least-connections-node'
