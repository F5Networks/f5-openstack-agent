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
from mock import patch
from requests import HTTPError

import f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder import \
    LBaaSBuilder


LOG = f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder.LOG


POLICY_DELETE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.delete_l7policy'
POLICY_BUILD_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.build_policy'
POLICY_CREATE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.create_l7policy'
VS_POOL_UPDATE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.listener_service' \
    '.ListenerServiceBuilder.update_listener_pool'

POOL_BLDR_PATH = 'f5_openstack_agent.lbaasv2.drivers.bigip.pool_service.' \
    'PoolServiceBuilder'


@pytest.fixture
def l7_listener_policy():

    import json
    import os

    lpm = (os.path.join(os.path.dirname(
        os.path.abspath(__file__)),
        './l7_listener_policy.json')
    )
    return json.load(open(lpm))


@pytest.fixture
def l7policy_and_rules():
    return {
        "healthmonitors": [],
        "l7policies": [
            {
                "action": "REDIRECT_TO_URL",
                "admin_state_up": True,
                "description": "",
                "id": "1d4590b8-c7e6-4e1b-bfa2-ec9b7d2d1905",
                "listener_id": "0768eb5c-fc16-49c6-ab4c-101d596ec1f6",
                "name": "",
                "position": 2,
                "provisioning_status": "ACTIVE",
                "redirect_pool_id": None,
                "redirect_url": "http://www.website.com:90",
                "rules": [
                    {
                        "id": "159f1a5e-04f6-473b-936f-0c03566d59f6"
                    }
                ],
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1"
            },
            {
                "action": "REJECT",
                "admin_state_up": True,
                "description": "",
                "id": "afdbfab4-de48-449c-86e8-7541ec9137bd",
                "listener_id": "0768eb5c-fc16-49c6-ab4c-101d596ec1f6",
                "name": "",
                "position": 1,
                "provisioning_status": "ACTIVE",
                "redirect_pool_id": None,
                "redirect_url": None,
                "rules": [
                    {
                        "id": "325df4eb-70fc-46f5-a885-a2cf961e3a19"
                    }
                ],
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1"
            }
        ],
        "l7policy_rules": [
            {
                "admin_state_up": True,
                "compare_type": "EQUAL_TO",
                "id": "159f1a5e-04f6-473b-936f-0c03566d59f6",
                "invert": False,
                "key": "X-Header",
                "policies": [
                    {
                        "id": "1d4590b8-c7e6-4e1b-bfa2-ec9b7d2d1905"
                    }
                ],
                "policy_id": "1d4590b8-c7e6-4e1b-bfa2-ec9b7d2d1905",
                "provisioning_status": "PENDING_CREATE",
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1",
                "type": "HEADER",
                "value": "ForwardThis"
            },
            {
                "admin_state_up": True,
                "compare_type": "EQUAL_TO",
                "id": "325df4eb-70fc-46f5-a885-a2cf961e3a19",
                "invert": False,
                "key": "X-Header",
                "policies": [
                    {
                        "id": "afdbfab4-de48-449c-86e8-7541ec9137bd"
                    }
                ],
                "policy_id": "afdbfab4-de48-449c-86e8-7541ec9137bd",
                "provisioning_status": "ACTIVE",
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1",
                "type": "HEADER",
                "value": "RejectThis"
            }
        ],
        "listeners": [
            {
                "admin_state_up": True,
                "connection_limit": -1,
                "default_pool_id": None,
                "default_tls_container_id": None,
                "description": "",
                "id": "0768eb5c-fc16-49c6-ab4c-101d596ec1f6",
                "l7_policies": [
                    {
                        "id": "afdbfab4-de48-449c-86e8-7541ec9137bd"
                    },
                    {
                        "id": "1d4590b8-c7e6-4e1b-bfa2-ec9b7d2d1905"
                    }
                ],
                "loadbalancer_id": "990ba002-6eb2-40b6-9c63-f364b28a630b",
                "name": "vs1",
                "operating_status": "ONLINE",
                "protocol": "HTTP",
                "protocol_port": 80,
                "provisioning_status": "ACTIVE",
                "sni_containers": [],
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1"
            }
        ],
        "loadbalancer": {
            "admin_state_up": True,
            "description": "",
            "gre_vteps": [],
            "id": "990ba002-6eb2-40b6-9c63-f364b28a630b",
            "listeners": [
                {
                    "id": "0768eb5c-fc16-49c6-ab4c-101d596ec1f6"
                }
            ],
            "name": "lb1",
            "network_id": "44a78cf5-eac9-4f72-ae0f-663fa6aa2ce0",
            "operating_status": "ONLINE",
            "pools": [],
            "provider": "f5networks",
            "provisioning_status": "ACTIVE",
            "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1",
            "vip_address": "192.168.101.3",
            "vip_port": {
                "admin_state_up": True,
                "allowed_address_pairs": [],
                "binding:host_id": "mitaka-stack",
                "binding:profile": {},
                "binding:vif_details": {},
                "binding:vif_type": "other",
                "binding:vnic_type": "baremetal",
                "created_at": "2017-11-23T01:14:37",
                "description": None,
                "device_id": "990ba002-6eb2-40b6-9c63-f364b28a630b",
                "device_owner": "F5:lbaasv2",
                "dns_name": None,
                "extra_dhcp_opts": [],
                "fixed_ips": [
                    {
                        "ip_address": "192.168.101.3",
                        "subnet_id": "8cc10931-7a60-433d-93d6-0ec1f61736ee"
                    }
                ],
                "id": "4fcad830-10f1-4e84-a2bc-db40917f9f99",
                "mac_address": "fa:16:3e:c3:d3:5c",
                "name": "loadbalancer-990ba002-6eb2-40b6-9c63-f364b28a630b",
                "network_id": "44a78cf5-eac9-4f72-ae0f-663fa6aa2ce0",
                "port_security_enabled": True,
                "security_groups": [
                    "99f64e53-4b85-4bcd-83da-0205570eaff6"
                ],
                "status": "DOWN",
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1",
                "updated_at": "2017-11-23T01:14:38"
            },
            "vip_port_id": "4fcad830-10f1-4e84-a2bc-db40917f9f99",
            "vip_subnet_id": "8cc10931-7a60-433d-93d6-0ec1f61736ee",
            "vxlan_vteps": [
                "10.1.0.147"
            ]
        },
        "members": [],
        "networks": {
            "44a78cf5-eac9-4f72-ae0f-663fa6aa2ce0": {
                "admin_state_up": True,
                "availability_zone_hints": [],
                "availability_zones": [
                    "nova"
                ],
                "created_at": "2017-11-23T01:13:47",
                "description": "",
                "id": "44a78cf5-eac9-4f72-ae0f-663fa6aa2ce0",
                "ipv4_address_scope": None,
                "ipv6_address_scope": None,
                "mtu": 1450,
                "name": "admin-net",
                "port_security_enabled": True,
                "provider:network_type": "vxlan",
                "provider:physical_network": None,
                "provider:segmentation_id": 1032,
                "router:external": False,
                "shared": False,
                "status": "ACTIVE",
                "subnets": [
                    "8cc10931-7a60-433d-93d6-0ec1f61736ee"
                ],
                "tags": [],
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1",
                "updated_at": "2017-11-23T01:13:47",
                "vlan_transparent": None
            }
        },
        "pools": [],
        "subnets": {
            "8cc10931-7a60-433d-93d6-0ec1f61736ee": {
                "allocation_pools": [
                    {
                        "end": "192.168.101.254",
                        "start": "192.168.101.2"
                    }
                ],
                "cidr": "192.168.101.0/24",
                "created_at": "2017-11-23T01:14:12",
                "description": "",
                "dns_nameservers": [],
                "enable_dhcp": True,
                "gateway_ip": "192.168.101.1",
                "host_routes": [],
                "id": "8cc10931-7a60-433d-93d6-0ec1f61736ee",
                "ip_version": 4,
                "ipv6_address_mode": None,
                "ipv6_ra_mode": None,
                "name": "admin-subnet",
                "network_id": "44a78cf5-eac9-4f72-ae0f-663fa6aa2ce0",
                "shared": False,
                "subnetpool_id": None,
                "tenant_id": "bb6b38d7879a47b8ae9562b241bab1f1",
                "updated_at": "2017-11-23T01:14:12"
            }
        }
    }


