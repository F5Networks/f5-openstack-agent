# coding=utf-8
# Copyright 2016 F5 Networks Inc.
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

from copy import deepcopy
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


@pytest.fixture()
def service_create_member_up_down():
    neutron_services_filename = (
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../testdata/service_requests/create_single_member_up_down.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture()
def service_create_member_down_up():
    neutron_services_filename = (
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../testdata/service_requests/create_single_member_down_up.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture()
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


def lbaas_service_one_member(request,
                             bigip,
                             services,
                             icd_config,
                             icontrol_driver):
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)
    validator = ResourceValidator(bigip, env_prefix)

    # create loadbalancer
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)

    # create listener
    service = service_iter.next()
    listener = service['listeners'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_valid(listener, folder)

    # create pool
    service = service_iter.next()
    pool = service['pools'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool, folder)

    # create health monitor
    service = service_iter.next()
    monitor = service['healthmonitors'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_healthmonitor_valid(monitor, folder)

    # create member, node
    service = service_iter.next()
    member = service['members'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_member_valid(pool, member, folder)

    def fin():
        # delete health monitor
        service = service_iter.next()
        icontrol_driver._common_service_handler(service)
        validator.assert_healthmonitor_deleted(monitor, folder)

        # delete pool (and member, node)
        service = service_iter.next()
        icontrol_driver._common_service_handler(service)
        validator.assert_pool_deleted(pool, member, folder)

        # delete listener
        service = service_iter.next()
        icontrol_driver._common_service_handler(service)
        validator.assert_virtual_deleted(listener, folder)

        # delete loadbalancer
        service = service_iter.next()
        icontrol_driver._common_service_handler(service, delete_partition=True)
        assert not bigip.folder_exists(folder)

    request.addfinalizer(fin)
    return service_iter


def test_create_single_member_up(bigip,
                                 service_create_member_up_down,
                                 icd_config,
                                 icontrol_driver):

    env_prefix = icd_config['environment_prefix']
    service_iter = iter(service_create_member_up_down)

    service = service_iter.next()
    member = service['members'][0]
    pool = service['pools'][0]
    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])

    icontrol_driver._common_service_handler(service)

    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])
    node_name = '{0}'.format(member['address'])

    assert bigip.member_exists(
        pool_name, member_name, partition=folder)
    assert bigip.resource_exists(
        ResourceType.node, node_name, partition=folder)

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)

    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    assert m.address == "10.2.1.2%1"
    assert m.session == "monitor-enabled"
    assert m.ratio == 1


def test_create_single_member_down(bigip,
                                   service_create_member_down_up,
                                   icd_config,
                                   icontrol_driver):

    env_prefix = icd_config['environment_prefix']
    service_iter = iter(service_create_member_down_up)

    service = service_iter.next()
    member = service['members'][0]
    pool = service['pools'][0]
    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])

    icontrol_driver._common_service_handler(service)

    pool = service['pools'][0]
    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])
    node_name = '{0}'.format(member['address'])

    assert bigip.member_exists(
        pool_name, member_name, partition=folder)
    assert bigip.resource_exists(
        ResourceType.node, node_name, partition=folder)

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)

    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    assert m.address == "10.2.1.2%1"
    assert m.session == "user-disabled"
    assert m.ratio == 1


def test_create_single_member_down_up(bigip,
                                      service_create_member_down_up,
                                      icd_config,
                                      icontrol_driver):

    env_prefix = icd_config['environment_prefix']
    service_iter = iter(service_create_member_down_up)

    service = service_iter.next()
    member = service['members'][0]
    pool = service['pools'][0]
    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])

    icontrol_driver._common_service_handler(service)

    pool = service['pools'][0]
    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])
    node_name = '{0}'.format(member['address'])

    assert bigip.member_exists(
        pool_name, member_name, partition=folder)
    assert bigip.resource_exists(
        ResourceType.node, node_name, partition=folder)

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    assert m.address == "10.2.1.2%1"
    assert m.session == "user-disabled"

    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    assert m.address == "10.2.1.2%1"
    assert m.session == "monitor-enabled"


def test_create_single_member_up_down(bigip,
                                      service_create_member_up_down,
                                      icd_config,
                                      icontrol_driver):

    env_prefix = icd_config['environment_prefix']
    service_iter = iter(service_create_member_up_down)

    service = service_iter.next()
    member = service['members'][0]
    pool = service['pools'][0]
    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])

    icontrol_driver._common_service_handler(service)

    pool = service['pools'][0]
    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])
    node_name = '{0}'.format(member['address'])

    assert bigip.member_exists(
        pool_name, member_name, partition=folder)
    assert bigip.resource_exists(
        ResourceType.node, node_name, partition=folder)

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    assert m.address == "10.2.1.2%1"
    assert m.session == "monitor-enabled"

    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    assert m.address == "10.2.1.2%1"
    assert m.session == "user-disabled"
