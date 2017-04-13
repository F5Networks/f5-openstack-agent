# coding=utf-8
# Copyright 2017 F5 Networks Inc.
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


from ..testlib.service_reader import LoadbalancerReader
from copy import deepcopy
import json
import logging
import os
import pytest
import requests


from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/create_delete_lb.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture(scope="module")
def icd_config():
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../config/basic_agent_config.json')
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password
    config['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name

    return config


def test_create_delete_lb_autosnat(bigip, services, icd_config, icontrol_driver):

    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']
    fake_rpc = icontrol_driver.plugin_rpc
    hostname = pytest.symbols.bigip_hostname

    # Change the configuration so that Auto SNAT is used.
    icd_config['f5_snat_addresses_per_subnet'] = 0

    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())

    # Make sure we are starting clean.
    assert not bigip.folder_exists(folder)

    # Create the loadbalancer
    icontrol_driver._common_service_handler(service)

    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1
    call_record = fake_rpc.get_calls('update_loadbalancer_status')[0]
    assert call_record.get("operating_status", None) == 'ONLINE'
    assert call_record.get("provisioning_status", None) == 'ACTIVE'

    # Assert folder created
    assert bigip.folder_exists(folder)

    # Assert tunnel created.
    tunnel_name = 'tunnel-%s-%d' % (lb_reader.network_type(),
                                    lb_reader.network_seg_id())
    fq_tunnel_name = '/%s/%s' % (folder, tunnel_name)
    assert bigip.resource_exists(ResourceType.tunnel, tunnel_name)
    tunnel = bigip.get_resource(ResourceType.tunnel,
                                tunnel_name,
                                partition=folder)
    assert tunnel

    # Assert route domain created
    rd_name = folder
    assert bigip.resource_exists(ResourceType.route_domain, rd_name)
    rd = bigip.get_resource(ResourceType.route_domain,
                            rd_name,
                            partition=folder)

    # Assert route domain properties
    assert rd
    assert rd.id == 1
    assert rd.strict == "disabled"
    assert fq_tunnel_name in rd.vlans

    # Assert that a self ip was created.
    selfip_name = "local-%s-%s" % (hostname, lb_reader.subnet_id())
    assert bigip.resource_exists(ResourceType.selfip, selfip_name)
    selfip = bigip.get_resource(ResourceType.selfip,
                                selfip_name,
                                partition=folder)
    assert selfip
    assert selfip.vlan == fq_tunnel_name
    assert selfip.address == "10.2.2.100%1/24"

    assert fake_rpc.get_call_count('create_port_on_subnet') == 1
    call = fake_rpc.get_calls('create_port_on_subnet')[0]
    assert call['name'] == selfip_name
    
    # Assert that a snat pool was not created.
    snatpool_name = folder
    assert not bigip.resource_exists(ResourceType.snatpool, snatpool_name)

    # Assert virtual address
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert bigip.resource_exists(ResourceType.virtual_address,
                                 virtual_addr_name)
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr
    assert virtual_addr.address == "10.2.2.112%1"
    assert virtual_addr.trafficGroup == "/Common/traffic-group-1"
    assert virtual_addr.autoDelete == "false"

    # Delete the loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(folder)


