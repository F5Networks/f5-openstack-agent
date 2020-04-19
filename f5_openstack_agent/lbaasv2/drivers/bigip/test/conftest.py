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

import copy
import os
import pytest
import sys
import uuid

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2


class TestingWithServiceConstructor(object):
    """An object class meant for the use of constructing service objects

    This object class is meant to assist tests in orchestrating the appropraite
    steps to create a unique service object.  From there, the tests themselves
    can perform additional operations to make the service object what they
    need.

    MockBuilder classes will use this method upon occasion, but it should not
    be inherited or used directly by tester, but can be owned by for fixture
    de-referencing.  For an example of this, please see:
    test_agent_manager.py::TestAgentManager::test_fcwb_purge_orphaned_listeners
    """
    defaultservice = \
        dict(listeners=[], loadbalancer={}, pools=[], networks={}, subnets={},
             healthmonitors=[], members=[], l7policies=[], l7policy_rules=[])

    @staticmethod
    @pytest.fixture
    def new_id(*args):
        # this may or may not be called by an instantiated element... mind
        # blown...
        return str(uuid.uuid4())

    @staticmethod
    @pytest.fixture
    def esd():
        # Generate a esd mocked item that is pretty lame until more
        # intelligence is needed.
        return dict(lbaas_stcp='lbaas_stcp', lbaas_ctcp='lbaas_ctcp',
                    lbaas_cssl_profile='lbaas_cssl_profile',
                    lbaas_persist='lbaas_persist',
                    lbaas_fallback_persist='lbaas_fallback_persist',
                    lbaas_irule=['rule1', 'rule2'],
                    lbaas_policy=['policy1', 'policy2'],
                    lbaas_sssl_profile='lbaas_sssl_profile')

    @classmethod
    @pytest.fixture
    def service_with_network(cls, new_id):
        # service = cls.defaultservice.copy()
        service = copy.deepcopy(cls.defaultservice)
        new_network = dict(id=new_id, name='network', mtu=0, shared=False,
                           status='ACTIVE', subnets=[], tenant_id=cls.new_id(),
                           vlan_transparent=None)
        service['networks'][new_id] = new_network
        return service

    @classmethod
    def new_service_with_network(cls):
        return cls.service_with_network(cls.new_id())

    @classmethod
    @pytest.fixture
    def service_with_subnet(cls, new_id, service_with_network):
        network_id = service_with_network['networks'].keys()[0]
        network = service_with_network['networks'][network_id]
        tenant_id = network['tenant_id']
        allocation_pools = [dict(start='10.22.22.2', end='10.22.22.48')]
        dns_servers = ['10.22.22.2']
        host_routes = []
        new_subnet = \
            dict(allocation_pools=allocation_pools, tenant_id=tenant_id,
                 dns_servers=dns_servers, host_routes=host_routes,
                 cidr='10.22.22.0/22', gateway='10.22.22.1', id=cls.new_id(),
                 ip_version=4, ipv6_address_mode=None, ipv6_ra_mode=None,
                 enable_dhcp=True)
        network['subnets'].append(new_subnet)
        service_with_network['subnets'][cls.new_id()] = new_subnet
        return service_with_network

    @classmethod
    def new_service_with_subnet(cls):
        return \
            cls.service_with_subnet(
                cls.new_id(), cls.new_service_with_network())

    @classmethod
    @pytest.fixture
    def service_with_loadbalancer(cls, new_id, service_with_subnet):
        network_id = service_with_subnet['networks'].keys()[0]
        subnet_id = service_with_subnet['subnets'].keys()[0]
        network = service_with_subnet['networks'][network_id]
        tenant_id = network['tenant_id']
        vip_address = '10.22.22.4'
        device_id = cls.new_id()
        hostname = 'host-{}'.format(vip_address.replace('.', '-'))
        dns_assignment = \
            dict(fqdn="{}.openstacklocal.".format(hostname),
                 hostname=hostname, ip_address=vip_address)
        fixed_ips = [dict(ip_address=vip_address, subnet_id=subnet_id)]
        vip_port = \
            dict(admin_state_up=True, allowed_address_pairs=[],
                 device_id=device_id, divcie_owner='newutron:LOADBALANCERV2',
                 dns_assignment=dns_assignment, dns_name=None,
                 extra_dhcp_opts=[], id=cls.new_id(), network_id=network_id,
                 name='loadbalancer-'.format(new_id), security_groups=[],
                 mac_address='xx:xx:xx:xx:xx:xx', status='UP',
                 tenant_id=tenant_id, fixed_ips=fixed_ips)
        new_lb = \
            dict(admin_state_up=True, description='', gre_vteps=[],
                 id=new_id, listeners=[], name='lb1', network_id=network_id,
                 operating_status='OFFLINE', provider=None, vip_port=vip_port,
                 provisioning_status=constants_v2.F5_PENDING_CREATE,
                 vip_address=vip_address, dns_name=None,
                 dns_assignment=[dns_assignment],
                 tenant_id=tenant_id, vip_id=vip_port['id'],
                 vip_subnet_id=subnet_id, vxlan_vteps=[])
        service_with_subnet['loadbalancer'] = new_lb
        return service_with_subnet

    @classmethod
    def new_service_with_loadbalancer(cls):
        return \
            cls.service_with_loadbalancer(cls.new_id(),
                                          cls.new_service_with_subnet())

    @classmethod
    @pytest.fixture
    def service_with_listener(cls, new_id, service_with_loadbalancer):
        svc = service_with_loadbalancer
        lb = svc['loadbalancer']
        lb['listeners'].append(new_id)
        tenant_id = lb['tenant_id']
        lb_id = lb['id']
        lb['provisioning_status'] = constants_v2.F5_PENDING_UPDATE
        new_listener = \
            dict(admin_state_up=True, connection_limit=-1,
                 default_pool_id=None, default_tls_container_id=None,
                 description='', id=new_id, loadbalaner_id=lb_id,
                 name='l1', operating_status='OFFLINE', protocol='HTTP',
                 protocol_port=8080, sni_containers=[], tenant_id=tenant_id,
                 provisioning_status=constants_v2.F5_PENDING_CREATE)
        svc['listeners'].append(new_listener)
        return svc

    @classmethod
    def new_service_with_listener(cls):
        return \
            cls.service_with_listener(cls.new_id(),
                                      cls.new_service_with_loadbalancer())

    @classmethod
    @pytest.fixture
    def service_with_l7_policy(cls, new_id, service_with_listener):
        # update as needed for more intelligence...
        svc = service_with_listener
        li = svc['listeners'][0]
        li_id = li['id']
        tenant_id = li['tenant_id']
        li['l7_policies'] = [new_id]
        new_l7_policy = {
            "action": "REJECT", "admin_state_up": True, "description": "",
            "id": new_id, "listener_id": li_id, "name": "f5_ESD_ABSTRACT_ESD",
            "position": 1, "provisioning_status": "PENDING_CREATE",
            "redirect_pool_id": None, "redirect_url": None, "rules": [],
            "tenant_id": tenant_id}
        svc['l7_policies'] = [new_l7_policy]
        return svc

    @classmethod
    def new_service_with_l7_policy(cls):
        return cls.service_with_l7_policy(cls.new_id(),
                                          cls.new_service_with_listener())

    @classmethod
    @pytest.fixture
    def service_with_pool(cls, new_id, service_with_listener):
        # update as needed for more intelligence...
        svc = service_with_listener
        li = svc['listeners'][0]
        tenant_id = li['tenant_id']
        li['default_pool_id'] = new_id
        li['provisioning_status'] = constants_v2.F5_PENDING_UPDATE
        new_pool = {'id': new_id, 'listeners': [dict(id=li['id'])],
                    'provisioning_status': constants_v2.F5_PENDING_CREATE,
                    'tenant_id': tenant_id}
        svc['pools'].append(new_pool)
        return svc

    @classmethod
    def new_service_with_pool(cls):
        return cls.service_with_pool(cls.new_id(),
                                     cls.new_service_with_listener())

    @classmethod
    @pytest.fixture
    def service_with_health_monitor(cls, new_id, service_with_pool):
        pool_id = service_with_pool['pools'][0]['id']
        tenant_id = service_with_pool['loadbalancer']['tenant_id']
        service_with_pool['pools'][0]['healthmonitor_id'] = new_id
        new_monitor = dict(admin_state_up=True, delay=10, expected_codes=200,
                           http_method='GET', id=new_id, max_retries=5,
                           name='hm1', pool_id=pool_id, tenant_id=tenant_id,
                           timeout=5, type='HTTP', url_path='/')
        service_with_pool['healthmonitors'].append(new_monitor)
        return service_with_pool

    @classmethod
    def new_service_with_health_monitor(cls):
        return \
            cls.service_with_health_monitor(cls.new_id(),
                                            cls.new_service_with_pool())