@pytest.fixture
def service():
    return {
        u"listeners": [{
            u"admin_state_up": True,
            u"connection_limit": -1,
            u"default_pool_id": "2dbca6cd-30d8-4013-9c9a-df0850fabf52",
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
        u"healthmonitors": [{
            u"admin_state_up": True,
            u"id": u"5108c2fe-29bd-4e5b-94de-aaaaaaaaa",
            u"provisioning_status": u"ACTIVE",
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
                'vlan_transparent': None}
        },
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


@pytest.fixture
def l7policy_create_service():
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
            u'pools': [],
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
        u'l7policies': [
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 2,
                u'provisioning_status': u'PENDING_CREATE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'},
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'8935a899-706d-46d6-8376-51f013431533',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 1,
                u'provisioning_status': u'ACTIVE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'}],
        u'l7policy_rules': [],
        u'listeners': [
            {
                u'admin_state_up': True,
                u'connection_limit': -1,
                u'default_pool_id': None,
                u'default_tls_container_id': None,
                u'description': u'',
                u'id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'l7_policies': [
                    {
                        u'id': u'8935a899-706d-46d6-8376-51f013431533'},
                    {
                        u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7'}],
                u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
                u'name': u'vs1',
                u'operating_status': 'ONLINE',
                u'protocol': u'HTTP',
                u'protocol_port': 80,
                u'provisioning_status': u'ACTIVE',
                'snat_pool_name': u'Project_5197d6a284044c72b63f2fe6ae6edc21',
                u'sni_containers': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                'use_snat': True}],
        u'members': [],
        u'pools': [],
    }


@pytest.fixture
def l7policy_delete_service():
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
            u'pools': [],
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
        u'l7policies': [
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 2,
                u'provisioning_status': u'PENDING_DELETE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'},
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'8935a899-706d-46d6-8376-51f013431533',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 1,
                u'provisioning_status': u'ACTIVE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'}],
        u'l7policy_rules': [],
        u'listeners': [
            {
                u'admin_state_up': True,
                u'connection_limit': -1,
                u'default_pool_id': None,
                u'default_tls_container_id': None,
                u'description': u'',
                u'id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'l7_policies': [
                    {
                        u'id': u'8935a899-706d-46d6-8376-51f013431533'},
                    {
                        u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7'}],
                u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
                u'name': u'vs1',
                u'operating_status': 'ONLINE',
                u'protocol': u'HTTP',
                u'protocol_port': 80,
                u'provisioning_status': u'ACTIVE',
                'snat_pool_name': u'Project_5197d6a284044c72b63f2fe6ae6edc21',
                u'sni_containers': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                'use_snat': True}],
        u'members': [],
        u'pools': [],
    }


