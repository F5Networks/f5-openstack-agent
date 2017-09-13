# coding=utf-8
# Copyright 2017 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from f5_openstack_agent.lbaasv2.drivers.bigip import agent_manager

import mock
import pytest


@pytest.fixture
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager.'
            'LbaasAgentManager._setup_rpc')
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager.'
            'importutils.import_object')
def agent_mgr_setup(mock_importutils, mock_setup_rpc):
    return agent_manager.LbaasAgentManager(mock.MagicMock(name='conf'))


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager.LOG')
def test_update_fdb_entries(mock_log, agent_mgr_setup):
    '''When func is called in agent_manager, it prooduces a warning message.'''

    agent_mgr_setup.update_fdb_entries('', '')
    warning_msg = "update_fdb_entries: the LBaaSv2 Agent does not handle an " \
        "update of the IP address of a neutron port. This port is generally " \
        "tied to a member. If the IP address of a member was changed, be " \
        "sure to also recreate the member in neutron-lbaas with the new " \
        "address."
    assert mock_log.warning.call_args == mock.call(warning_msg)
