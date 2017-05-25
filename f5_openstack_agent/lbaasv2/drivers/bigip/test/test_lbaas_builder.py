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

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder import \
    LBaaSBuilder

import copy
import mock
import pytest

from requests import HTTPError


POL_CREATE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.create_l7policy'
POL_DELETE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.update_l7policy'
RULE_CREATE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.create_l7rule'
RULE_DELETE_PATH = \
    'f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_service' \
    '.L7PolicyService.delete_l7rule'


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
                      u'port': 'port',
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
        with mock.patch(
                target='f5_openstack_agent.lbaasv2.drivers.bigip.'
                       'pool_service.PoolServiceBuilder.'
                       'create_member') as mock_create:
            with mock.patch(
                    target='f5_openstack_agent.lbaasv2.drivers.'
                           'bigip.pool_service.PoolServiceBuilder.'
                           'update_member') as mock_update:
                mock_create.side_effect = MockHTTPError(
                    MockHTTPErrorResponse409())
                mock_update.side_effect = MockHTTPError(
                    MockHTTPErrorResponse409())
                service['members'][0]['provisioning_status'] = 'PENDING_UPDATE'
                service['pools'][0]['provisioning_status'] = 'ACTIVE'
                builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
                with pytest.raises(f5_ex.MemberUpdateException):
                    builder._assure_members(service, mock.MagicMock())
                    assert service['members'][0]['provisioning_status'] ==\
                        'ERROR'

    def test_create_policy_active_status(self, l7policy_create_service):
        """provisioning_status is ACTIVE after successful policy creation."""

        svc = l7policy_create_service
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_l7policies_created(svc)
        assert svc['l7policies'][0]['provisioning_status'] == 'PENDING_CREATE'
        assert svc['loadbalancer']['provisioning_status'] == 'ACTIVE'

    def test_create_policy_error_status(self, l7policy_create_service):
        """provisioning_status is ERROR after policy creation fails."""

        svc = l7policy_create_service
        with mock.patch(POL_CREATE_PATH) as mock_pol_create:
            mock_pol_create.side_effect = \
                MockHTTPError(MockHTTPErrorResponse500(), 'Server failure.')
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            with pytest.raises(f5_ex.L7PolicyCreationException) as ex:
                builder._assure_l7policies_created(svc)
            assert svc['l7policies'][0]['provisioning_status'] == 'ERROR'
            assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
            assert ex.value.message == 'Server failure.'

    def test_delete_policy(self, l7policy_delete_service):
        """provisioning_status is PENDING_DELETE when deleteing policy."""

        svc = l7policy_delete_service
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_l7policies_deleted(svc)
        assert svc['l7policies'][0]['provisioning_status'] == 'PENDING_DELETE'
        assert svc['loadbalancer']['provisioning_status'] == 'ACTIVE'

    def test_delete_policy_error_status(self, l7policy_delete_service):
        """provisioning_status is ERROR when policy fails to delete."""

        svc = l7policy_delete_service
        with mock.patch(POL_DELETE_PATH) as mock_pol_delete:
            mock_pol_delete.side_effect = \
                MockHTTPError(MockHTTPErrorResponse409(), 'Not found.')
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            with pytest.raises(f5_ex.L7PolicyDeleteException) as ex:
                builder._assure_l7policies_deleted(svc)
            assert svc['l7policies'][0]['provisioning_status'] == 'ERROR'
            assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
            assert ex.value.message == 'Not found.'

    def test_create_rule_active_status(self, l7rule_create_service):
        """provisioning_status is ACTIVE after successful rule creation."""

        svc = l7rule_create_service
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_l7rules_created(svc)
        assert svc['l7policy_rules'][0]['provisioning_status'] == \
            'PENDING_CREATE'
        assert svc['loadbalancer']['provisioning_status'] == 'ACTIVE'

    def test_create_rule_error_status(self, l7rule_create_service):
        """provisioning_status is ERROR after rule creation fails."""

        svc = l7rule_create_service
        with mock.patch(RULE_CREATE_PATH) as mock_pol_create:
            mock_pol_create.side_effect = \
                MockHTTPError(MockHTTPErrorResponse500(), 'Server failure.')
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            with pytest.raises(f5_ex.L7PolicyCreationException) as ex:
                builder._assure_l7rules_created(svc)
            assert svc['l7policy_rules'][0]['provisioning_status'] == 'ERROR'
            assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
            assert ex.value.message == 'Server failure.'

    def test_delete_rule(self, l7rule_delete_service):
        """provisioning_status is PENDING_DELETE when deleteing rule."""

        svc = l7rule_delete_service
        builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
        builder._assure_l7rules_deleted(svc)
        assert svc['l7policy_rules'][0]['provisioning_status'] == \
            'PENDING_DELETE'
        assert svc['loadbalancer']['provisioning_status'] == 'ACTIVE'

    def test_delete_rule_error_status(self, l7rule_delete_service):
        """provisioning_status is ERROR when rule fails to delete."""

        svc = l7rule_delete_service
        with mock.patch(RULE_DELETE_PATH) as mock_pol_delete:
            mock_pol_delete.side_effect = \
                MockHTTPError(MockHTTPErrorResponse409(), 'Not found.')
            builder = LBaaSBuilder(mock.MagicMock(), mock.MagicMock())
            with pytest.raises(f5_ex.L7PolicyDeleteException) as ex:
                builder._assure_l7rules_deleted(svc)
            assert svc['l7policy_rules'][0]['provisioning_status'] == 'ERROR'
            assert svc['loadbalancer']['provisioning_status'] == 'ERROR'
            assert ex.value.message == 'Not found.'
