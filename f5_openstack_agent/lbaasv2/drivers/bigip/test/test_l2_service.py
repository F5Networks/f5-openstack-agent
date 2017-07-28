#!/usr/bin/env python
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

import pytest

from mock import Mock
from mock import patch

from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    L2ServiceBuilder


class Test_L2ServiceBuilder(object):
    """Performs tests against L2ServiceBuilder

    The beginning variable assignments should reflect the items that should be
    rotated back to their original values in code-space in the teardown()
    method.  All items that are manipulated to mocks initially should be
    performed in a fixture method when repeated.
    """

    @pytest.fixture(autouse=True)
    def create_self(self, request):
        """Creates a 'blank' L2ServiceBuilder instance in self

        This method is executed for every test method during runtime.
        """
        request.addfinalizer(self.teardown)

        # create our fake driver object...
        self.driver = Mock()
        self.driver.conf = Mock()
        force_false = ['vlan_binding_driver']
        list_vars = ['f5_external_physical_mappings']
        for item in force_false:
            setattr(self.driver.conf, item, False)
        for item in list_vars:
            setattr(self.driver.conf, item, list())

        # set our mocks...
        self.system_helper = Mock()
        self.network_helper = Mock()
        self.service_model_adopter = Mock()
        self.f5_global_routed_mode = Mock()
        args = [self.driver, self.f5_global_routed_mode]

        NetworkHelper = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l2_service.'
                'NetworkHelper')
        ServiceModelAdapter = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l2_service.'
                'ServiceModelAdapter')
        SystemHelper = \
            str('f5_openstack_agent.lbaasv2.drivers.bigip.l2_service.'
                'SystemHelper')
        with patch(SystemHelper, self.system_helper, create=True):
            with patch(ServiceModelAdapter, self.service_model_adopter,
                       create=True):
                with patch(NetworkHelper, self.network_helper, create=True):
                    self.l2_service_builder = L2ServiceBuilder(*args)

    def test__init__(self):
        """tests the target's __init__ method"""
        # tests based on basic object creation from self.create_self():
        assert self.l2_service_builder.driver is self.driver, \
            "Driver provisioning test"
        assert self.l2_service_builder.conf is self.driver.conf, \
            "Dirver conf provisioning test"
        assert self.l2_service_builder.f5_global_routed_mode is \
            self.f5_global_routed_mode, \
            "f5_global_routed_mode provisioning test"
        self.system_helper.assert_called_once_with()
        self.network_helper.assert_called_once_with()
        self.service_model_adopter.assert_called_once_with(self.driver.conf)

        # further tests needed:
        # add tests for...
        #   - f5_external_physical_mappings assignment test
        #   - vlan_binding_driver assignment/importation test
        # Suggest a refactor for implementing the above in unit tests...

    def teardown(self):
        """Tears down the code space variables returning code state."""
        pass

    def test_is_common_network(self):
        """Tests the target's is_common_network() method"""
        target = self.l2_service_builder
        network = {"shared": True, "id": "foodogzoo", "router:external": True,
                   }
        setattr(target.conf, "f5_common_external_networks", True)
        setattr(target.conf, "common_network_ids", ['foodogzoo'])
        setattr(target.conf, "f5_common_networks", True)
        # network['shared'] condition
        assert target.is_common_network(network), "shared test"
        # self.conf.f5_common_networks condition
        network['shared'] = False
        assert target.is_common_network(network), "f5_common_networks test"
        # self.conf.f5_common_external_networks condition
        setattr(target.conf, "f5_common_networks", False)
        assert target.is_common_network(network), \
            "f5_common_external_networks test"
        setattr(target.conf, "f5_common_external_networks", False)
        target.conf.common_network_ids.pop()
        assert not target.is_common_network(network), \
            "f5_common_external_networks negative test"
        setattr(target.conf, "f5_common_external_networks", True)
        assert target.is_common_network(network), \
            "f5_common_network_ids negative test"
        target.conf.f5_common_network_ids.push('foodogzoo')
        network['router:external'] = False
        assert not target.is_common_network(network), \
            "network['reouter:external'] negative test"
        del network['router:external']
        assert not target.is_common_network(network), \
            "No 'reouter:external' network 'negative' test"
