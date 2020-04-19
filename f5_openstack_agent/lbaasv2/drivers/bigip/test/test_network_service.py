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

from collections import namedtuple
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.network_service import \
    NetworkServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter

import mock
import netaddr
import pytest


@pytest.fixture
def rds_cache():
    return {
        '361ce86e845d43ad808cfe9a4c95cbfb': {},
        'cf705431f2a944c28ba1f03cce26d5f6': {
            1: {
                'vlan-604': {
                    'subnets': {
                        'ce48687c-11f3-40bf-a6fb-060547acf0d7': {
                            'cidr': netaddr.IPNetwork('172.32.252.0/24')
                        }
                    }
                }
            }
        },
        'f2a944c28b5d43ad808cc28ba1f03cce': {
            1: {
                'vlan-606': {
                    'subnets': {
                        '1189a88f-0fe7-4d0e-8549-b557d7f7e98b': {
                            'cidr': netaddr.IPNetwork('172.32.254.0/24')
                        },
                        'ce48687c-11f3-40bf-a6fb-060547acf0d7': {
                            'cidr': netaddr.IPNetwork('172.32.254.0/24')
                        }
                    }
                }
            },
            2: {
                'vlan-608': {
                    'subnets': {
                        'ce48687c-11f3-40bf-a6fb-060547acf0d7': {
                            'cidr': netaddr.IPNetwork('172.32.253.0/24')
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def network():
    return {
        'provider:physical_network': 'physnet1',
        'ipv6_address_scope': None,
        'port_security_enabled': True,
        'mt': 1450,
        'id': '9b4cd0a9-188c-4b02-b195-33f7593cd8f5',
        'router:external': False,
        'availability_zon      e_hints': [],
        'availability_zones': ['nova'],
        'ipv4_address_scope': None,
        'shared': False,
        'provider:segmentation_id': 608,
        'status': 'ACTIVE',
        'subnets': ['1189a88f-0fe7-4d0e-8549-b557d7f7e98b'],
        'description': '',
        'tags': [],
        'updated_at': '2017-05-24T07:42:09',
        'route_domain_id': 1,
        'qos_policy_id': None,
        'name': '4c9961bf-ba29-41ac-81c2-e222eeaaa543',
        'admin_state_up': True,
        'tenant_id': '361ce86e845d43ad808cfe9a4c95cbfb',
        'created_at': '2017-05-24T07:42:09',
        'provider:network_type': 'vlan',
        'vlan_transparent': None
    }


@pytest.fixture
def subnet():
    return {'description': '',
            'enable_dhcp': True,
            'network_id': '9b4cd0a9-188c-4b02-b195-33f7593cd8f5',
            'tenant_id': 'f2a944c28b5d43ad808cc28ba1f03cce',
            'created_at': '2017-05-24T07:42:09',
            'dns_nameservers': [],
            'updated_at': '2017-05-24T07:42:11',
            'gateway_ip': '172.32.254.1',
            'ipv6_ra_mode': None,
            'allocation_pools': [{'start': '172.32.254.2',
                                  'end': '172.32.254.254'}],
            'host_routes': [],
            'shared': False,
            'ip_version': 4,
            'ipv6_address_mode': None,
            'cidr': '172.32.254.0/24',
            'id': '1189a88f-0fe7-4d0e-8549-b557d7f7e98b',
            'subnetpool_id': None,
            'name': 'subnet-new'}


@pytest.fixture
def service():
    return {
        'subnets': {
            '2c2deedd-9a4e-47c6-aeb3-148c6042707d': {
                'name': 'sub1',
                'enable_dhcp': True,
                'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
                'tenant_id': 'b95f6e974471433eb9f482303a5da291',
                'dns_nameservers': [],
                'gateway_ip': '10.2.5.1',
                'ipv6_ra_mode': None,
                'allocation_pools': [{
                    'start': '10.2.5.2',
                    'end': '10.2.5.254'
                }],
                'host_routes': [],
                'shared': True,
                'ip_version': 4,
                'ipv6_address_mode': None,
                'cidr': '10.2.5.0/24',
                'id': '2c2deedd-9a4e-47c6-aeb3-148c6042707d',
                'subnetpool_id': None
            },
            '30715508-bdde-4aed-90d9-7aa86adb2214': {
                'name': 'mgmt_v4_subnet',
                'enable_dhcp': True,
                'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
                'tenant_id': 'b95f6e974471433eb9f482303a5da291',
                'dns_nameservers': ['10.190.20.5', '10.190.0.20'],
                'gateway_ip': '10.2.4.1',
                'ipv6_ra_mode': None,
                'allocation_pools': [{
                    'start': '10.2.4.100',
                    'end': '10.2.4.150'
                }],
                'host_routes': [],
                'shared': True,
                'ip_version': 4,
                'ipv6_address_mode': None,
                'cidr': '10.2.4.0/24',
                'id': '30715508-bdde-4aed-90d9-7aa86adb2214',
                'subnetpool_id': None
            },
            '237dc7ae-d56d-4c64-a4c3-ea984ff6de0b': {
                'name': 'sub2',
                'enable_dhcp': True,
                'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
                'tenant_id': 'b95f6e974471433eb9f482303a5da291',
                'dns_nameservers': [],
                'gateway_ip': '10.2.6.1',
                'ipv6_ra_mode': None,
                'allocation_pools': [{
                    'start': '10.2.6.2',
                    'end': '10.2.6.254'
                }],
                'host_routes': [],
                'shared': True,
                'ip_version': 4,
                'ipv6_address_mode': None,
                'cidr': '10.2.6.0/24',
                'id': '237dc7ae-d56d-4c64-a4c3-ea984ff6de0b',
                'subnetpool_id': None
            }
        },
        'listeners': [{
            'protocol_port': 80,
            'protocol': 'HTTP',
            'description': '',
            'default_tls_container_id': None,
            'tenant_id': 'b95f6e974471433eb9f482303a5da291',
            'admin_state_up': True,
            'connection_limit': -1,
            'id': '6aa36094-5ecd-422c-a3d3-723476ef6ab2',
            'sni_containers': [],
            'provisioning_status': 'ACTIVE',
            'default_pool_id': 'b0fa36ef-c125-460b-b94c-174139915af7',
            'loadbalancer_id': 'b0ac477a-a334-4bc9-8071-13692eee2d4e',
            'operating_status': 'ONLINE',
            'name': 'l1'
        }],
        'healthmonitors': [],
        'members': [{
            'weight': 1,
            'admin_state_up': True,
            'subnet_id': '2c2deedd-9a4e-47c6-aeb3-148c6042707d',
            'tenant_id': 'b95f6e974471433eb9f482303a5da291',
            'provisioning_status': 'ACTIVE',
            'pool_id': 'b0fa36ef-c125-460b-b94c-174139915af7',
            'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
            'address': '10.2.5.10',
            'protocol_port': 8080,
            'id': 'dd1e0ccc-6bc9-4c8e-abe5-f5789f0a3e70',
            'operating_status': 'NO_MONITOR'
        }, {
            'weight': 1,
            'admin_state_up': True,
            'subnet_id': '237dc7ae-d56d-4c64-a4c3-ea984ff6de0b',
            'tenant_id': 'b95f6e974471433eb9f482303a5da291',
            'provisioning_status': 'PENDING_CREATE',
            'pool_id': 'b0fa36ef-c125-460b-b94c-174139915af7',
            'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
            'address': '10.2.6.10',
            'protocol_port': 8080,
            'id': 'e4bbd6bd-d4e0-4737-8c31-02cd1935f08c',
            'operating_status': 'OFFLINE'
        }],
        'pools': [{
            'lb_algorithm': 'ROUND_ROBIN',
            'protocol': 'HTTP',
            'description': '',
            'provisioning_status': 'ACTIVE',
            'tenant_id': 'b95f6e974471433eb9f482303a5da291',
            'admin_state_up': True,
            'session_persistence': None,
            'healthmonitor_id': None,
            'listeners': [{
                'id': '6aa36094-5ecd-422c-a3d3-723476ef6ab2'
            }],
            'members': [{
                'id': 'dd1e0ccc-6bc9-4c8e-abe5-f5789f0a3e70'
            }, {
                'id': 'e4bbd6bd-d4e0-4737-8c31-02cd1935f08c'
            }],
            'sessionpersistence': None,
            'id': 'b0fa36ef-c125-460b-b94c-174139915af7',
            'operating_status': 'ONLINE',
            'name': 'p1'
        }],
        'networks': {
            '8f398b94-635e-4a58-9f70-bf4d93f206a6': {
                'status': 'ACTIVE',
                'subnets': ['2c2deedd-9a4e-47c6-aeb3-148c6042707d',
                            '237dc7ae-d56d-4c64-a4c3-ea984ff6de0b',
                            '30715508-bdde-4aed-90d9-7aa86adb2214'],
                'name': 'tempest-mgmt-network',
                'provider:physical_network': None,
                'admin_state_up': True,
                'tenant_id': 'b95f6e974471433eb9f482303a5da291',
                'mtu': 0,
                'router:external': False,
                'vlan_transparent': None,
                'shared': True,
                'provider:network_type': 'vxlan',
                'id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
                'provider:segmentation_id': 22
            }
        },
        'loadbalancer': {
            'vxlan_vteps': ['201.0.156.1', '201.0.160.1', '201.0.157.10',
                            '201.0.159.1'],
            'name': 'lb1',
            'provisioning_status': 'PENDING_UPDATE',
            'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
            'tenant_id': 'b95f6e974471433eb9f482303a5da291',
            'admin_state_up': True,
            'provider': 'f5networks',
            'id': 'b0ac477a-a334-4bc9-8071-13692eee2d4e',
            'gre_vteps': [],
            'listeners': [{
                'id': '6aa36094-5ecd-422c-a3d3-723476ef6ab2'
            }],
            'vip_port_id': '56eff2ad-ede0-49fd-bf37-aa34c4f76e6e',
            'vip_address': '10.2.4.104',
            'vip_subnet_id': '30715508-bdde-4aed-90d9-7aa86adb2214',
            'vip_port': {
                'status': 'DOWN',
                'binding:host_id':
                    'host-155.int.lineratesystems.com:'
                    'e4d04069-3d8b-555c-a154-3e2486f7c92e',
                'name': 'loadbalancer-b0ac477a-a334-4bc9-8071-13692eee2d4e',
                'allowed_address_pairs': [],
                'admin_state_up': True,
                'network_id': '8f398b94-635e-4a58-9f70-bf4d93f206a6',
                'dns_name': '',
                'extra_dhcp_opts': [],
                'mac_address': 'fa:16:3e:8d:ca:54',
                'dns_assignment': [{
                    'hostname': 'host-10-2-4-104',
                    'ip_address': '10.2.4.104',
                    'fqdn': 'host-10-2-4-104.openstacklocal.'
                }],
                'binding:vif_details': {},
                'binding:vif_type': 'binding_failed',
                'device_owner': 'F5:lbaasv2',
                'tenant_id': 'b95f6e974471433eb9f482303a5da291',
                'binding:profile': {},
                'binding:vnic_type': 'normal',
                'fixed_ips': [{
                    'subnet_id': '30715508-bdde-4aed-90d9-7aa86adb2214',
                    'ip_address': '10.2.4.104'
                }],
                'id': '56eff2ad-ede0-49fd-bf37-aa34c4f76e6e',
                'security_groups': ['b1d95c23-bdb8-4b5f-99c5-83ea4bdd08ee'],
                'device_id': '1d69cdd3-e560-530a-b615-15bb7a18ba68'
            },
            'operating_status': 'ONLINE',
            'description': ''
        }
    }


@pytest.fixture
def network_service(rds_cache):
    conf = mock.MagicMock()
    conf.vlan_binding_driver = None
    driver = mock.MagicMock()
    driver.conf = conf
    service = NetworkServiceBuilder(False, conf, driver)
    service.service_adapter = ServiceModelAdapter(conf)

    # add a 'real' RD cache
    service.rds_cache = rds_cache

    # mock NetworkHelper.get_route_domain()
    rd = namedtuple('RouteDomain', 'id')
    rd.id = 1234
    service.network_helper = mock.MagicMock()
    service.network_helper.get_route_domain = mock.MagicMock(return_value=rd)

    return service


class TestNetworkServiceBuilder(object):
    """Test assign route domain in NetworkServiceBuilder class"""

    def test_get_neutron_net_short_name(self, network_service, network):
        """Test function that creates network name.

        """
        # valid name
        net_short_name = network_service.get_neutron_net_short_name(network)
        assert net_short_name == 'vlan-608'

        # invalid network type
        with pytest.raises(f5_ex.InvalidNetworkType) as excinfo:
            network['provider:network_type'] = ''
            network_service.get_route_domain_from_cache(network)
            assert 'provider:network_type' in str(excinfo.value)

        # invalid segmentation ID
        with pytest.raises(f5_ex.InvalidNetworkType) as excinfo:
            network['provider:network_type'] = 'vlan'
            network['provider:segmentation_id'] = ''
            network_service.get_route_domain_from_cache(network)
            assert 'provider:network_type - vlan' in str(excinfo.value)

    def test_get_route_domain_from_cache(self, network_service, network):
        # valid cache entries
        rd = network_service.get_route_domain_from_cache(network)
        assert rd == 2

        network['provider:segmentation_id'] = 604
        rd = network_service.get_route_domain_from_cache(network)
        assert rd == 1

        # vlan not in cache
        with pytest.raises(f5_ex.RouteDomainCacheMiss) as excinfo:
            network['provider:segmentation_id'] = 600
            network_service.get_route_domain_from_cache(network)
        assert 'vlan-600' in str(excinfo.value)

        # empty cache
        with pytest.raises(f5_ex.RouteDomainCacheMiss) as excinfo:
            network['provider:segmentation_id'] = 606
            network['provider:network_type'] = 'vlan'
            network_service.rds_cache = {}
            network_service.get_route_domain_from_cache(network)
        assert 'vlan-606' in str(excinfo.value)

        # invalid network data
        with pytest.raises(f5_ex.InvalidNetworkType):
            network['provider:segmentation_id'] = 604
            network['provider:network_type'] = ''
            network_service.get_route_domain_from_cache(network)

    def test_assign_route_domain(self, network_service, network, subnet):
        """Test assign_route_domain()

        This is not an exhaustive test, but it is intended to cover
        the major sections of assign_route_domain(), including:
            shared network configuration
            vlan in route domain cache
            vlan not in cache, namespace = 1 in agent config
            vlan not in cache, namespace > 1 in agent config
        """
        tenant_id = 'f2a944c28b5d43ad808cc28ba1f03cce'

        network_service.conf.f5_common_networks = False

        # shared (common) network always get RD 0
        network['shared'] = True
        network_service.assign_route_domain(tenant_id, network, subnet)
        assert network['route_domain_id'] == 0

        # valid cache entry
        network['shared'] = False
        network_service.assign_route_domain(tenant_id, network, subnet)
        assert network['route_domain_id'] == 2

        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'network_service.LOG') as mock_log:
            # no cache entry, single namespace
            network_service.conf.max_namespaces_per_tenant = 1
            network['provider:segmentation_id'] = 600
            network_service.assign_route_domain(tenant_id, network, subnet)
            assert network['route_domain_id'] == 1234
            assert mock.call('No route domain cache entry for vlan-600') in \
                mock_log.debug.call_args_list
            assert mock.call('max namespaces: 1') in \
                mock_log.debug.call_args_list

            # no cache entry, multiple namespaces
            network_service.conf.max_namespaces_per_tenant = 3
            network_service.assign_route_domain(tenant_id, network, subnet)
            assert network['route_domain_id'] == 2
            assert mock.call('max namespaces: 3') in \
                mock_log.debug.call_args_list

        # invalid network data
        with pytest.raises(f5_ex.InvalidNetworkType):
            network['provider:segmentation_id'] = 604
            network['provider:network_type'] = ''
            network_service.assign_route_domain(tenant_id, network, subnet)

    def test_get_subnets_to_assure(self, network_service, service):
        net_id = '8f398b94-635e-4a58-9f70-bf4d93f206a6'

        # expect three subnets: vip, first member, second member
        subnets = network_service._get_subnets_to_assure(service)
        assert len(subnets) == 3
        self._verify_assure_item('mgmt_v4_subnet', subnets, net_id, False)
        self._verify_assure_item('sub1', subnets, net_id, True)
        self._verify_assure_item('sub2', subnets, net_id, True)

        # expect only member subnets, not vip
        service['loadbalancer']['provisioning_status'] = 'PENDING_DELETE'
        subnets = network_service._get_subnets_to_assure(service)
        assert len(subnets) == 2
        self._verify_assure_item('sub1', subnets, net_id, True)
        self._verify_assure_item('sub2', subnets, net_id, True)

        # back to three subnets
        service['loadbalancer']['provisioning_status'] = 'ACTIVE'
        subnets = network_service._get_subnets_to_assure(service)
        assert len(subnets) == 3
        self._verify_assure_item('mgmt_v4_subnet', subnets, net_id, False)
        self._verify_assure_item('sub1', subnets, net_id, True)
        self._verify_assure_item('sub2', subnets, net_id, True)

        # expect vip and first member subnet
        service['members'].pop()
        subnets = network_service._get_subnets_to_assure(service)
        assert len(subnets) == 2
        self._verify_assure_item('mgmt_v4_subnet', subnets, net_id, False)
        self._verify_assure_item('sub1', subnets, net_id, True)

        # expect vip only
        service['members'].pop()
        subnets = network_service._get_subnets_to_assure(service)
        assert len(subnets) == 1
        self._verify_assure_item('mgmt_v4_subnet', subnets, net_id, False)

    def _verify_assure_item(self, name, subnets, net_id, is_member):
        item = self._get_assure_item(name, subnets)
        assert item
        assert item['subnet']['network_id'] == net_id
        assert item['network']['id'] == net_id
        assert item['is_for_member'] == is_member

    def _get_assure_item(self, name, items):
        try:
            return next(
                item for item in items if item['subnet']['name'] == name)
        except StopIteration:
            return None
