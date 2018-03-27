# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType
import json
import logging
import os
import pytest
import requests
import urllib

from ..testlib.resource_validator import ResourceValidator
from ..testlib.service_reader import LoadbalancerReader


requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/single_pool.json')
    )
    return (json.load(open(neutron_services_filename)))


def get_service_file(relative_path):
    test_file_path = os.path.dirname(os.path.abspath(__file__))
    neutron_services_filename = (
        os.path.join(test_file_path,relative_path)
    )
    return (json.load(open(neutron_services_filename)))

def get_service_info(service, env_prefix):
    member = service['members'][0]
    pool = service['pools'][0]
    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])
    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])
    node_name = '{0}'.format(member['address'])

    return pool_name, member_name, node_name, folder


def get_member_created(bigip, pool_name, member_name, folder):
    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)
    return m


def check_member_up(member):
    assert member.address == "10.2.1.2%1"
    assert member.session == "monitor-enabled"
    assert member.ratio == 1


def check_member_down(member):
    assert member.address == "10.2.1.2%1"
    assert member.session == "user-disabled"
    assert member.ratio == 1


def test_create_single_member_down_up(track_bigip_cfg,
                                      bigip,
                                      icd_config,
                                      icontrol_driver):

    env_prefix = icd_config['environment_prefix']

    # Tests the creation and bringing a member down and then up
    service_create_member_down_up = get_service_file(
        '../../testdata/service_requests/create_single_member_down_up.json')
    service_iter = iter(service_create_member_down_up)

    # create single member down
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    pool_name, member_name, node_name, folder = get_service_info(service,
                                                                 env_prefix)
    assert bigip.member_exists(
        pool_name, member_name, partition=folder)
    assert bigip.resource_exists(
        ResourceType.node, node_name, partition=folder)

    m = get_member_created(bigip, pool_name, member_name, folder)
    check_member_down(m)

    # bring member up
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    m = get_member_created(bigip, pool_name, member_name, folder)
    check_member_up(m)


def test_create_single_member_up_down(track_bigip_cfg, bigip, icd_config,
                                      icontrol_driver):

    env_prefix = icd_config['environment_prefix']

    # Tests the creation and bringing a member up and then down
    service_create_member_up_down = get_service_file(
        '../../testdata/service_requests/create_single_member_up_down.json')
    service_iter = iter(service_create_member_up_down)

    # create single member up
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    pool_name, member_name, node_name, folder = get_service_info(service,
                                                                 env_prefix)
    assert bigip.member_exists(
        pool_name, member_name, partition=folder)
    assert bigip.resource_exists(
        ResourceType.node, node_name, partition=folder)

    m = get_member_created(bigip, pool_name, member_name, folder)
    check_member_up(m)

    # bring member down
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    m = get_member_created(bigip, pool_name, member_name, folder)
    check_member_down(m)
