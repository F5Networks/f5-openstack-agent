#!/usr/bin/env python
# Copyright (c) 2017,2018, F5 Networks, Inc.
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

import mock_builder_base_class

"""class_tester_base_class.py is a module hosting the ClassTesterBase

    This is a module hosting the base class for the ClassTesterBase and is used
    for testing purposes by having class testers inherit it.  These child
    classes then utilize the mock factory and the builder factory to set where
    in code space their black or white box tests begin and end.
"""


class ClassTesterBase(object):
    """An ABC for ClassTester objects that hold test_{method} methods

    This is a base class for ClassTester objects that contain test_{method} for
    the method within the target class.  Due to the limitations of pytest,
    there can only be one such class per test_{module}.py mirroring modules
    within production.

    Also due to the limitations of pytest, this ABC will contain a lot of
    fixtures that construct items that might otherwise be handled in
    MockBuilder classes.
    """
    builder = mock_builder_base_class.MockBuilderBase

    def list_currently_mocked(self):
        """A user-friendly pretty-printer of the current set of mocks given

        This is a tool built into the TesterClass meant for developers to list
        out the currently-implemented mocks within all targets.  This can be
        helpful for troubleshooting, but is not meant to replace the debugger.

        Always keep in mind that most mock_{method} methods have 'target' as
        an optional argument and will create their own target if needed.  This
        is meant to expand the flexiblity of the ClassTester class to include
        fixtures named after these mock_{method} methods.
        """
        # 'mock_builder, call_cnt, expected_args, target_mod, target_obj',
        # 'static'
        builder = self.my_builder
        items = builder.list_currently_mocked()
        print_fmt = """MockBuilder: {}
    MockObject: {}
TargetMod: {}
    TargetObj: {}
        ExpectedBehavior:
            call_cnt: {}
            expected_args: {}
            static: {}
===============================================================================
"""
        for item in items:
            print(
                print_fmt.format(
                    item.mock_builder, item.mock_object, item.target_mod,
                    item.target_obj, item.call_cnt, item.expected_args,
                    item.static))

    # fixtures:
    @pytest.fixture
    def standalone_builder(self):
        """Returns the test module used's MockBuilder's standalone builder

        This method will attempt to call the builder's standalone_builder's
        method to retrieve which builder it should use.  Either by factory or
        polymorphism, the MockBuilder should return which standalone_builder
        it uses.
        """
        standalone_builder = getattr(self, '_standalone_builder', None)
        if not standalone_builder:
            standalone_builder = self.builder.standalone_builder()
            self.my_builder = standalone_builder
        return standalone_builder

    @classmethod
    @pytest.fixture
    def neutron_only_builder(cls):
        """Returns the test module used's MockBuilder's neutron_only builder

        This method will attempt to call the builder's
        neutron_only_builder's method to retrieve which builder it should use.
        Either by factory or polymorphism, the MockBuilder should return which
        neutron_only_builder
        it uses.
        """
        return cls.builder.neutron_only_builder()

    @classmethod
    @pytest.fixture
    def bigip_only_builder(cls):
        """Returns the test module used's MockBuilder's bigip_only builder

        This method will attempt to call the builder's bigip_only_builder's
        method to retrieve which builder it should use.  Either by factory or
        polymorphism, the MockBuilder should return which bigip_only_builder
        it uses.
        """
        return cls.builder.bigip_only_builder()

    @classmethod
    @pytest.fixture
    def fully_int_builder(cls):
        """Returns the test module used's MockBuilder's fully_int builder

        This method will attempt to call the builder's fully_int_builder's
        method to retrieve which builder it should use.  Either by factory or
        polymorphism, the MockBuilder should return which fully_int_builder
        it uses.
        """
        return cls.builder.fully_int_builder()

    @classmethod
    @pytest.fixture
    def mocked_target(cls):
        return cls.handle_calling_my_builder(
            cls.my_builder.mocked_target)

    @pytest.fixture
    def fully_mocked_target(self):
        if hasattr(self, '_standalone_builder'):
            target = self._standalone_builder.new_fully_mocked_target()
        else:
            a_standalone = self.builder.standalone_builder()
            self._standalone_builder = a_standalone
            target = a_standalone.new_fully_mocked_target()
        return target

    @classmethod
    @pytest.fixture
    def service_with_network(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_network)

    @classmethod
    @pytest.fixture
    def service_with_loadbalancer(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_loadbalancer)

    @classmethod
    @pytest.fixture
    def service_with_listener(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_listener)

    @classmethod
    @pytest.fixture
    def service_with_l7_policy(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_l7_policy)

    @classmethod
    @pytest.fixture
    def service_with_pool(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_pool)

    @classmethod
    @pytest.fixture
    def service_with_health_monitor(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_health_monitor)

    @classmethod
    @pytest.fixture
    def service_with_policy(cls):
        return cls.handle_calling_builder(
            cls.builder.new_service_with_policy)

    # non-fixture based:
    @classmethod
    def handle_calling_builder(cls, my_classmethod):
        try:
            return my_classmethod()
        except AttributeError as error:
            if 'service_with' in str(error):
                raise AttributeError("Does your builder '{}' inheriting "
                                     "correctly for this fixture?"
                                     .format(cls.builder))
