from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_service import \
    LbaasServiceObject

import pytest


class FakeConfig(object):
    def __init__(self, environment_prefix='Fake'):
        self.environment_prefix = environment_prefix


service_def = {
    'healthmonitors':
        [{'admin_state_up': True,
          'delay': 1,
          'expected_codes': '200',
          'http_method': 'GET',
          'id': '3bdb3ba7-a027-4267-9837-8f402bfa6ce8',
          'max_retries': 5,
          'name': '',
          'pool_id': '67a89f9a-b172-4e75-b583-46f09451face',
          'provisioning_status': 'ACTIVE',
          'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
          'timeout': 1,
          'type': 'HTTP',
          'url_path': '/'}],
    'l7policies':
        [{'action': 'REJECT',
          'admin_state_up': True,
          'description': '',
          'id': 'd23fed66-0927-4de4-ae9d-da9799c42269',
          'listener_id': '5bd3f2bd-80ba-43f4-849e-679bf19641e2',
          'name': '',
          'position': 1,
          'provisioning_status': 'ACTIVE',
          'redirect_pool_id': None,
          'redirect_url': None,
          'rules': [{'id': 'fe96d470-f7f5-4ea8-adcd-25e7e2691a9a'}],
          'tenant_id': 'a494c1bc65c346bc86319315d4f138ba'}],
    'l7policy_rules':
        [{'admin_state_up': True,
          'compare_type': 'STARTS_WITH',
          'id': 'fe96d470-f7f5-4ea8-adcd-25e7e2691a9a',
          'invert': False,
          'key': None,
          'policies': [
              {'id': 'd23fed66-0927-4de4-ae9d-da9799c42269'}],
          'policy_id': 'd23fed66-0927-4de4-ae9d-da9799c42269',
          'provisioning_status': 'ACTIVE',
          'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
          'type': 'PATH',
          'value': '/api'}],
    'listeners':
        [{'admin_state_up': True,
          'connection_limit': -1,
          'default_pool_id': '67a89f9a-b172-4e75-b583-46f09451face',
          'default_tls_container_id': None,
          'description': '',
          'id': '5bd3f2bd-80ba-43f4-849e-679bf19641e2',
          'l7_policies': [
              {'id': 'd23fed66-0927-4de4-ae9d-da9799c42269'}],
          'loadbalancer_id': 'c22375f7-82c3-42b7-9590-68f41c04af0c',
          'name': '',
          'operating_status': 'ONLINE',
          'protocol': 'HTTP',
          'protocol_port': 80,
          'provisioning_status': 'ACTIVE',
          'sni_containers': [],
          'tenant_id': 'a494c1bc65c346bc86319315d4f138ba'}],
    'loadbalancer':
        {'admin_state_up': True,
         'description': '',
         'gre_vteps': [],
         'id': 'c22375f7-82c3-42b7-9590-68f41c04af0c',
         'listeners': [
             {'id': '5bd3f2bd-80ba-43f4-849e-679bf19641e2'}],
         'name': '',
         'network_id': 'ff23a8bd-7dbf-43f2-bba7-1cf564c07b00',
         'operating_status': 'ONLINE',
         'pools': [{'id': '67a89f9a-b172-4e75-b583-46f09451face'}],
         'provider': 'f5networks',
         'provisioning_status': 'ACTIVE',
         'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
         'vip_address': '172.16.101.2',
         'vip_port':
             {'admin_state_up': True,
              'allowed_address_pairs': [],
              'binding:host_id':
                  'host-164.int.lineratesystems.com:'
                  '55630282-333b-5d3c-82f4-63054317df58',
              'binding:profile': {},
              'binding:vif_details': {},
              'binding:vif_type': 'binding_failed',
              'binding:vnic_type': 'normal',
              'created_at': '2016-10-27T16:57:53',
              'description': None,
              'device_id': 'ca979235-4310-5ed8-b679-2222f37f861c',
              'device_owner': 'F5:lbaasv2',
              'dns_name': None,
              'extra_dhcp_opts': [],
              'fixed_ips':
                  [{'ip_address': '172.16.101.2',
                    'subnet_id': '5a6e3943-52bd-4d59-9f9c-13e15617701b'}],
              'id': '3a44815c-c45c-47ac-9f0a-33e98a627076',
              'mac_address': 'fa:16:3e:82:2a:db',
              'name': 'loadbalancer-c22375f7-82c3-42b7-9590-68f41c04af0c',
              'network_id': 'ff23a8bd-7dbf-43f2-bba7-1cf564c07b00',
              'security_groups': [
                  '8a1b7afb-2ea6-44b7-84f4-4ff20a4ebd91'],
              'status': 'DOWN',
              'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
              'updated_at': '2016-10-27T16:57:55'},
         'vip_port_id': '3a44815c-c45c-47ac-9f0a-33e98a627076',
         'vip_subnet_id': '5a6e3943-52bd-4d59-9f9c-13e15617701b',
         'vxlan_vteps': ['201.0.160.1',
                         '201.0.162.1',
                         '201.0.165.1',
                         '201.0.159.10']},
    'members': [{'address': '10.2.2.3',
                 'admin_state_up': True,
                 'id': 'a8e2063b-ebec-4597-9d75-3393817bd6aa',
                 'name': '',
                 'network_id': 'ff23a8bd-7dbf-43f2-bba7-1cf564c07b00',
                 'operating_status': 'ONLINE',
                 'pool_id': '67a89f9a-b172-4e75-b583-46f09451face',
                 'protocol_port': 8080,
                 'provisioning_status': 'ACTIVE',
                 'subnet_id': '5a6e3943-52bd-4d59-9f9c-13e15617701b',
                 'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
                 'weight': 1}],
    'networks': {
        'ff23a8bd-7dbf-43f2-bba7-1cf564c07b00':
            {'admin_state_up': True,
             'availability_zone_hints': [],
             'availability_zones': ['nova'],
             'created_at': '2016-10-27T16:57:52',
             'description': '',
             'id': 'ff23a8bd-7dbf-43f2-bba7-1cf564c07b00',
             'ipv4_address_scope': None,
             'ipv6_address_scope': None,
             'mt': 1450,
             'name': 'network-1628266283',
             'provider:network_type': 'vxlan',
             'provider:physical_network': None,
             'provider:segmentation_id': 22,
             'router:external': False,
             'shared': False,
             'status': 'ACTIVE',
             'subnets': [
                 '5a6e3943-52bd-4d59-9f9c-13e15617701b'],
             'tags': [],
             'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
             'updated_at': '2016-10-27T16:57:52',
             'vlan_transparent': None}},
    'pools': [{'admin_state_up': True,
               'description': '',
               'healthmonitor_id': '3bdb3ba7-a027-4267-9837-8f402bfa6ce8',
               'id': '67a89f9a-b172-4e75-b583-46f09451face',
               'l7_policies': [],
               'lb_algorithm': 'ROUND_ROBIN',
               'listener_id': '5bd3f2bd-80ba-43f4-849e-679bf19641e2',
               'listeners': [{'id': '5bd3f2bd-80ba-43f4-849e-679bf19641e2'}],
               'loadbalancer_id': 'c22375f7-82c3-42b7-9590-68f41c04af0c',
               'members': [{'id': 'a8e2063b-ebec-4597-9d75-3393817bd6aa'}],
               'name': '',
               'operating_status': 'ONLINE',
               'protocol': 'HTTP',
               'provisioning_status': 'ACTIVE',
               'sessionpersistence': None,
               'tenant_id': 'a494c1bc65c346bc86319315d4f138ba'}],
    'subnets': {'5a6e3943-52bd-4d59-9f9c-13e15617701b': {
        'allocation_pools': [{'end': '172.16.101.14',
                              'start': '172.16.101.2'}],
        'cidr': '172.16.101.0/28',
        'created_at': '2016-10-27T16:57:52',
        'description': '',
        'dns_nameservers': [],
        'enable_dhcp': True,
        'gateway_ip': '172.16.101.1',
        'host_routes': [],
        'id': '5a6e3943-52bd-4d59-9f9c-13e15617701b',
        'ip_version': 4,
        'ipv6_address_mode': None,
        'ipv6_ra_mode': None,
        'name': '',
        'network_id': 'ff23a8bd-7dbf-43f2-bba7-1cf564c07b00',
        'shared': False,
        'subnetpool_id': None,
        'tenant_id': 'a494c1bc65c346bc86319315d4f138ba',
        'updated_at': '2016-10-27T16:57:52'}}}


