# coding=utf-8
# Copyright 2017 F5 Networks Inc.
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
def network_service(rds_cache):
    conf = mock.MagicMock()
    conf.vlan_binding_driver = None
    driver = mock.MagicMock()
    driver.conf = conf
    service = NetworkServiceBuilder(False, conf, driver)

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
        with pytest.raises(f5_ex.InvalidNetworkType):
            network['provider:network_type'] = ''
            network_service.get_route_domain_from_cache(network)

        # invalid segmentation ID
        with pytest.raises(f5_ex.InvalidNetworkType):
            network['provider:network_type'] = 'vlan'
            network['provider:segmentation_id'] = ''
            network_service.get_route_domain_from_cache(network)

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
