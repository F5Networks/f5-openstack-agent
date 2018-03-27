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


requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/'
                     'create_delete_opflex_member.json')
    )
    return (json.load(open(neutron_services_filename)))


def test_lbaas_service_one_opflex_member(
        track_bigip_cfg, request, bigip, services, icd_config,
        icontrol_driver):
    env_prefix = icd_config['environment_prefix']
    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    fake_rpc = icontrol_driver.plugin_rpc
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())

    lb_pending = icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)
    assert not lb_pending
    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1

    # create member, node
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert lb_pending
    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 1

    # create member, node
    service = service_iter.next()
    lb_pending = icontrol_driver._common_service_handler(service)
    assert not lb_pending
    # Assert that update loadbalancer status was called once
    assert fake_rpc.get_call_count('update_loadbalancer_status') == 2
