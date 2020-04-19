# coding=utf-8
# Copyright (c) 2014-2018, F5 Networks, Inc.
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

import f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter
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
        default_pool_id = str(uuid.uuid4())
        monitor_id = str(uuid.uuid4())
        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.1%0'),
                'pools': [dict(id=default_pool_id,
                               session_persistence=True)],
                'healthmonitors': [dict(id=str(monitor_id))],
                'listener': dict(id=str(uuid.uuid4()),
                                 connection_limit=4,
                                 protocol='HTTPS',
                                 protocol_port='8080',
                                 admin_state_up=True,
                                 default_pool_id=default_pool_id)}

    @staticmethod
    @pytest.fixture
    def basic_l7service():
        tenant_id = str(uuid.uuid4())
        default_pool_id = str(uuid.uuid4())
        policy_id = str(uuid.uuid4())
        l7policy_rules = list()
        for i in range(5):
            l7policy_rules.append(dict(id=str(uuid.uuid4()),
                                       provisioning_status="ACTIVE"))

        l7policy = dict(id=policy_id)
        l7policy['rules'] = [dict(id=rule['id'])
                             for rule in l7policy_rules]

        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.100%0'),
                'pools': [dict(id=default_pool_id,
                               session_persistence=True)],
                'l7policies': [l7policy],
                'l7policy_rules': l7policy_rules,
                'listener': dict(id=str(uuid.uuid4()),
                                 connection_limit=4,
                                 protocol='HTTP',
                                 protocol_port='80',
                                 admin_state_up=True,
                                 default_pool_id=default_pool_id,
                                 l7_policies=[dict(id=policy_id)])}

    @staticmethod
    @pytest.fixture
    def basic_l7service_2policies():
        tenant_id = str(uuid.uuid4())
        default_pool_id = str(uuid.uuid4())
        listener_policy_ids = [dict(id=str(uuid.uuid4())),
                               dict(id=str(uuid.uuid4()))]
        listener_id = str(uuid.uuid4())
        l7policies = list()
        l7policy_rules = list()
        for policy in listener_policy_ids:
            l7policy = dict(id=policy['id'],
                            listener_id=listener_id)

            rules = list()
            for i in range(2):
                rule = dict(id=str(uuid.uuid4()),
                            provisioning_status="ACTIVE")
                l7policy_rules.append(rule)
                rules.append(rule)

            l7policy['rules'] = [dict(id=r['id']) for r in rules]
            l7policies.append(l7policy)

        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.100%0'),
                'pools': [dict(id=default_pool_id,
                               session_persistence=True)],
                'l7policies': l7policies,
                'l7policy_rules': l7policy_rules,
                'listener': dict(id=listener_id,
                                 connection_limit=4,
                                 protocol='HTTP',
                                 protocol_port='80',
                                 admin_state_up=True,
                                 default_pool_id=default_pool_id,
                                 l7_policies=listener_policy_ids)}

    @staticmethod
    @pytest.fixture
    def basic_service_no_persist():
        tenant_id = str(uuid.uuid4())
        default_pool_id = str(uuid.uuid4())
        monitor_id = str(uuid.uuid4())
        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.1%0'),
                'pools': [dict(id=default_pool_id,
                               session_persistence=False)],
                'healthmonitors': [dict(id=str(monitor_id))],
                'listener': dict(id=str(uuid.uuid4()),
                                 connection_limit=4,
                                 protocol='HTTPS',
                                 protocol_port='8080',
                                 admin_state_up=True,
                                 default_pool_id=default_pool_id)}

    @staticmethod
    @pytest.fixture
    def basic_http_service_no_pool():
        tenant_id = str(uuid.uuid4())
        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.1%0'),
                'listener': dict(id=str(uuid.uuid4()),
                                 connection_limit=4,
                                 protocol='HTTP',
                                 protocol_port='8080',
                                 admin_state_up=True,
                                 default_pool_id='')}

    @staticmethod
    @pytest.fixture
    def basic_service_with_monitor():
        tenant_id = str(uuid.uuid4())
        default_pool_id = str(uuid.uuid4())
        monitor_id = str(uuid.uuid4())
        return {'loadbalancer': dict(id=str(uuid.uuid4()),
                                     tenant_id=tenant_id,
                                     vip_address='192.168.1.1%0'),
                'pools': [dict(id=default_pool_id,
                               session_persistence=True,
                               healthmonitor_id=monitor_id)],
                'healthmonitors': [dict(id=str(monitor_id))],
                'listener': dict(id=str(uuid.uuid4()),
                                 connection_limit=4,
                                 protocol='HTTPS',
                                 protocol_port='8080',
                                 admin_state_up=True,
                                 default_pool_id=default_pool_id)}

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

    def test_get_virtual_name(self, target, basic_service):
        listener = basic_service['listener']
        loadbalancer = basic_service['loadbalancer']
        tenant_id = loadbalancer['tenant_id']
        target.prefix = 'pre-'
        target.get_folder_name = Mock(
            return_value=target.prefix + tenant_id)

        vs_name = target.get_virtual_name(basic_service)
        assert vs_name['name'] == target.prefix + listener['id']
        assert vs_name['partition'] == target.prefix + \
            loadbalancer['tenant_id']

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
            pool=basic_service['pool'], policies=list(), irules=list())

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

    def test_map_virtual_no_persist(self, target, basic_service_no_persist):
        basic_service = basic_service_no_persist
        pool = basic_service['pools'][0]
        # pool['provisioning_status'] = "ACTIVE"
        loadbalancer = basic_service['loadbalancer']
        listener = basic_service['listener']
        description = 'description'
        target.get_resource_description = Mock(return_value=description)

        cx_limit = listener['connection_limit']
        proto_port = listener['protocol_port']
        vip_address = loadbalancer['vip_address'].replace('%0', '')
        listener['pool'] = pool
        expected = dict(
            name="pre-_" + listener['id'],
            partition="pre-_" + loadbalancer['tenant_id'],
            destination=vip_address + ':' + proto_port, ipProtocol='tcp',
            connectionLimit=cx_limit, description=description, enabled=True,
            pool="pre-_" + pool['id'], mask="255.255.255.255",
            vlansDisabled=True,
            profiles=['/Common/fastL4'],
            vlans=[], policies=[], rules=[],
            fallbackPersistence='', persist=[],
            sourceAddressTranslation={'pool': None, 'type': None},
        )
        assert expected == target._map_virtual(
            loadbalancer, listener, pool=pool)

    def test_add_vlan_and_snat_no_snat(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service['listener']

        vip = dict()
        adapter._add_vlan_and_snat(listener, vip)
        expected = dict(
            vlansDisabled=True, vlans=[],
            sourceAddressTranslation={'pool': None, 'type': None}
        )
        assert vip == expected

    def test_add_vlan_and_snat_automap(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service['listener']
        listener['use_snat'] = True
        vip = dict()
        adapter._add_vlan_and_snat(listener, vip)
        expected = dict(
            sourceAddressTranslation=dict(type='automap'),
            vlansDisabled=True, vlans=[])
        assert vip == expected

    def test_add_vlan_and_snatpool(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service['listener']
        listener['use_snat'] = True
        listener['snat_pool_name'] = 'mysnat'
        vip = dict()
        adapter._add_vlan_and_snat(listener, vip)
        expected = dict(sourceAddressTranslation=dict(
            type='snat', pool='mysnat'), vlansDisabled=True,
            vlans=[])
        assert vip == expected

    def test_add_session_persistence_http_no_pool(
            self, basic_http_service_no_pool):
        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_http_service_no_pool['listener']

        vip = dict()
        adapter._add_profiles_session_persistence(listener, None, vip)

        expected = dict(ipProtocol='tcp',
                        profiles=['/Common/http',
                                  '/Common/oneconnect'],
                        fallbackPersistence='', persist=[])
        assert vip == expected

    def test_add_session_persistence_https_no_pool(
            self, basic_http_service_no_pool):
        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_http_service_no_pool['listener']
        listener['protocol'] = 'HTTPS'

        vip = dict()
        adapter._add_profiles_session_persistence(listener, None, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/fastL4'],
                        fallbackPersistence='', persist=[])
        assert vip == expected

    def test_add_session_peristence_tcp_no_pool(
            self, basic_http_service_no_pool):
        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_http_service_no_pool['listener']
        listener['protocol'] = 'TCP'

        vip = dict()
        adapter._add_profiles_session_persistence(listener, None, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/fastL4'],
                        fallbackPersistence='', persist=[])
        assert vip == expected

    def test_add_session_persistence_pool_no_persist(
            self, basic_service_no_persist):

        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service_no_persist['listener']
        pool = basic_service_no_persist['pools'][0]

        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp',
                        profiles=['/Common/fastL4'],
                        fallbackPersistence='', persist=[])
        assert vip == expected

    def test_add_session_persistence_pool_invalid_persist(
            self, basic_service_no_persist):

        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service_no_persist['listener']
        pool = basic_service_no_persist['pools'][0]
        pool['session_persistence'] = dict(type="INVALID")
        f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter.LOG = Mock()
        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp',
                        profiles=['/Common/fastL4'],
                        fallbackPersistence='', persist=[])
        assert vip == expected

    def test_add_session_persistence_sourceip_persist(
            self, basic_service_no_persist):

        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service_no_persist['listener']
        pool = basic_service_no_persist['pools'][0]
        pool['session_persistence'] = dict(type="SOURCE_IP")

        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/fastL4'],
                        fallbackPersistence='',
                        persist=[dict(name='/Common/source_addr')])
        assert vip == expected

        pool['lb_algorithm'] = 'SOURCE_IP'
        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/fastL4'],
                        fallbackPersistence='',
                        persist=[dict(name='/Common/source_addr')])
        assert vip == expected

    def test_add_session_persistence_cookie_persist(
            self, basic_service_no_persist):

        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service_no_persist['listener']
        pool = basic_service_no_persist['pools'][0]
        pool['session_persistence'] = dict(type="HTTP_COOKIE")

        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/http',
                                                    '/Common/oneconnect'],
                        fallbackPersistence='',
                        persist=[dict(name='/Common/cookie')])
        assert vip == expected

        pool['lb_algorithm'] = 'SOURCE_IP'
        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/http',
                                                    '/Common/oneconnect'],
                        fallbackPersistence='/Common/source_addr',
                        persist=[dict(name='/Common/cookie')])
        assert vip == expected

    def test_add_session_persistence_cookie_persist_tcp(
            self, basic_service_no_persist):

        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service_no_persist['listener']
        listener['protocol'] = 'TCP'
        pool = basic_service_no_persist['pools'][0]
        pool['session_persistence'] = dict(type="HTTP_COOKIE")

        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/http',
                                                    '/Common/oneconnect'],
                        fallbackPersistence='',
                        persist=[dict(name='/Common/cookie')])
        assert vip == expected

        pool['lb_algorithm'] = 'SOURCE_IP'
        vip = dict()
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(ipProtocol='tcp', profiles=['/Common/http',
                                                    '/Common/oneconnect'],
                        fallbackPersistence='/Common/source_addr',
                        persist=[dict(name='/Common/cookie')])
        assert vip == expected

    def test_add_session_persistence_app_cookie_persist(
            self, basic_service_no_persist):

        adapter = ServiceModelAdapter(mock.MagicMock())
        listener = basic_service_no_persist['listener']
        pool = basic_service_no_persist['pools'][0]
        pool['session_persistence'] = dict(type="APP_COOKIE")
        vip_name = 'vip_name'
        persist_name = "app_cookie_{}".format(vip_name)

        vip = dict(name=vip_name)
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(
            name=vip_name,
            ipProtocol='tcp', profiles=['/Common/http',
                                        '/Common/oneconnect'],
            fallbackPersistence='',
            persist=[dict(name=persist_name)])
        assert vip == expected

        pool['lb_algorithm'] = 'SOURCE_IP'
        vip = dict(name=vip_name)
        adapter._add_profiles_session_persistence(listener, pool, vip)

        expected = dict(
            name=vip_name,
            ipProtocol='tcp', profiles=['/Common/http',
                                        '/Common/oneconnect'],
            fallbackPersistence='/Common/source_addr',
            persist=[dict(name=persist_name)])
        assert vip == expected

    def test_vs_http_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        service['listener']['protocol'] = 'HTTPS'

        # should have http and oneconnect but not fastL4
        vs = adapter.get_virtual(service)
        assert '/Common/fastL4' in vs['profiles']

    def test_vs_https_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        # should have http and oneconnect but not fastL4
        service['listener']['protocol'] = 'HTTPS'
        vs = adapter.get_virtual(service)
        assert '/Common/fastL4' in vs['profiles']

    def test_vs_tcp_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        service['listener']['protocol'] = 'TCP'
        vs = adapter.get_virtual(service)

        # should have fastL4 but not http and oneconnect
        assert '/Common/http' not in vs['profiles']
        assert '/Common/oneconnect' not in vs['profiles']
        assert '/Common/fastL4' in vs['profiles']

    def test_vs_terminated_https_profiles(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        # should have http and oneconnect but not fastL4
        service['listener']['protocol'] = 'TERMINATED_HTTPS'
        vs = adapter.get_virtual(service)
        assert '/Common/http' in vs['profiles']
        assert '/Common/oneconnect' in vs['profiles']
        assert '/Common/fastL4' not in vs['profiles']

    def test_get_vip_default_pool_no_pool(self, service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        pool = adapter.get_vip_default_pool(service)
        assert not pool

    def test_get_vip_default_pool(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        pools = basic_service.get('pools', [None])
        default_pool = adapter.get_vip_default_pool(basic_service)
        assert default_pool == pools[0]

    def test_get_vip_default_pool_pending_delete(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        pools = basic_service.get('pools', [None])
        pools[0]['provisioning_status'] = "PENDING_DELETE"
        default_pool = adapter.get_vip_default_pool(basic_service)
        assert not default_pool

    def test_get_vip_default_pool_pending_create(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())

        pools = basic_service.get('pools', [None])
        pools[0]['provisioning_status'] = "PENDING_CREATE"
        default_pool = adapter.get_vip_default_pool(basic_service)
        assert default_pool == pools[0]

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

    def test_get_pool_monitor_no_monitor(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        pools = basic_service.get('pools', [None])
        assert not adapter._get_pool_monitor(pools[0], basic_service)

        pools[0]['healthmonitor_id'] = str(uuid.uuid4())
        assert not adapter._get_pool_monitor(pools[0], basic_service)

    def test_get_pool_monitor(self, basic_service_with_monitor):
        basic_service = basic_service_with_monitor
        adapter = ServiceModelAdapter(mock.MagicMock())
        pools = basic_service.get('pools', [None])
        monitor = adapter._get_pool_monitor(pools[0], basic_service)

        assert monitor == basic_service.get('healthmonitors')[0]

    def test_get_vlan(self, basic_service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        vip = dict(vlans=[], vlansDisabled=True)
        bigip = Mock()

        # Test case where network is not assured
        bigip.assured_networks = {}
        adapter.get_vlan(vip, bigip, "net_UUID")

        expected = dict(vlans=[], vlansDisabled=True)

        assert vip == expected

        # Test case where network is assured.
        vip = dict(vlans=[], vlansDisabled=True)
        bigip.assured_networks = {'net_UUID': 'tunnel-vxlan-100'}
        adapter.get_vlan(vip, bigip, "net_UUID")

        expected = dict(vlans=['tunnel-vxlan-100'], vlansEnabled=True)

        assert vip == expected

        # Test case where network is not assured, but in common networks
        vip = dict(vlans=[], vlansDisabled=True)
        bigip.assured_networks = {}
        adapter.conf.common_network_ids = {'net_UUID': 'vlan-100'}

        adapter.get_vlan(vip, bigip, "net_UUID")

        expected = dict(vlans=['vlan-100'], vlansEnabled=True)

        assert vip == expected

    def test_get_l7policy(self, basic_l7service):

        adapter = ServiceModelAdapter(mock.MagicMock())
        vip = dict(policies=list())
        listener = basic_l7service['listener']
        policies = list()

        adapter._apply_l7_and_esd_policies(listener, policies, vip)
        assert vip == dict(policies=list())

    def test_get_listener_policies(self, basic_l7service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        policies = adapter.get_listener_policies(basic_l7service)
        policy = policies[0]

        assert len(policy['rules']) == len(policy['l7policy_rules'])
        for rule in policy['l7policy_rules']:
            assert rule.get('provisioning_status', "") == "ACTIVE"

    def test_get_listener_policies_pending_delete(self, basic_l7service):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        service_rules = basic_l7service['l7policy_rules']
        service_rules[2]['provisioning_status'] = "PENDING_DELETE"
        policies = adapter.get_listener_policies(basic_l7service)
        policy = policies[0]

        assert len(policy['rules']) == 5
        assert len(policy['l7policy_rules']) == 4

        for rule in policy['l7policy_rules']:
            assert rule.get('provisioning_status', "") == "ACTIVE"

    def test_get_listener_policies_2_policies(self, basic_l7service_2policies):
        adapter = ServiceModelAdapter(mock.MagicMock())
        adapter.esd = Mock()
        adapter.esd.get_esd.return_value = None

        l7service = basic_l7service_2policies
        listener = l7service.get('listener', None)

        policies = adapter.get_listener_policies(l7service)

        assert len(policies) == 2
        for policy in policies:
            assert len(policy['rules']) == 2
            assert len(policy['l7policy_rules']) == 2
            assert policy['listener_id'] == listener['id']

    def test_get_tls(self, basic_l7service):
        pass
        # adapter = ServiceModelAdapter(mock.MagicMock())

    def test_get_resource_description(self):
        adapter = ServiceModelAdapter(mock.MagicMock())
        resource = dict(name='test_name',
                        description='test_description')

        # invalid input type
        with pytest.raises(ValueError):
            description = adapter.get_resource_description('')

        # both name and description
        description = adapter.get_resource_description(resource)
        assert description == 'test_name: test_description'

        # name but no description
        resource['description'] = ''
        description = adapter.get_resource_description(resource)
        assert description == 'test_name:'

        # handle None for value
        resource['description'] = None
        description = adapter.get_resource_description(resource)
        assert description == 'test_name:'

        # neither name nor description
        resource['name'] = ''
        description = adapter.get_resource_description(resource)
        assert description == ''

        # handle None for value
        resource['name'] = None
        description = adapter.get_resource_description(resource)
        assert description == ''

        # description but no name
        resource['description'] = 'test_description'
        description = adapter.get_resource_description(resource)
        assert description == 'test_description'

        # no keys defined
        resource.pop('name')
        description = adapter.get_resource_description(resource)
        assert description == 'test_description'

        resource['name'] = 'test_name'
        resource.pop('description')
        description = adapter.get_resource_description(resource)
        assert description == 'test_name:'

    def test_apply_empty_esd(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict()
        vip = dict()
        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "profiles" not in vip
        assert "rules" not in vip
        assert "policies" not in vip

    def test_apply_esd_oneconnect_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_oneconnect_profile="oneconnect_profile")
        vip = dict(profiles=["/Common/http", "/Common/oneconnect"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=["/Common/http",
                                  dict(name="tcp",
                                       partition="Common",
                                       context="all"),
                                  "/Common/oneconnect_profile"]
                        )
        assert vip == expected

    def test_apply_esd_ctcp_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_ctcp="tcp-mobile-optimized")
        vip = dict(profiles=["/Common/http"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=["/Common/http",
                                  dict(name="tcp-mobile-optimized",
                                       partition="Common",
                                       context="all")
                                  ]
                        )
        assert vip == expected

    def test_apply_esd_stcp_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_stcp="tcp-lan-optimized")
        vip = dict(profiles=["/Common/http"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=["/Common/http",
                                  dict(name="tcp-lan-optimized",
                                       partition="Common",
                                       context="serverside"),
                                  dict(name="tcp",
                                       partition="Common",
                                       context="clientside")
                                  ]
                        )

        assert vip == expected

    def test_apply_esd_ctcp_and_stcp_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_ctcp="tcp-mobile-optimized",
                   lbaas_stcp="tcp-lan-optimized")
        vip = dict(profiles=["/Common/http"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=["/Common/http",
                                  dict(name="tcp-lan-optimized",
                                       partition="Common",
                                       context="serverside"),
                                  dict(name="tcp-mobile-optimized",
                                       partition="Common",
                                       context="clientside")
                                  ]
                        )

        assert vip == expected

    def test_apply_esd_ssl_profiles(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_cssl_profile="clientssl")
        vip = dict(profiles=["/Common/http"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=["/Common/http",
                                  dict(name="tcp",
                                       partition="Common",
                                       context="all"),
                                  dict(name="clientssl",
                                       partition="Common",
                                       context="clientside")
                                  ]
                        )

        assert vip == expected

        esd = dict(lbaas_sssl_profile="serverssl")
        vip = dict(profiles=["/Common/http"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=["/Common/http",
                                  dict(name="tcp",
                                       partition="Common",
                                       context="all"),
                                  dict(name="serverssl",
                                       partition="Common",
                                       context="serverside")
                                  ]
                        )

        assert vip == expected

    def test_apply_esd_http_profiles(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_http_profile="http_profile")
        vip = dict(profiles=["/Common/http"])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        expected = dict(profiles=[dict(name="tcp",
                                       partition="Common",
                                       context="all"),
                                  "/Common/http_profile"]
                        )

        assert vip == expected

    def test_apply_esd_persist_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_persist="hash")
        vip = dict(profiles=[])

        adapter._apply_esd(vip, esd)

        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        assert vip['persist'] == [dict(name="hash")]
        assert vip['profiles'] == [
            dict(name="tcp", partition="Common", context="all")]

    def test_apply_esd_persist_profile_collision(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_persist="hash")
        vip = dict(profiles=[], persist=[dict(name='sourceip')])

        adapter._apply_esd(vip, esd)

        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        assert vip['persist'] == [dict(name="hash")]
        assert vip['profiles'] == [dict(
            name="tcp", partition="Common", context="all")]

    def test_apply_esd_fallback_persist_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_fallback_persist="hash",
                   lbaas_persist="sourceip")

        vip = dict(profiles=[])

        adapter._apply_esd(vip, esd)

        assert "policies" not in vip

        assert vip['persist'] == [dict(name="sourceip")]
        assert vip['fallbackPersistence'] == 'hash'
        assert vip['profiles'] == [
            dict(name="tcp", partition="Common", context="all")]

    def test_apply_esd_fallback_persist_profile_collision(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_fallback_persist="hash",
                   lbaas_persist="sourceip")

        vip = dict(profiles=[], fallbackPersistence='mock')

        adapter._apply_esd(vip, esd)

        assert "policies" not in vip

        assert vip['persist'] == [dict(name="sourceip")]
        assert vip['fallbackPersistence'] == 'hash'
        assert vip['profiles'] == [dict(
            name="tcp", partition="Common", context="all")]

    def test_apply_esd_fallback_persist_profile_nopersist(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_fallback_persist="hash")

        vip = dict(profiles=[])

        adapter._apply_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip

    def test_apply_esd_irules_empty(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_irule=[])

        vip = dict(profiles=[])

        adapter._apply_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert not vip['rules']

    def test_apply_esd_irules(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_irule=[
            "_sys_https_redirect",
            "_sys_APM_ExchangeSupport_helper"
        ])
        vip = dict(profiles=[])

        adapter._apply_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert vip['rules'] == [
            "/Common/_sys_https_redirect",
            "/Common/_sys_APM_ExchangeSupport_helper"]

    def test_apply_esd_policy(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_policy=["demo_policy"])
        vip = dict(profiles=[])

        adapter._apply_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert vip['policies'] == [dict(name='demo_policy',
                                        partition="Common")]

    def test_apply_l4_esd_persist_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_persist="hash")
        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        assert vip['persist'] == [dict(name="hash")]
        assert vip['profiles'] == ["/Common/http", "/Common/fastL4"]

    def test_apply_l4_esd_persist_profile_collision(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_persist="hash")
        vip = dict(profiles=[],
                   persist=[dict(name='sourceip')])

        adapter._apply_fastl4_esd(vip, esd)

        assert "fallbackPersistence" not in vip
        assert "policies" not in vip

        assert vip['persist'] == [dict(name="hash")]
        assert vip['profiles'] == ["/Common/http", "/Common/fastL4"]

    def test_apply_l4_esd_fallback_persist_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_fallback_persist="hash",
                   lbaas_persist="sourceip")

        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "policies" not in vip

        assert vip['persist'] == [dict(name="sourceip")]
        assert vip['fallbackPersistence'] == 'hash'
        assert vip['profiles'] == ["/Common/http", "/Common/fastL4"]

    def test_apply_l4_esd_fallback_persist_profile_collision(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_fallback_persist="hash",
                   lbaas_persist="sourceip")

        vip = dict(profiles=[], fallbackPersistence='mock')

        adapter._apply_fastl4_esd(vip, esd)

        assert "policies" not in vip

        assert vip['persist'] == [dict(name="sourceip")]
        assert vip['fallbackPersistence'] == 'hash'
        assert vip['profiles'] == ["/Common/http", "/Common/fastL4"]

    def test_apply_l4_esd_http_profile(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_http_profile="http_profile")

        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip

        assert vip['profiles'] == ["/Common/http_profile", "/Common/fastL4"]

    def test_apply_l4_esd_fallback_persist_profile_nopersist(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_fallback_persist="hash")

        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip

    def test_apply_l4_esd_irules_empty(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_irule=[])

        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert not vip['rules']

    def test_apply_l4_esd_irules(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_irule=[
            "_sys_https_redirect",
            "_sys_APM_ExchangeSupport_helper"
        ])
        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "policies" not in vip
        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert vip['rules'] == [
            "/Common/_sys_https_redirect",
            "/Common/_sys_APM_ExchangeSupport_helper"]

    def test_apply_l4_esd_policy(adapter):
        adapter = ServiceModelAdapter(mock.MagicMock())
        esd = dict(lbaas_policy=["demo_policy"])
        vip = dict(profiles=[])

        adapter._apply_fastl4_esd(vip, esd)

        assert "persist" not in vip
        assert "fallbackPersistence" not in vip
        assert vip['policies'] == [dict(name='demo_policy',
                                        partition="Common")]
