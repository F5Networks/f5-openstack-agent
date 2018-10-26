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

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

"""
Commands to create a member for the weight testing.

(neutron) lbaas-member-create --protocol-port 8080 --address 192.168.101.9 \
    --subnet admin-subnet pool1
Created a new member:
+----------------+--------------------------------------+
| Field          | Value                                |
+----------------+--------------------------------------+
| address        | 192.168.101.9                        |
| admin_state_up | True                                 |
| id             | a3e24756-4131-4157-a6cc-f9066260ad61 |
| name           |                                      |
| protocol_port  | 8080                                 |
| subnet_id      | 2b7ca4b5-a2b9-4234-91ed-5236afac1166 |
| tenant_id      | dfd83103ce2047d5b20ccd6ef272f3cc     |
| weight         | 1                                    |
+----------------+--------------------------------------+
(neutron) lbaas-member-update --weight 5 a3e24756-4131-4157-a6cc-f9066260ad61 \
    pool1
Updated member: a3e24756-4131-4157-a6cc-f9066260ad61
(neutron) lbaas-member-update --weight 1 a3e24756-4131-4157-a6cc-f9066260ad61 \
    pool1
Updated member: a3e24756-4131-4157-a6cc-f9066260ad61
(neutron) lbaas-member-update --weight 0 a3e24756-4131-4157-a6cc-f9066260ad61 \
    pool1
Updated member: a3e24756-4131-4157-a6cc-f9066260ad61
(neutron) lbaas-member-update --weight 1 a3e24756-4131-4157-a6cc-f9066260ad61 \
    pool1
Updated member: a3e24756-4131-4157-a6cc-f9066260ad61
(neutron) lbaas-member-update --weight 256 \
    a3e24756-4131-4157-a6cc-f9066260ad61 pool1
Updated member: a3e24756-4131-4157-a6cc-f9066260ad61
(neutron) lbaas-member-update --weight 257 \
    a3e24756-4131-4157-a6cc-f9066260ad61 pool1
Invalid input for weight. Reason: '257' is too large - must be no larger than
'256'.
Neutron server returns request_ids: ['req-5517a572-3f7f-4f8c-812c-268c252b382b']
(neutron) lbaas-member-update --weight 1 a3e24756-4131-4157-a6cc-f9066260ad61 \
    pool1
Updated member: a3e24756-4131-4157-a6cc-f9066260ad61
(neutron) lbaas-member-delete a3e24756-4131-4157-a6cc-f9066260ad61 pool1
Deleted member: a3e24756-4131-4157-a6cc-f9066260ad61
"""


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../testdata/service_requests/single_member_weight_updates.json')
    )
    return (json.load(open(neutron_services_filename)))


def get_next_member(service_iterator, icontrol_driver, bigip, env_prefix):

    service = service_iterator.next()
    member = service['members'][0]
    pool = service['pools'][0]
    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])
    icontrol_driver._common_service_handler(service)

    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])

    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    m = m.load(name=urllib.quote(member_name), partition=folder)

    return m


def get_names_from_service(service, env_prefix):
    member = service['members'][0]
    member_name = '{0}:{1}'.format(member['address'],
                                   member['protocol_port'])
    pool = service['pools'][0]
    pool_name = '{0}_{1}'.format(env_prefix, pool['id'])

    folder = '{0}_{1}'.format(env_prefix, pool['tenant_id'])

    node_name = '{0}'.format(member['address'])

    return (member_name, pool_name, node_name, folder)


def test_single_member_weight_updates(
        track_bigip_cfg,
        bigip,
        services,
        icd_config,
        icontrol_driver):
    """Tests a single member's weight with updates"""
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)

    # create loadbalancer with pool
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # Create a member
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.session == "user-enabled"
    assert m.ratio == 1

    # Update the member weight to 5
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.ratio == 5
    assert m.session == "user-enabled"

    # Set the member weight to 1
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.ratio == 1
    assert m.session == "user-enabled"

    # Set the member weight to 0 (not a valid weight for BIG-IP)
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.ratio == 1
    assert m.session == "user-disabled"

    # Set the weight back to 1
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.ratio == 1
    assert m.session == "user-enabled"

    # Set the weight to the Neutron max
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.ratio == 256
    assert m.session == "user-enabled"

    # Set the weight to 1
    m = get_next_member(service_iter, icontrol_driver, bigip, env_prefix)
    assert m.ratio == 1
    assert m.session == "user-enabled"

    # Delete the member
    service = service_iter.next()
    (member_name, pool_name, node_name, folder) = \
        get_names_from_service(service, env_prefix)
    icontrol_driver._common_service_handler(service)
    p = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    m = p.members_s.members
    assert not m.exists(name=urllib.quote(member_name), partition=folder)

    # Delete the rest of the objects, pool, listener, loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)

    assert not bigip.folder_exists(folder)