@pytest.fixture
def l7rule_create_service():
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
            u'pools': [],
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
            u'vxlan_vteps': []
        },
        u'l7policies': [
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 2,
                u'provisioning_status': u'ACTIVE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [{u'id': u'40e06ae9-3297-435d-be23-f3f6ff465e22'}],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'},
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'8935a899-706d-46d6-8376-51f013431533',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 1,
                u'provisioning_status': u'ACTIVE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'
            }],
        u'l7policy_rules': [
            {
                u'admin_state_up': True,
                u'compare_type': u'EQUAL_TO',
                u'id': u'40e06ae9-3297-435d-be23-f3f6ff465e22',
                u'invert': False,
                u'key': None,
                u'policies': [
                    {u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7'}],
                u'policy_id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7',
                u'provisioning_status': u'PENDING_CREATE',
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                u'type': u'FILE_TYPE',
                u'value': u'txt'}],
        u'listeners': [
            {
                u'admin_state_up': True,
                u'connection_limit': -1,
                u'default_pool_id': None,
                u'default_tls_container_id': None,
                u'description': u'',
                u'id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'l7_policies': [
                    {u'id': u'8935a899-706d-46d6-8376-51f013431533'},
                    {u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7'}],
                u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
                u'name': u'vs1',
                u'operating_status': 'ONLINE',
                u'protocol': u'HTTP',
                u'protocol_port': 80,
                u'provisioning_status': u'ACTIVE',
                'snat_pool_name': u'Project_5197d6a284044c72b63f2fe6ae6edc21',
                u'sni_containers': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                'use_snat': True}],
        u'members': [],
        u'pools': [],
    }


@pytest.fixture
def l7rule_delete_service():
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
            u'pools': [],
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
        u'l7policies': [
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 2,
                u'provisioning_status': u'ACTIVE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [
                    {u'id': u'40e06ae9-3297-435d-be23-f3f6ff465e22'}],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'},
            {
                u'action': u'REJECT',
                u'admin_state_up': True,
                u'description': u'',
                u'id': u'8935a899-706d-46d6-8376-51f013431533',
                u'listener_id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'name': u'',
                u'position': 1,
                u'provisioning_status': u'ACTIVE',
                u'redirect_pool_id': None,
                u'redirect_url': None,
                u'rules': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'}],
        u'l7policy_rules': [
            {
                u'admin_state_up': True,
                u'compare_type': u'EQUAL_TO',
                u'id': u'40e06ae9-3297-435d-be23-f3f6ff465e22',
                u'invert': False,
                u'key': None,
                u'policies': [
                    {u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7'}],
                u'policy_id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7',
                u'provisioning_status': u'PENDING_DELETE',
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                u'type': u'FILE_TYPE',
                u'value': u'txt'
            }],
        u'listeners': [
            {
                u'admin_state_up': True,
                u'connection_limit': -1,
                u'default_pool_id': None,
                u'default_tls_container_id': None,
                u'description': u'',
                u'id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'l7_policies': [
                    {u'id': u'8935a899-706d-46d6-8376-51f013431533'},
                    {u'id': u'23eea01d-5151-44fd-9ceb-6356bbb1ebb7'}],
                u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
                u'name': u'vs1',
                u'operating_status': 'ONLINE',
                u'protocol': u'HTTP',
                u'protocol_port': 80,
                u'provisioning_status': u'ACTIVE',
                'snat_pool_name': u'Project_5197d6a284044c72b63f2fe6ae6edc21',
                u'sni_containers': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                'use_snat': True}],
        u'members': [],
        u'pools': [],
    }


@pytest.fixture
def shared_pool_service():
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
            u'pools': [],
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
        u'l7policies': [],
        u'l7policy_rules': [],
        u'listeners': [
            {
                u'admin_state_up': True,
                u'connection_limit': -1,
                u'default_pool_id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
                u'default_tls_container_id': None,
                u'description': u'',
                u'id': u'7ddad6cc-887d-49aa-b970-5820471dc6e5',
                u'l7_policies': [],
                u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d593',
                u'name': u'vs1',
                u'operating_status': 'ONLINE',
                u'protocol': u'HTTP',
                u'protocol_port': 80,
                u'provisioning_status': u'ACTIVE',
                'snat_pool_name': u'Project_5197d6a284044c72b63f2fe6ae6edc21',
                u'sni_containers': [],
                u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21',
                'use_snat': True}],
        u'members': [],
        u'pools': [{u'admin_state_up': True,
                    u'description': u'',
                    u'healthmonitor_id': None,
                    u'id': u'2dbca6cd-30d8-4013-9c9a-df0850fabf52',
                    u'l7_policies': [],
                    u'lb_algorithm': u'ROUND_ROBIN',
                    u'loadbalancer_id': u'd5a0396e-e862-4cbf-8eb9-25c7fbc4d59',
                    u'name': u'',
                    u'operating_status': u'ONLINE',
                    u'protocol': u'HTTP',
                    u'provisioning_status': u'PENDING_CREATE',
                    u'session_persistence': None,
                    u'sessionpersistence': None,
                    u'tenant_id': u'5197d6a284044c72b63f2fe6ae6edc21'}],
    }


class MockHTTPError(HTTPError):
    def __init__(self, response_obj, message=''):
        self.response = response_obj
        self.message = message


class MockHTTPErrorResponse404(HTTPError):
    def __init__(self):
        self.status_code = 404


class MockHTTPErrorResponse409(HTTPError):
    def __init__(self):
        self.status_code = 409


class MockHTTPErrorResponse500(HTTPError):
    def __init__(self):
        self.status_code = 500


class TestLBaaSBuilderConstructor(object):
    @staticmethod
    @pytest.fixture
    @patch('f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder.'
           'LBaaSBuilder.__init__')
    def fully_mocked_target(init):
        init.return_value = None
        return LBaaSBuilder()

    @staticmethod
    @pytest.fixture
    def assure_mocked_target(fully_mocked_target):
        target = fully_mocked_target
        target.driver = Mock()
        target.service_adapter = Mock()
        target._update_subnet_hints = Mock()
        target._set_status_as_active = Mock()
        return target


class TestLbaasBuilder(TestLBaaSBuilderConstructor):
    f5_constants = constants_v2

    @pytest.fixture
    def create_self(self, request):
        request.addfinalizer(self.teardown)
        conf = Mock()
        driver = Mock()
        listener_service = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.listener_service.'
                'ListenerServiceBuilder')
        pool_service = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.pool_service.'
                'PoolServiceBuilder')
        l7service = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service.'
                'L7PolicyService')
        mock_listener = Mock()
        mock_pool = Mock()
        mock_l7service = Mock()
        self.log = Mock()
        f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder.LOG = self.log
        with patch(listener_service, mock_listener, create=True):
            with patch(pool_service, mock_pool, create=True):
                with patch(l7service, mock_l7service, create=True):
                    self.builder = LBaaSBuilder(conf, driver)
        self.listener_service = mock_listener
        self.pool_service = mock_pool
        self.l7service = mock_l7service

    def teardown(self):
        f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder.LOG = LOG

    def test_l7_policy_rule_create(
            self, l7policy_and_rules, l7_listener_policy):
        svc = l7policy_and_rules
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder.esd = Mock()
        builder.esd.is_esd.return_value = False
        bigips = [Mock()]
        builder.driver.get_config_bigips.return_value = bigips

        with mock.patch(POLICY_BUILD_PATH) as mock_policy_build:
            with mock.patch(POLICY_CREATE_PATH) as mock_policy_create:
                mock_policy_create.return_value = None
                mock_policy_build.return_value = l7_listener_policy

                builder._assure_l7policies_created(svc)

                mock_policy_create.assert_called_once_with(
                    l7_listener_policy['f5_policy'], bigips)
                assert mock_policy_build.called
                for policy in svc['l7policies']:
                    assert policy['provisioning_status'] == "ACTIVE"
                assert svc['loadbalancer']['provisioning_status'] == \
                    "ACTIVE"

    def test_l7_policy_rule_create_error(
            self, l7policy_and_rules, l7_listener_policy):
        svc = l7policy_and_rules
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder.esd = Mock()
        builder.esd.is_esd.return_value = False
        bigips = [Mock()]
        builder.driver.get_config_bigips.return_value = bigips

        with mock.patch(POLICY_BUILD_PATH) as mock_policy_build:
            with mock.patch(POLICY_CREATE_PATH) as mock_policy_create:
                mock_policy_create.return_value = "error"
                mock_policy_build.return_value = l7_listener_policy

                builder._assure_l7policies_created(svc)

                mock_policy_create.assert_called_once_with(
                    l7_listener_policy['f5_policy'], bigips)
                assert mock_policy_build.called
                for policy in svc['l7policies']:
                    assert policy['provisioning_status'] == "ERROR"
                assert svc['loadbalancer']['provisioning_status'] == \
                    "ERROR"

    def test_set_status_as_active(self, fully_mocked_target):
        preserved = ['PENDING_DELETE', 'ERROR']

        def new_svc_obj(status):
            state = getattr(constants_v2, status)
            return dict(provisioning_status=state, id=1)

        def is_state(svc_obj, state):
            state = getattr(constants_v2, state)
            return svc_obj['provisioning_status'] == state

        def preserve_status(target):
            for state in preserved:
                svc = new_svc_obj(state)
                target._set_status_as_active(svc, force=False)
                assert is_state(svc, state)

        def forced_through_preserved_status(target):
            for state in preserved:
                svc = new_svc_obj(state)
                target._set_status_as_active(svc, force=True)
                assert is_state(svc, 'ACTIVE')

        def other_status(target):
            svc = new_svc_obj('PENDING_UPDATE')
            target._set_status_as_active(svc)
            assert is_state(svc, 'ACTIVE')

        preserve_status(fully_mocked_target)
        forced_through_preserved_status(fully_mocked_target)
        other_status(fully_mocked_target)

    def test_assure_barebones_service(self, service, create_self):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'ACTIVE'
        svc['listeners'] = list()
        svc['pools'] = list()
        svc['healthmonitors'] = list()
        svc['members'] = list()
        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips
        builder.assure_service(service, None, Mock())

        assert loadbalancer['provisioning_status'] == 'ACTIVE'

    def test_assure_listeners_created_update(self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test UPDATE case
        target.listener_builder = Mock()
        target.listener_builder.create_listener.return_value = None

        expected_bigips = target.driver.get_config_bigips()
        listener['provisioning_status'] = \
            constants_v2.F5_PENDING_UPDATE
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_PENDING_UPDATE
        target._assure_listeners_created(service)

        expected_svc = dict(loadbalancer=service['loadbalancer'],
                            pools=service['pools'], l7policies=[],
                            l7policy_rules=[], listener=listener,
                            irules=[], networks=service['networks'])
        target.listener_builder.create_listener.assert_called_once_with(
            expected_svc, expected_bigips)
        assert listener['provisioning_status'] == "ACTIVE"
        assert loadbalancer['provisioning_status'] == "PENDING_UPDATE"

    def test_assure_listeners_created_create(self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test CREATE case
        target.listener_builder = Mock()
        target.listener_builder.create_listener.return_value = None

        expected_bigips = target.driver.get_config_bigips()
        listener['provisioning_status'] = \
            constants_v2.F5_PENDING_CREATE
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_PENDING_UPDATE
        target._assure_listeners_created(service)

        expected_svc = dict(loadbalancer=loadbalancer, pools=service['pools'],
                            l7policies=[], l7policy_rules=[], irules=[],
                            listener=listener, networks=service['networks'])
        target.listener_builder.create_listener.assert_called_once_with(
            expected_svc, expected_bigips)
        assert listener['provisioning_status'] == "ACTIVE"
        assert loadbalancer['provisioning_status'] == "PENDING_UPDATE"

    def test_assure_listeners_created_create_error(self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test CREATE case
        target.listener_builder = Mock()
        target.listener_builder.create_listener.return_value = "error"

        expected_bigips = target.driver.get_config_bigips()
        listener['provisioning_status'] = \
            constants_v2.F5_PENDING_CREATE
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_PENDING_UPDATE
        target._assure_listeners_created(service)

        expected_svc = dict(loadbalancer=loadbalancer, pools=service['pools'],
                            l7policies=[], l7policy_rules=[], irules=[],
                            listener=listener, networks=service['networks'])
        target.listener_builder.create_listener.assert_called_once_with(
            expected_svc, expected_bigips)
        assert listener['provisioning_status'] == "ERROR"
        assert loadbalancer['provisioning_status'] == "ERROR"

    def test_assure_listeners_created_error_to_active(
            self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test CREATE case
        target.listener_builder = Mock()
        target.listener_builder.create_listener.return_value = None

        expected_bigips = target.driver.get_config_bigips()
        listener['provisioning_status'] = \
            constants_v2.F5_ERROR
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_ACTIVE
        target._assure_listeners_created(service)

        expected_svc = dict(loadbalancer=loadbalancer, pools=service['pools'],
                            l7policies=[], l7policy_rules=[], irules=[],
                            listener=listener, networks=service['networks'])
        target.listener_builder.create_listener.assert_called_once_with(
            expected_svc, expected_bigips)
        assert listener['provisioning_status'] == "ACTIVE"
        assert loadbalancer['provisioning_status'] == "ACTIVE"

    def test_assure_listeners_deleted_pending_delete(
            self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test CREATE case
        target.listener_builder = Mock()
        target.listener_builder.delete_listener.return_value = None

        expected_bigips = target.driver.get_config_bigips()
        listener['provisioning_status'] = \
            constants_v2.F5_PENDING_DELETE
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_ACTIVE
        target._assure_listeners_deleted(service)

        expected_svc = dict(loadbalancer=loadbalancer,
                            listener=listener)
        target.listener_builder.delete_listener.assert_called_once_with(
            expected_svc, expected_bigips)
        assert listener['provisioning_status'] == "PENDING_DELETE"
        assert loadbalancer['provisioning_status'] == "ACTIVE"

    def test_assure_listeners_deleted_pending_delete_error(
            self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test CREATE case
        target.listener_builder = Mock()
        target.listener_builder.delete_listener.return_value = "error"

        expected_bigips = target.driver.get_config_bigips()
        listener['provisioning_status'] = \
            constants_v2.F5_PENDING_DELETE
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_ACTIVE
        target._assure_listeners_deleted(service)

        expected_svc = dict(loadbalancer=loadbalancer,
                            listener=listener)
        target.listener_builder.delete_listener.assert_called_once_with(
            expected_svc, expected_bigips)
        assert listener['provisioning_status'] == "ERROR"
        assert loadbalancer['provisioning_status'] == "ACTIVE"

    def test_assure_listeners_deleted_not_pending_delete(
            self, service, create_self):
        listener = service.get('listeners')[0]
        target = self.builder
        service['listener'] = listener
        loadbalancer = service['loadbalancer']

        # Test CREATE case
        target.listener_builder = Mock()

        listener['provisioning_status'] = \
            constants_v2.F5_ACTIVE
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_ACTIVE
        target._assure_listeners_deleted(service)

        assert not target.listener_builder.delete_listener.called
        assert listener['provisioning_status'] == "ACTIVE"
        assert loadbalancer['provisioning_status'] == "ACTIVE"

        listener['provisioning_status'] = \
            constants_v2.F5_ERROR
        loadbalancer['provisioning_status'] = \
            constants_v2.F5_ACTIVE
        target._assure_listeners_deleted(service)

        assert not target.listener_builder.delete_listener.called
        assert listener['provisioning_status'] == "ERROR"
        assert loadbalancer['provisioning_status'] == "ACTIVE"

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

    def reset_mocks(self, *mocks):
        for mymock in mocks:
            mymock.reset_mock()

    @pytest.mark.skip(reason="Replace implementation")
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

    @pytest.mark.skip(reason="Replace implementation")
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
                with pytest.raises(Exception):
                    builder._assure_members(service, mock.MagicMock())
                    assert service['members'][0]['provisioning_status'] ==\
                        'ERROR'

    def test_create_policy_active_status(
            self, l7policy_create_service,
            l7_listener_policy):
        """provisioning_status is ACTIVE after successful policy creation."""

        svc = l7policy_create_service
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder.esd = Mock()
        builder.esd.is_esd = Mock(return_value=False)

        mock_policy = dict(
            f5_policy=dict(name='wrapper_policy', rules=[], partition='test'),
            l7rules=list(), l7policies=list()
        )
        with mock.patch(POLICY_BUILD_PATH) as mock_policy_build:
            with mock.patch(POLICY_CREATE_PATH) as mock_policy_create:
                mock_policy_build.return_value = mock_policy

                builder._assure_l7policies_created(svc)
                assert not mock_policy_create.called

        for policy in svc['l7policies']:
            assert policy['provisioning_status'] == 'ACTIVE'

        assert svc['loadbalancer']['provisioning_status'] == 'ACTIVE'

    def test_create_policy_no_rules_error_status(
            self, l7policy_create_service):
        """provisioning_status is ERROR after policy creation fails."""

        svc = l7policy_create_service
        with mock.patch(POLICY_CREATE_PATH) as mock_pol_create:
            mock_pol_create.return_value = \
                MockHTTPError(MockHTTPErrorResponse500(), 'Server failure.')
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            builder.esd = Mock()
            builder.esd.is_esd = Mock(return_value=False)

            builder._assure_l7policies_created(svc)
            assert svc['l7policies'][0]['provisioning_status'] == 'ACTIVE'
            assert not mock_pol_create.called

    def test_delete_policy(self, l7policy_delete_service):
        """provisioning_status is PENDING_DELETE when deleteing policy."""

        svc = l7policy_delete_service
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder.esd = Mock()
        builder.esd.is_esd = Mock(return_value=False)
        builder._assure_l7policies_deleted(svc)
        assert svc['l7policies'][0]['provisioning_status'] == 'PENDING_DELETE'
        assert svc['loadbalancer']['provisioning_status'] == 'ACTIVE'

    def test_delete_policy_error_status(self, l7policy_delete_service):
        """provisioning_status is ERROR when policy fails to delete."""

        svc = l7policy_delete_service
        with mock.patch(POLICY_DELETE_PATH) as mock_pol_delete:
            mock_pol_delete.return_value = \
                MockHTTPError(MockHTTPErrorResponse409(), 'Not found.')
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            builder.esd = Mock()
            builder.esd.is_esd = Mock(return_value=False)
            builder._assure_l7policies_deleted(svc)
            assert svc['l7policies'][0]['provisioning_status'] == 'ERROR'
            # assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
            # assert ex.value.message == 'Not found.'

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
                mock_log.debug.call_args_list == \
                [mock.call('Member definition does not include Neutron port'),
                 mock.call('Member definition does not include Neutron port')]

    def test_assure_member_has_one_port(self, service):
        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'lbaas_builder.LOG') as mock_log:
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            service['members'][0].pop('port', None)
            builder._assure_members(service, mock.MagicMock())
            assert \
                mock_log.debug.call_args_list == \
                [mock.call('Member definition does not include Neutron port')]

    def test_assure_member_has_two_ports(self, service):
        with mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.'
                        'lbaas_builder.LOG') as mock_log:
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            builder._assure_members(service, mock.MagicMock())
            assert mock_log.warning.call_args_list == []

    @mock.patch(POOL_BLDR_PATH + '.delete_pool')
    def test_assure_pools_deleted(self, mock_delete, shared_pool_service):
        '''Test assure pools does not iterate of pool's listeners.'''
        shared_pool_service['pools'][0]['provisioning_status'] = \
            'PENDING_DELETE'
        pool = shared_pool_service['pools'][0]
        mock_driver = mock.MagicMock(name='driver')
        mock_bigip = mock.MagicMock(name='bigip')
        mock_driver.get_config_bigips.return_value = [mock_bigip]
        mock_delete.return_value = None

        builder = LBaaSBuilder(mock.MagicMock(), mock_driver)
        builder._assure_pools_deleted(shared_pool_service)

        assert mock_delete.called
        assert pool['provisioning_status'] == "PENDING_DELETE"

    @mock.patch(POOL_BLDR_PATH + '.delete_pool')
    def test_assure_pools_deleted_error(self, mock_delete,
                                        shared_pool_service):
        '''Test assure pools does not iterate of pool's listeners.'''
        shared_pool_service['pools'][0]['provisioning_status'] = \
            'PENDING_DELETE'
        pool = shared_pool_service['pools'][0]
        mock_driver = mock.MagicMock(name='driver')
        mock_bigip = mock.MagicMock(name='bigip')
        mock_driver.get_config_bigips.return_value = [mock_bigip]
        mock_delete.return_value = "error"

        builder = LBaaSBuilder(mock.MagicMock(), mock_driver)
        builder._assure_pools_deleted(shared_pool_service)

        assert mock_delete.called
        assert pool['provisioning_status'] == "ERROR"

    @mock.patch(POOL_BLDR_PATH + '.delete_pool')
    def test_assure_pools_deleted_create_pool(self, mock_delete,
                                              shared_pool_service):
        '''Test assure pools does not iterate of pool's listeners.'''
        pool = shared_pool_service['pools'][0]
        mock_driver = mock.MagicMock(name='driver')
        mock_bigip = mock.MagicMock(name='bigip')
        mock_driver.get_config_bigips.return_value = [mock_bigip]
        mock_delete.return_value = None

        builder = LBaaSBuilder(mock.MagicMock(), mock_driver)
        builder._assure_pools_deleted(shared_pool_service)

        assert not mock_delete.called
        assert pool['provisioning_status'] == "PENDING_CREATE"

    @mock.patch(POOL_BLDR_PATH + '.delete_healthmonitor')
    def test_assure_monitors_deleted_active(
            self, mock_delete, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'ACTIVE'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_monitors_deleted(svc)
        assert not mock_delete.called

        assert monitor['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.delete_healthmonitor')
    def test_assure_monitors_deleted_pending_delete(
            self, mock_delete, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'PENDING_DELETE'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_delete.return_value = None
        builder._assure_monitors_deleted(svc)
        assert mock_delete.called

        assert monitor['provisioning_status'] == 'PENDING_DELETE'

    @mock.patch(POOL_BLDR_PATH + '.delete_healthmonitor')
    def test_assure_monitors_deleted_error(
            self, mock_delete, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'PENDING_DELETE'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_delete.return_value = "error"
        builder._assure_monitors_deleted(svc)
        assert mock_delete.called

        assert monitor['provisioning_status'] == 'ERROR'

    @mock.patch(POOL_BLDR_PATH + '.create_healthmonitor')
    def test_assure_monitors_created_pending_create(
            self, mock_create, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'PENDING_CREATE'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_monitors_created(svc)
        assert mock_create.called

        assert monitor['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_healthmonitor')
    def test_assure_monitors_created_pending_create_error(
            self, mock_create, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'PENDING_CREATE'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = "error"
        builder._assure_monitors_created(svc)
        assert mock_create.called

        assert monitor['provisioning_status'] == 'ERROR'

    @mock.patch(POOL_BLDR_PATH + '.create_healthmonitor')
    def test_assure_monitors_created_error_to_active(
            self, mock_create, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'ERROR'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_monitors_created(svc)
        assert mock_create.called

        assert monitor['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_healthmonitor')
    def test_assure_monitors_created_pending_delete(
            self, mock_create, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        monitor = svc['healthmonitors'][0]
        monitor['provisioning_status'] = 'PENDING_DELETE'

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_monitors_created(svc)
        assert not mock_create.called

        assert monitor['provisioning_status'] == 'PENDING_DELETE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    def test__assure_pools_created_pool_create(
            self, mock_create, service):
        '''create_pool should be called in pool builder on pool create'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'PENDING_CREATE'
        pool = svc['pools'][0]

        svc['pools'][0]['provisioning_status'] = 'PENDING_CREATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_pools_created(svc)
        assert mock_create.called

        assert pool['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    def test__assure_pools_created_pool_update(
            self, mock_create, service):
        '''update_pool should be called in pool builder on pool update'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'PENDING_UPDATE'
        pool = svc['pools'][0]
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_pools_created(svc)

        assert mock_create.called

        assert pool['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    def test__assure_pools_created_pool_active(
            self, mock_create, service):
        '''create_pool should be called in pool builder with active pool'''
        svc = service
        pool = svc['pools'][0]
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_pools_created(svc)

        assert mock_create.called

        assert pool['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    def test__assure_pools_created_pool_error_to_active(
            self, mock_create, service):
        '''create_pool should be called in pool builder with errored pool'''
        svc = service
        pool = svc['pools'][0]
        svc['pools'][0]['provisioning_status'] = 'ERROR'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_pools_created(svc)

        assert mock_create.called

        assert pool['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    def test__assure_pools_created_pool_pending_to_error(
            self, mock_create, service):
        '''create_pool should be called in pool builder with errored pool'''
        svc = service
        pool = svc['pools'][0]
        svc['pools'][0]['provisioning_status'] = 'PENDING_CREATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = "ERROR"
        builder._assure_pools_created(svc)

        assert mock_create.called

        assert pool['provisioning_status'] == 'ERROR'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    def test__assure_pools_created_pool_pending_delete(
            self, mock_create, service):
        '''create_pool should be called in pool builder with errored pool'''
        svc = service
        pool = svc['pools'][0]
        svc['pools'][0]['provisioning_status'] = 'PENDING_DELETE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = "ERROR"
        builder._assure_pools_created(svc)

        assert not mock_create.called

        assert pool['provisioning_status'] == 'PENDING_DELETE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_listener_update_with_pool_active(
            self, mock_update, mock_create, service):
        '''create_pool is called on active pool and updating listener'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        svc['listeners'][0]['provisioning_status'] = 'PENDING_UPDATE'
        svc['loadbalancer']['provisioning_status'] = 'PENDING_UPDATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_pools_created(svc)

        assert not mock_update.called
        assert mock_create.called

        assert svc['loadbalancer']['provisioning_status'] == 'PENDING_UPDATE'
        assert svc['pools'][0]['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_listener_create_with_pool_active(
            self, mock_update, mock_create, service):
        '''create_pool is called with active pool and creating listener'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        svc['listeners'][0]['provisioning_status'] = 'PENDING_CREATE'
        svc['loadbalancer']['provisioning_status'] = 'PENDING_UPDATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        mock_create.return_value = None
        builder._assure_pools_created(svc)

        assert not mock_update.called
        assert mock_create.called

        assert svc['loadbalancer']['provisioning_status'] == 'PENDING_UPDATE'
        assert svc['pools'][0]['provisioning_status'] == 'ACTIVE'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_listener_update_with_pool_active_error(
            self, mock_update, mock_create, service):
        '''create_pool is called and does not fail for updating listener'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        svc['listeners'][0]['provisioning_status'] = 'PENDING_UPDATE'
        svc['loadbalancer']['provisioning_status'] = 'PENDING_UPDATE'
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())

        mock_create.return_value = "error"

        builder._assure_pools_created(svc)

        assert mock_create.called
        assert not mock_update.called

        assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
        assert svc['pools'][0]['provisioning_status'] == 'ERROR'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_listener_update_with_pool_active_404(
            self, mock_update, mock_create, service):
        '''exception raised with 404 seen on create_pool with vs update'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        svc['listeners'][0]['provisioning_status'] = 'PENDING_UPDATE'
        svc['loadbalancer']['provisioning_status'] = 'PENDING_UPDATE'
        mock_create.return_value = \
            MockHTTPError(MockHTTPErrorResponse404(), 'Exists')
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())

        builder._assure_pools_created(svc)

        assert not mock_update.called
        assert mock_create.called
        assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
        assert svc['pools'][0]['provisioning_status'] == 'ERROR'

    @mock.patch(POOL_BLDR_PATH + '.create_pool')
    @mock.patch(POOL_BLDR_PATH + '.update_pool')
    def test__assure_pools_created_listener_create_with_pool_active_404(
            self, mock_update, mock_create, service):
        '''exception raised with 404 seen on create_pool with vs create'''
        svc = service
        svc['pools'][0]['provisioning_status'] = 'ACTIVE'
        svc['listeners'][0]['provisioning_status'] = 'PENDING_CREATE'
        svc['loadbalancer']['provisioning_status'] = 'PENDING_UPDATE'
        mock_create.return_value = \
            MockHTTPError(MockHTTPErrorResponse404(), 'Exists')
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())

        builder._assure_pools_created(svc)

        assert not mock_update.called
        assert mock_create.called
        assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
        assert svc['pools'][0]['provisioning_status'] == 'ERROR'

    def test_get_pool_by_id(self, service, create_self):
        target = self.builder
        never_id = uuid.uuid4()
        pool = service['pools'][0]
        pool_id = pool['id']
        assert target.get_pool_by_id(service, pool_id) == service['pools'][0]
        assert not target.get_pool_by_id(service, never_id)

    def test_assure_loadbalancer_created_no_lb(self, service):
        svc = service
        svc.pop('loadbalancer')

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert not mock_vaddr.assure.called

    def test_assure_loadbalancer_created_active_to_active(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'ACTIVE'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert mock_vaddr.assure.called

        assert loadbalancer['provisioning_status'] == 'ACTIVE'

    def test_assure_loadbalancer_created_pending_to_active(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'PENDING_CREATE'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert mock_vaddr.assure.called

        assert loadbalancer['provisioning_status'] == 'ACTIVE'

        loadbalancer['provisioning_status'] = 'PENDING_UPDATE'

        mock_vaddr.reset_mock()
        with patch(virtual_address, return_value=mock_vaddr):
            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert mock_vaddr.assure.called

        assert loadbalancer['provisioning_status'] == 'ACTIVE'

    def test_assure_loadbalancer_created_error_to_active(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'ERROR'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert mock_vaddr.assure.called

        assert loadbalancer['provisioning_status'] == 'ACTIVE'

    def test_assure_loadbalancer_created_pending_delete(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'PENDING_DELETE'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert not mock_vaddr.assure.called

        assert loadbalancer['provisioning_status'] == 'PENDING_DELETE'

    def test_assure_loadbalancer_created_error(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'PENDING_CREATE'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        mock_vaddr.assure.side_effect = MockHTTPError(
            MockHTTPErrorResponse500())
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_created(svc, mock.MagicMock())
            assert mock_vaddr.assure.called

        assert loadbalancer['provisioning_status'] == 'ERROR'

    def test_assure_loadbalancer_deleted_pending_delete(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'PENDING_DELETE'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            builder._assure_loadbalancer_deleted(svc)
            mock_vaddr.assure.called_once_with(delete=True)

        assert loadbalancer['provisioning_status'] == 'PENDING_DELETE'

    def test_assure_loadbalancer_deleted_not_pending_delete(self, service):
        svc = service
        loadbalancer = svc.get('loadbalancer')
        loadbalancer['provisioning_status'] = 'ACTIVE'

        bigips = [Mock()]

        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._update_subnet_hints = Mock()
        builder.driver.get_config_bigips.return_value = bigips

        mock_vaddr = Mock()
        virtual_address = str(
            'f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address.'
            'VirtualAddress')
        with patch(virtual_address, return_value=mock_vaddr):

            loadbalancer['provisioning_status'] = 'ACTIVE'
            builder._assure_loadbalancer_deleted(svc)
            assert not mock_vaddr.assure.called
            assert loadbalancer['provisioning_status'] == 'ACTIVE'

            loadbalancer['provisioning_status'] = 'PENDING_CREATE'
            builder._assure_loadbalancer_deleted(svc)
            assert not mock_vaddr.assure.called
            assert loadbalancer['provisioning_status'] == 'PENDING_CREATE'

            loadbalancer['provisioning_status'] = 'PENDING_UPDATE'
            builder._assure_loadbalancer_deleted(svc)
            assert not mock_vaddr.assure.called
            assert loadbalancer['provisioning_status'] == 'PENDING_UPDATE'

            loadbalancer['provisioning_status'] = 'ERROR'
            builder._assure_loadbalancer_deleted(svc)
            assert not mock_vaddr.assure.called
            assert loadbalancer['provisioning_status'] == 'ERROR'