@pytest.fixture
def pool_member_service():
    return {
        u'loadbalancer': {
            u'admin_state_up': True,
            u'description': u'',
            u'gre_vteps': [u'201.0.162.1', u'201.0.160.1', u'201.0.165.1'],
            u'id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
            u'listeners': [{u'id': u'e3af03f4-d3df-4c9b-b3dd-8002f133d5bf'}],
            u'name': u'',
            u'network_id': u'cdf1eb6d-9b17-424a-a054-778f3d3a5490',
            u'operating_status': u'ONLINE',
            u'pools': [{u'id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52'}],
            u'provider': u'f5networks',
            u'provisioning_status': u'ACTIVE',
            u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd',
            u'vip_address': u'172.16.101.3',
            u'vip_port': {
                u'admin_state_up': True,
                u'allowed_address_pairs': [],
                u'binding:host_id': u'host-164.int.lineratesystems.com:16ea1e',
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
        u'members': [
            {
                u'address': u'10.2.2.3',
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
                u'weight': 1},
            {
                u'address': u'10.2.2.7',
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
                u'weight': 10}],
        u'pool': {
            u'admin_state_up': True,
            u'description': u'',
            u'healthmonitor_id': u'70fed03a-efc4-460a-8a21',
            u'id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
            u'l7_policies': [],
            u'lb_algorithm': u'LEAST_CONNECTIONS',
            u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d59',
            u'name': u'',
            u'operating_status': u'ONLINE',
            u'protocol': u'HTTP',
            u'provisioning_status': u'ACTIVE',
            u'session_persistence': None,
            u'sessionpersistence': None,
            u'tenant_id': u'd9ed216f67f04a84bf8fd97c155855cd'}
        }


def check_for_relative_path(start, path_ending):
    starting = start.split('/')
    relative_path = list()
    for path in starting:
        relative_path.append(path)
        if os.path.isdir("{}{}".format('/'.join(relative_path), path_ending)):
            return relative_path
    raise AssertionError("Could not establish relative path from({})".format(
                         start))


@pytest.fixture
def get_relative_path():
    cwd = os.getcwd()
    expected_finishing_path = "/f5_openstack_agent/lbaasv2/drivers/bigip/test"
    try:
        relative_path = check_for_relative_path(cwd, expected_finishing_path)
    except AssertionError as Err:
        errors = [Err]
        for arg in sys.argv[1:]:
            if os.path.isdir(arg):
                try:
                    relative_path = \
                        check_for_relative_path(arg, expected_finishing_path)
                except AssertionError as Err:
                    errors.append(Err)
        if errors:
            assert AssertionError("Could not derive path ({})".format(errors))
    return '/'.join(relative_path)
