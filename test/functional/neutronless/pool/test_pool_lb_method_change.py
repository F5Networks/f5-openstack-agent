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

import json
import logging
import os
import pytest
import requests

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

from ..testlib.resource_validator import ResourceValidator
from ..testlib.service_reader import LoadbalancerReader

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../testdata/service_requests/pool_multiple_members.json')
    )
    return (json.load(open(neutron_services_filename)))


def test_pool_lb_change_ratio(track_bigip_cfg, bigip, services, icd_config,
                              icontrol_driver):
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)
    validator = ResourceValidator(bigip, env_prefix)

    # create lb
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)

    # create listener
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # create pool with round-robin, no members
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    pool_srvc = service['pools'][0]
    pool_name = '{0}_{1}'.format(env_prefix, pool_srvc['id'])
    validator.assert_pool_valid(pool_srvc, folder)
    pool = bigip.get_resource(ResourceType.pool, pool_name, partition=folder)
    assert pool.loadBalancingMode == 'round-robin'

    # create member with weight = 1
    service = service_iter.next()
    member = service['members'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_member_valid(pool_srvc, member, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'round-robin'

    # create member with weight > 1
    service = service_iter.next()
    member = service['members'][1]
    icontrol_driver._common_service_handler(service)
    validator.assert_member_valid(pool_srvc, member, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'ratio-member'

    # create member with weight = 1
    service = service_iter.next()
    member = service['members'][2]
    icontrol_driver._common_service_handler(service)
    validator.assert_member_valid(pool_srvc, member, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'ratio-member'

    # delete pool member with weight > 1
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'round-robin'

    # update pool to have lb method least connections
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'least-connections-member'

    # create member with weight > 1
    service = service_iter.next()
    member = service['members'][2]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    validator.assert_member_valid(pool_srvc, member, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'ratio-least-connections-member'

    # delete member with weight > 1
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'least-connections-member'

    # delete second member
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'least-connections-member'

    # set lb method to SOURCE_IP for pool
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'least-connections-node'

    # update member to have weight > 1
    service = service_iter.next()
    member = service['members'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    validator.assert_member_valid(pool_srvc, member, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'least-connections-node'

    # delete remaining member
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool_srvc, folder)
    pool.refresh()
    assert pool.loadBalancingMode == 'least-connections-node'

    # delete pool
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    assert not bigip.resource_exists(
        ResourceType.pool, pool_name, partition=folder)

    # delete listener
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # delete lb
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
