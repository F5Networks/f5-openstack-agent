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

from ..testlib.service_reader import LoadbalancerReader
from ..testlib.resource_validator import ResourceValidator

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/'
                     'tcp_listener.json'
                     )
    )
    return (json.load(open(neutron_services_filename)))


def test_single_pool_tcp_vs(track_bigip_cfg, bigip, services, icd_config,
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
    validator.assert_virtual_profiles(listener, folder, ['/Common/fastL4'])

    # create pool
    service = service_iter.next()
    pool = service['pools'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool, folder)
    validator.assert_virtual_profiles(listener, folder, ['/Common/fastL4'])
    validator.assert_session_persistence(listener, 'source_addr', None, folder)

    # update pool session persistence, HTTP_COOKIE
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_session_persistence(listener, 'cookie', None, folder)
    validator.assert_virtual_profiles(
        listener, folder, ['/Common/http', '/Common/oneconnect', '/Common/tcp'])

    # update pool session persistence, APP_COOKIE
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_session_persistence(
        listener, 'app_cookie_TEST_' + listener['id'], 'JSESSIONID', folder)
    validator.assert_virtual_profiles(
        listener, folder, ['/Common/http', '/Common/oneconnect', '/Common/tcp'])

    # remove pool session persistence
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_session_persistence(listener, None, None, folder)
    validator.assert_virtual_profiles(listener, folder, ['/Common/fastL4'])

    # delete pool (and member, node)
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_deleted(pool, None, folder)
    validator.assert_virtual_profiles(listener, folder, ['/Common/fastL4'])

    # delete listener
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    # delete loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(folder)
