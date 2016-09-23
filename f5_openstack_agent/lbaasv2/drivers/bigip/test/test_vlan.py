# coding=utf-8
# Copyright 2014-2016 F5 Networks Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper

from f5.bigip.tm.net.vlan import TagModeDisallowedForTMOSVersion

import mock
import pytest


tagged_vlan_no_int = {'name': "test_valan",
                      'partition': "Project_123456789",
                      'tag': 1000}


class TestVLANCreate(object):

    @pytest.fixture
    def bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.net.vlans.vlan = mock.MagicMock()
        bigip.tm.net.vlans.vlan.exists.return_value = True

        return bigip

    @pytest.fixture
    def network_helper(self):
        nh = NetworkHelper()
        nh.get_route_domain_by_id = mock.MagicMock(return_value=0)

        return nh

    def test_create_vlan_no_name(self, bigip, network_helper):
        tagged_vlan_no_name = {'partition': "Project_123456789"}

        vlan = network_helper.create_vlan(bigip, tagged_vlan_no_name)

        assert(vlan is None)

    def test_create_vlan_exists(self, bigip, network_helper):
        tagged_vlan_no_int = {'name': "test_vlan",
                              'partition': "Project_123456789",
                              'tag': 1000}

        v = network_helper.create_vlan(bigip, tagged_vlan_no_int)

        assert(v is not None)

        bigip.tm.net.vlans.vlan.exists.assert_called_once_with(
            name='test_vlan', partition='Project_123456789')
        bigip.tm.net.vlans.vlan.load.assert_called_once_with(
            name='test_vlan', partition='Project_123456789')

    def test_create_vlan_no_int(self, bigip, network_helper):

        tagged_vlan_no_int = {'name': "test_vlan",
                              'partition': "Project_123456789",
                              'tag': 1000}

        bigip.tm.net.vlans.vlan.exists.return_value = False

        v = network_helper.create_vlan(bigip, tagged_vlan_no_int)

        assert(v is not None)

        bigip.tm.net.vlans.vlan.create.assert_called_once_with(
            name='test_vlan', partition='Project_123456789', tag=1000)

    def test_create_vlan_with_untagged_int(self, bigip, network_helper):

        vlan_with_untagged_int = {'name': "test_vlan",
                                  'partition': "Project_123456789",
                                  'interface': "1.3"}

        bigip.tm.net.vlans.vlan.exists.return_value = False
        bigip.tm.net.vlans.vlan.create.return_value = (
            bigip.tm.net.vlans.vlan)

        v = network_helper.create_vlan(bigip, vlan_with_untagged_int)

        bigip.tm.net.vlans.vlan.create.assert_called_once_with(
            name='test_vlan', partition='Project_123456789', tag=0)

        v.interfaces_s.interfaces.create.assert_called_with(
            name='1.3', untagged=True)

    def test_create_vlan_with_tagged_int(self, bigip, network_helper):

        vlan_with_untagged_int = {'name': "test_vlan",
                                  'partition': "Project_123456789",
                                  'tag': 1000,
                                  'interface': "1.3"}

        bigip.tm.net.vlans.vlan.exists.return_value = False
        bigip.tm.net.vlans.vlan.create.return_value = (
            bigip.tm.net.vlans.vlan)

        v = network_helper.create_vlan(bigip, vlan_with_untagged_int)

        bigip.tm.net.vlans.vlan.create.assert_called_once_with(
            name='test_vlan', partition='Project_123456789', tag=1000)

        v.interfaces_s.interfaces.create.assert_called_with(
            name='1.3', tagged=True, tagMode="service")

    def test_create_vlan_with_tagged_int_11_5(self, bigip, network_helper):

        vlan_with_untagged_int = {'name': "test_vlan",
                                  'partition': "Project_123456789",
                                  'tag': 1000,
                                  'interface': "1.3"}

        bigip.tm.net.vlans.vlan.exists.return_value = False
        bigip.tm.net.vlans.vlan.create.return_value = (
            bigip.tm.net.vlans.vlan)
        bigip.tm.net.vlans.vlan.interfaces_s.interfaces.create.side_effect = (
            [TagModeDisallowedForTMOSVersion, None]
        )

        v = network_helper.create_vlan(bigip, vlan_with_untagged_int)

        bigip.tm.net.vlans.vlan.create.assert_called_once_with(
            name='test_vlan', partition='Project_123456789', tag=1000)

        call_count = v.interfaces_s.interfaces.create.call_count
        v.interfaces_s.interfaces.create.assert_called_with(
            name='1.3', tagged=True)
        assert(call_count == 2)
