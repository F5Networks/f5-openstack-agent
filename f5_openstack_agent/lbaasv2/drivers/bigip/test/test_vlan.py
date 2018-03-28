# coding=utf-8
# Copyright (c) 2014-2018, F5 Networks, Inc.
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


class TestVLANCreate(object):

    @pytest.fixture
    def bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.net.vlans.vlan = mock.MagicMock()
        bigip.tm.net.vlans.vlan.exists.return_value = True

        return bigip

    @pytest.fixture
    def network_helper(self, bigip):
        nh = NetworkHelper()
        nh.get_route_domain_by_id = mock.MagicMock(
            return_value=bigip.tm.net.route_domains.route_domain)

        return nh

    def test_create_vlan_no_name(self, bigip, network_helper):
        """Assert that if name is not in model that returned vlan none."""
        tagged_vlan_no_name = {'partition': "Project_123456789"}

        vlan = network_helper.create_vlan(bigip, tagged_vlan_no_name)

        assert(vlan is None)

    def test_create_vlan_exists(self, bigip, network_helper):
        """Test vlan_create with preexisting vlan.

        Assert that if vlan already exists that vlan create
        is not performed.

        """

        tagged_vlan_no_int = {'name': "test_vlan",
                              'partition': "Project_123456789",
                              'tag': 1000}

        v = network_helper.create_vlan(bigip, tagged_vlan_no_int)

        assert(v is not None)

        bigip.tm.net.vlans.vlan.exists.assert_called_once_with(
            name='test_vlan', partition='Project_123456789')
        bigip.tm.net.vlans.vlan.load.assert_called_once_with(
            name='test_vlan', partition='Project_123456789')
        bigip.tm.net.vlans.vlan.create.assert_not_called

    def test_create_vlan_no_int(self, bigip, network_helper):
        """Test vlan_create with model without interface.

        1) Assert that create vlan returns a vlan object.
        2) Assert that the vlan was created.

        """
        tagged_vlan_no_int = {'name': "test_vlan",
                              'partition': "Project_123456789",
                              'tag': 1000}

        bigip.tm.net.vlans.vlan.exists.return_value = False

        v = network_helper.create_vlan(bigip, tagged_vlan_no_int)

        assert(v is not None)

        bigip.tm.net.vlans.vlan.create.assert_called_once_with(
            name='test_vlan', partition='Project_123456789', tag=1000)

    def test_create_vlan_with_untagged_int(self, bigip, network_helper):
        """Test vlan create when model contains untagged interface.

        1) Assert that create vlan is only called once.
        2) Assert that create vlan called once with expected args.

        """

        vlan_with_untagged_int = {'name': "test_vlan",
                                  'partition': "Project_123456789",
                                  'interface': "1.3"}

        bigip.tm.net.vlans.vlan.exists.return_value = False
        bigip.tm.net.vlans.vlan.create.return_value = (
            bigip.tm.net.vlans.vlan)

        v = network_helper.create_vlan(bigip, vlan_with_untagged_int)

        bigip.tm.net.vlans.vlan.create.assert_called_once_with(
            name='test_vlan', partition='Project_123456789', tag=0)

        v.interfaces_s.interfaces.create.assert_called_once_with(
            name='1.3', untagged=True)

    def test_create_vlan_with_tagged_int(self, bigip, network_helper):
        """Test vlan create when model contains tagged interface.

        1) Assert that create vlan is only called once with
        expected args.

        2) Assert that create vlan interface called once with
        expected args.

        """

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
            name='1.3', tagged=True)

    def test_create_vlan_with_tagged_int_11_5(self, bigip, network_helper):
        """Test vlan create when model contains tagged interface (TMOS 11.5)

        1) Assert that create vlan is only called once with
        expected args.

        2) Assert that create vlan interface called once with
        expected args not including tagMode.
        3) The first call to create vlan interface results in exception
        that is caught.
        4) The subsequent call to create vlan interface does not have
        tagMode and does not result in exception

        """

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
        call_list = v.interfaces_s.interfaces.create.call_args_list

        # Ensure that the create v.interfaces_s.interfaces.create
        # is called only twice.
        assert(call_count == 2)

        # Check that tagMode was not used in first call
        args, kwargs = call_list[0]
        assert("tagMode" not in kwargs)

        # Check that tagMode was not used in second call.
        args, kwargs = call_list[1]
        assert("tagMode" not in kwargs)
