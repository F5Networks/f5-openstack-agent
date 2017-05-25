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
                     '../../testdata/service_requests/'
                     'create_update_lb_state.json')
    )
    return (json.load(open(neutron_services_filename)))


def test_create_update_lb_state(bigip, services, icd_config, icontrol_driver):
    """Test creating and updating loadbalancer with differing admin states.

    Create loadbalancer using admin-state-down and eval virtual address
    enabled value.

    Update loadbalancer using admin-state-up and eval virtual address
    enabled value.

    Create loadbalancer without admin-state-down and eval virtual address
    enabled value.

    Update loadbalancer using admin-state-up and eval virtual address
    enabled value.


    :param bigip: BIG-IP under test
    :param services: list of service objects
    :param icd_config: agent configuration
    :param icontrol_driver: icontrol driver instance
    """

    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']

    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())

    # Make sure we are starting clean.
    assert not bigip.folder_exists(folder)

    # Create loadbalancer, admin_state_down
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending

    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert bigip.resource_exists(ResourceType.virtual_address,
                                 virtual_addr_name)
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr.enabled == 'yes'

    # Update loadbalancer, admin_state_up=False
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr.enabled == 'no'

    # Update loadbalancer, admin_state_up=True
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr.enabled == 'yes'

    # Delete loadbalancer
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service, delete_partition=True,
                                                         delete_event=True)
    assert not lb_pending
    assert not bigip.resource_exists(ResourceType.virtual_address,
                                     virtual_addr_name)

    # Create loadbalancer, admin_state_down
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    assert bigip.resource_exists(ResourceType.virtual_address,
                                 virtual_addr_name)
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr.enabled == 'no'

    # Update loadbalancer, admin_state_up=True
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr.enabled == 'yes'

    # Update loadbalancer, admin_state_up=False
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name,
                                      partition=folder)
    assert virtual_addr.enabled == 'no'

    # Delete loadbalancer
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service, delete_partition=True,
                                                         delete_event=True)
    assert not lb_pending
    assert not bigip.folder_exists(folder)
