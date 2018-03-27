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

import json
import logging
import os
import pytest
import requests

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../testdata/service_requests/listener_update.json')
    )
    return (json.load(open(neutron_services_filename)))


def get_next_listener(service_iterator, icontrol_driver, bigip, env_prefix):

    service = service_iterator.next()
    listener = service['listeners'][0]
    folder = '{0}_{1}'.format(env_prefix, listener['tenant_id'])
    icontrol_driver._common_service_handler(service)

    listener_name = '{0}_{1}'.format(env_prefix, listener['id'])
    return bigip.get_resource(
        ResourceType.virtual, listener_name, partition=folder)


def get_folder_name(service, env_prefix):
    return '{0}_{1}'.format(env_prefix, service['loadbalancer']['tenant_id'])


def test_listener_update(
        track_bigip_cfg,
        bigip,
        services,
        icd_config,
        icontrol_driver):

    env_prefix = 'TEST'
    service_iter = iter(services)

    # Create loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # Create listener (no name, description)
    l = get_next_listener(service_iter, icontrol_driver, bigip, env_prefix)
    assert l.name.startswith('TEST_')
    assert not hasattr(l, 'description')
    assert l.connectionLimit == 0
    assert l.enabled

    # Update name ('spring'). Description is changed to include name.
    l = get_next_listener(service_iter, icontrol_driver, bigip, env_prefix)
    assert l.name.startswith('TEST_')
    assert l.description == 'spring:'
    assert l.connectionLimit == 0
    assert l.enabled

    # Update description ('has sprung')
    l = get_next_listener(service_iter, icontrol_driver, bigip, env_prefix)
    assert l.name.startswith('TEST_')
    assert l.description == 'spring: has-sprung'
    assert l.connectionLimit == 0
    assert l.enabled

    # Update connection limit (200)
    l = get_next_listener(service_iter, icontrol_driver, bigip, env_prefix)
    assert l.name.startswith('TEST_')
    assert l.description == 'spring: has-sprung'
    assert l.connectionLimit == 200
    assert l.enabled

    # Update admin_state_up (False)
    l = get_next_listener(service_iter, icontrol_driver, bigip, env_prefix)
    assert l.name.startswith('TEST_')
    assert l.description == 'spring: has-sprung'
    assert l.connectionLimit == 200
    assert l.disabled

    # Delete listener
    service = service_iter.next()
    folder = get_folder_name(service, env_prefix)
    icontrol_driver._common_service_handler(service)

    # Delete loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)

    # All objects deleted
    assert not bigip.folder_exists(folder)
