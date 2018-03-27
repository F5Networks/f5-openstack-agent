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


from ..testlib.service_reader import LoadbalancerReader
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
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            str('../../testdata/service_requests/'
                'create_delete_disconnected_lb.json'))
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture
def disconnected_service_no_seg():
    neutron_services_filename = (
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            str('../../testdata/service_requests/'
                'create_delete_disconnected_noseg_lb.json'))
    )
    return (json.load(open(neutron_services_filename)))


def test_featureoff_nosegid_lb(
        track_bigip_cfg, bigip, disconnected_service_no_seg, icd_config,
        icontrol_driver):

    service_iter = iter(disconnected_service_no_seg)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']
    fake_rpc = icontrol_driver.plugin_rpc
    hostname = bigip.get_device_name()
    icd_config['f5_network_segment_physical_network'] = None

    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())
    # Make sure we are starting clean.
    assert not bigip.folder_exists(folder)

    # Create the loadbalancer (should not complete)
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending

    # Assert that update loadbalancer status was not called
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1
    call_record = fake_rpc.get_calls('update_loadbalancer_status')[0]
    assert call_record.get("operating_status", None) == 'OFFLINE'
    assert call_record.get("provisioning_status", None) == 'ERROR'

    # Assert folder created
    assert bigip.folder_exists(folder)

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

    # Assert that a self ip was created.
    selfip_name = "local-%s-%s" % (hostname, lb_reader.subnet_id())
    assert not bigip.resource_exists(ResourceType.selfip, selfip_name)

    # Assert that a snat pool was created.
    snatpool_name = folder
    assert not bigip.resource_exists(ResourceType.snatpool, snatpool_name)

    # Assert virtual address
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert not bigip.resource_exists(ResourceType.virtual_address,
                                     virtual_addr_name)

    # Delete the loadbalancer
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(
        service, delete_partition=True, delete_event=True)

    assert not lb_pending

    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1
    assert fake_rpc.get_call_count('loadbalancer_destroyed') == 1

    assert not bigip.folder_exists(folder)


def test_featureon_nosegid_to_segid_lb(track_bigip_cfg, bigip, services,
                                       icd_config, icontrol_driver):

    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']
    fake_rpc = icontrol_driver.plugin_rpc
    hostname = bigip.get_device_name()
    icd_config['f5_network_segment_physical_network'] = \
        "physnet1"

    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())

    # Make sure we are starting clean.
    assert not bigip.folder_exists(folder)

    # Create the loadbalancer (should not complete)
    lb_pending = icontrol_driver._common_service_handler(service)
    assert lb_pending

    # Assert that update loadbalancer status was not called
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 0

    # Assert folder created
    assert bigip.folder_exists(folder)

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
    # assert len(rd.vlans) == 0

    # Assert that a self ip was created.
    selfip_name = "local-%s-%s" % (hostname, lb_reader.subnet_id())
    assert not bigip.resource_exists(ResourceType.selfip, selfip_name)

    # Assert that a snat pool was created.
    snatpool_name = folder
    assert not bigip.resource_exists(ResourceType.snatpool, snatpool_name)

    # Assert virtual address
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert not bigip.resource_exists(ResourceType.virtual_address,
                                     virtual_addr_name)

    # Create the loadbalancer with VLAN
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    lb_reader = LoadbalancerReader(service)

    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1

    # Assert tunnel created.
    vlan_name = 'vlan-%d' % (lb_reader.network_seg_id())
    fq_vlan_name = '/%s/%s' % (folder, vlan_name)
    assert bigip.resource_exists(ResourceType.vlan, vlan_name)
    vlan = bigip.get_resource(ResourceType.vlan,
                              vlan_name,
                              partition=folder)
    assert vlan

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
    assert fq_vlan_name in rd.vlans

    # Assert that a self ip was created.
    selfip_name = "local-%s-%s" % (hostname, lb_reader.subnet_id())
    assert bigip.resource_exists(ResourceType.selfip, selfip_name)
    selfip = bigip.get_resource(ResourceType.selfip,
                                selfip_name,
                                partition=folder)
    assert selfip
    assert selfip.vlan == fq_vlan_name
    assert selfip.address == "192.168.101.2%1/24"

    # Assert that a snat pool was created.
    snatpool_name = folder
    assert bigip.resource_exists(ResourceType.snatpool, snatpool_name)
    snatpool = bigip.get_resource(ResourceType.snatpool,
                                  snatpool_name,
                                  partition=folder)
    assert snatpool

    # Delete the loadbalancer
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending

    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1
    assert fake_rpc.get_call_count('loadbalancer_destroyed') == 1

    assert not bigip.folder_exists(folder)