def test_create_delete_lb_multisnat(bigip, services, icd_config, icontrol_driver):

    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']
    fake_rpc = icontrol_driver.plugin_rpc
    icd_config['f5_snat_addresses_per_subnet'] = 5
    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())
    hostname = pytest.symbols.bigip_hostname

    # Make sure we are starting clean.
    assert not bigip.folder_exists(folder)

    # Create the loadbalancer
    icontrol_driver._common_service_handler(service)

    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1
    call_record = fake_rpc.get_calls('update_loadbalancer_status')[0]
    assert call_record.get("operating_status", None) == 'ONLINE'
    assert call_record.get("provisioning_status", None) == 'ACTIVE'

    # Assert folder created
    assert bigip.folder_exists(folder)

    # Assert tunnel created.
    tunnel_name = 'tunnel-%s-%d' % (lb_reader.network_type(),
                                    lb_reader.network_seg_id())
    fq_tunnel_name = '/%s/%s' % (folder, tunnel_name)
    assert bigip.resource_exists(ResourceType.tunnel, tunnel_name)
    tunnel = bigip.get_resource(ResourceType.tunnel,
                                tunnel_name,
                                partition=folder)
    assert tunnel

    # Assert route domain created
    rd_name = folder
    assert bigip.resource_exists(ResourceType.route_domain, rd_name)
    rd = bigip.get_resource(ResourceType.route_domain,
                            rd_name,
                            partition=folder)

    # Assert route domain properties
    assert rd
    assert rd.id == 1
    assert rd.strict == "disabled"
    assert fq_tunnel_name in rd.vlans

    # Assert that a self ip was created.
    selfip_name = "local-%s-%s" % (hostname, lb_reader.subnet_id())
    assert bigip.resource_exists(ResourceType.selfip, selfip_name)
    selfip = bigip.get_resource(ResourceType.selfip,
                                selfip_name,
                                partition=folder)
    assert selfip
    assert selfip.vlan == fq_tunnel_name
    assert selfip.address == "10.2.2.100%1/24"

    # Assert that a snat pool was created.
    snatpool_name = folder
    assert bigip.resource_exists(ResourceType.snatpool, snatpool_name)
    snatpool = bigip.get_resource(ResourceType.snatpool,
                                  snatpool_name,
                                  partition=folder)
    assert snatpool
    snat_members = snatpool.members

    # Assert snat transtion pool members
    for i in range(icd_config['f5_snat_addresses_per_subnet']):
        snat_xlation = "snat-traffic-group-local-only-%s_%s" % (
            lb_reader.subnet_id(), i)

        snat_xlation_fq = "/%s/%s" % (folder, snat_xlation)
        assert bigip.resource_exists(ResourceType.snat_translation,
                                     snat_xlation)
        assert snat_xlation_fq in snat_members
        snat_member = bigip.get_resource(ResourceType.snat_translation,
                                         snat_xlation,
                                         partition=folder)

        assert snat_member
        assert snat_member.trafficGroup == "/Common/traffic-group-local-only"

        snat_xlation_addr = "10.2.2.%s%%1" % str(101 + i)
        assert snat_member.address == snat_xlation_addr

    # Assert virtual address
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert bigip.resource_exists(ResourceType.virtual_address,
                                 virtual_addr_name)
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr
    assert virtual_addr.address == "10.2.2.112%1"
    assert virtual_addr.trafficGroup == "/Common/traffic-group-1"
    assert virtual_addr.autoDelete == "false"

    # Delete the loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(folder)


def test_create_delete_lb_snatoff(bigip, services, icd_config, icontrol_driver):

    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']
    fake_rpc = icontrol_driver.plugin_rpc
    hostname = pytest.symbols.bigip_hostname

    # Change the configuration so that Auto SNAT is used.
    icd_config['f5_snat_mode'] = "false"
    icd_config['f5_snat_addresses_per_subnet'] = 0

    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())

    # Make sure we are starting clean.
    assert not bigip.folder_exists(folder)

    # Create the loadbalancer
    icontrol_driver._common_service_handler(service)

    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1
    call_record = fake_rpc.get_calls('update_loadbalancer_status')[0]
    assert call_record.get("operating_status", None) == 'ONLINE'
    assert call_record.get("provisioning_status", None) == 'ACTIVE'

    # Assert folder created
    assert bigip.folder_exists(folder)

    # Assert tunnel created.
    tunnel_name = 'tunnel-%s-%d' % (lb_reader.network_type(),
                                    lb_reader.network_seg_id())
    fq_tunnel_name = '/%s/%s' % (folder, tunnel_name)
    assert bigip.resource_exists(ResourceType.tunnel, tunnel_name)
    tunnel = bigip.get_resource(ResourceType.tunnel,
                                tunnel_name,
                                partition=folder)
    assert tunnel

    # Assert route domain created
    rd_name = folder
    assert bigip.resource_exists(ResourceType.route_domain, rd_name)
    rd = bigip.get_resource(ResourceType.route_domain,
                            rd_name,
                            partition=folder)

    # Assert route domain properties
    assert rd
    assert rd.id == 1
    assert rd.strict == "disabled"
    assert fq_tunnel_name in rd.vlans

    # Assert that a self ip was created.
    selfip_name = "local-%s-%s" % (hostname, lb_reader.subnet_id())
    assert bigip.resource_exists(ResourceType.selfip, selfip_name)
    selfip = bigip.get_resource(ResourceType.selfip,
                                selfip_name,
                                partition=folder)
    assert selfip
    assert selfip.vlan == fq_tunnel_name
    assert selfip.address == "10.2.2.100%1/24"

    assert fake_rpc.get_call_count('create_port_on_subnet') == 1
    call = fake_rpc.get_calls('create_port_on_subnet')[0]
    assert call['name'] == selfip_name
    
    # Assert that a snat pool was not created.
    snatpool_name = folder
    assert not bigip.resource_exists(ResourceType.snatpool, snatpool_name)

    # Assert virtual address
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert bigip.resource_exists(ResourceType.virtual_address,
                                 virtual_addr_name)
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr
    assert virtual_addr.address == "10.2.2.112%1"
    assert virtual_addr.trafficGroup == "/Common/traffic-group-1"
    assert virtual_addr.autoDelete == "false"

    # Delete the loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(folder)