@pytest.fixture()
def service_object():
    return LbaasServiceObject(service_def)


class TestLbaasService(object):
    def test_get_loadbalancer(self, service_object):
        lb = service_object.get_loadbalancer()
        assert lb['id'] == service_def['loadbalancer']['id']

    def test_get_l7rule(self, service_object):
        l7rule_id = 'fe96d470-f7f5-4ea8-adcd-25e7e2691a9a'
        l7rule = service_object.get_l7rule(l7rule_id)
        assert l7rule

    def test_get_l7rules(self, service_object):
        rules = service_object.get_l7rules()
        assert len(rules) == 1

    def test_get_l7policy(self, service_object):
        l7policy_id = 'd23fed66-0927-4de4-ae9d-da9799c42269'
        l7policy = service_object.get_l7policy(l7policy_id)
        assert l7policy

    def test_get_l7policies(self, service_object):
        policies = service_object.get_l7policies()
        assert len(policies) == 1

    def test_get_listener(self, service_object):
        listener_id = '5bd3f2bd-80ba-43f4-849e-679bf19641e2'
        listener = service_object.get_listener(listener_id)
        assert listener

    def test_get_listeners(self, service_object):
        listeners = service_object.get_listeners()
        assert len(listeners) == 1

    def test_get_pool(self, service_object):
        pool_id = '67a89f9a-b172-4e75-b583-46f09451face'
        pool = service_object.get_pool(pool_id)
        assert pool

    def test_get_pools(self, service_object):
        pools = service_object.get_pools()
        assert len(pools) == 1

    def test_get_member(self, service_object):
        member_id = 'a8e2063b-ebec-4597-9d75-3393817bd6aa'
        member = service_object.get_member(member_id)
        assert member

    def test_get_members(self, service_object):
        members = service_object.get_members()
        assert len(members) == 1

    def test_get_invalid_id(self, service_object):
        pool = service_object.get('pools', 'abc')
        assert pool is None

    def test_get_invalid_type(self, service_object):
        pool = service_object.get('abc',
                                  '67a89f9a-b172-4e75-b583-46f09451face')
        assert pool is None
