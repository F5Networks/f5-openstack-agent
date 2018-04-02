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

import mock
import pytest

"""mock_builder_base_class is a host module for the MockBuilderBase

    This class hosts the means by which ClassTesters can have the
    functionality of a mock factory and builder factory.  This functionality
    allows ClassTesters the flexibility to allow developers to set where their
    tests begin and end within production code.

    Keep in mind that words like 'target' and 'target-space' is actually
    production code.  There should be (and if there isn't, create it) a
    MockBuilderBase-class object for all production modules' classes
    (one-for-one) to allow the mock-factory and builder-factory to work.
"""


class MockDataHolder(object):
    """Slot-driven data class whose instance holds the data around a Mock

    This is the class object that is used by MockBuilders to track what
    methods are mocked in target-space.
    """
    __slots__ = \
        ['_MockDataHolder__mock_builder', '_MockDataHolder__call_cnt',
         '_MockDataHolder__expected_args', '_MockDataHolder__target_mod',
         '_MockDataHolder__target_obj', '_MockDataHolder__static',
         '_MockDataHolder__mock_object']

    def __init__(self, mock_builder, call_cnt, expected_args, target_mod,
                 target_obj, static, mock_object):
        self.__mock_builder = mock_builder
        self.__call_cnt = call_cnt
        self.__expected_args = expected_args
        self.__target_mod = target_mod
        self.__target_obj = target_obj
        self.__static = static
        self.__mock_object = mock_object

    @property
    def __dict__(self):
        return dict(mock_builder=self.mock_builder, call_cnt=self.call_cnt,
                    expected_args=self.expected_args, static=self.static,
                    target_module=self.target_mod,
                    mock_object=self.mock_object,
                    target_object=self.target_obj)

    @property
    def mock_builder(self):
        """Recalls the MockBuilderClass object instance that made the mock"""
        return self.__mock_builder

    @property
    def target_mod(self):
        """Recalls the ProductionClass object instance that owns the mock"""
        return self.__target_mod

    @property
    def target_obj(self):
        """Realls the ProductionClass that owns the mock"""
        return self.__target_obj

    @property
    def call_cnt(self):
        """Recalls the number of times the mock is expected to be called"""
        return self.__call_cnt

    @property
    def expected_args(self):
        """Recalls the an expected set of arguments that the mock will get"""
        return self.__expected_args

    @property
    def static(self):
        """Recalls the static object instead of the mock (if static= given)"""
        return self.__static

    @property
    def mock_object(self):
        """Recalls the mock.Mock that was created (the mock itself)"""
        return self.__mock_object


class MockBuilderBase(object):
    """Base class for all MockBuilder classes

    A mock builder class is a builder class that is owned by the tester class.
    It is expected that each test module that is directly associated with a
    product-coded module have a builder class that hosts its mock methods for
    the mock factory.

    MockBuilders behave like a factory with the following characteristics:
      - When a builder is invoked to mock a method, it will climb down into
        the appropriate level of object extraction (mimicing production) to
        find the builder with the apprpriate mock
      - The mock is then added at that level, which means that the mimick'ed
        objects are using instantiated production class objects, which allows
        the caller to deem where their black-box is situated and ends

    NOTE: WIP - this is a 'build as needed' progress; thus, some mock builders
    are mis-named as ClassConstructors and inherited by their testers.  This
    needs to be changed to fit this framework to make things consistently
    follow this convenience.

    USERS:
        This object, being a base class, is expecting you to have an object
        that overloads the methods here that have NotImplementedError raises.
        With that said, to find out how this implementation works, you can
        utilize these methods by commenting out the raises and following the
        steps laid out in the method descriptions.
        Further notes:
            - Leave SToredExpectedMockResult alone
            - Create your own _other_builders
            - Create your own mock_{method}'s for the methods you need _ONLY_
                - These will fill themselves in nicely as other's have need
                - Only add mock_{method} methods that the builder's target has
                  - The branching algorithms should be improvded rather than
                    having one-offs
    """
    # unique to the ABC and should not be replicated or replaced!
    StoredExpectedMockResult = MockDataHolder
    # each MockBuilder should have a _other_builders dict:
    # <targets_prod_attr_name>: <prod_mirrored_MockBuilder>
    _other_builders = dict()

    def __init__(self, _your_name=None, _already_instantiated={}):
        """Instantiates a MockBuilderBase class"""
        # instantiate other_builders...
        self._construct_others(
            _my_name=_your_name, _already_instantiated=_already_instantiated)

    @property
    def __name__(self):
        return self._strip_class_name(self.__class__)

    @staticmethod
    def _strip_class_name(my_class):
        """Returns <class '(full.coded.path.to.Class)'> from the class str"""
        my_cls = str(my_class)
        my_cls.replace("<class '", '')
        my_cls.replace(">'", "")
        return my_cls

    def _construct_others(self, _my_name=None, _already_instantiated={}):
        """Instantiates the other_builders attribute's MockBuilderBases

        This is the crux to the polymorphism that is offered in the
        MockBuilderBase class.  It will, essentially, set up a tree of
        builders that is then later used to mock the appropraite class methods
        via the mock factory.
        """
        self.other_builders = self._other_builders.copy()
        others = self.other_builders
        for attr in _already_instantiated:
            instantiated = _already_instantiated[attr]
            if isinstance(instantiated, self.__class__):
                # recurse blow-up proofing...
                self.am_duplicate = instantiated
                return
            elif attr in others and \
                    isinstance(instantiated, others[attr]):
                self.other_builders[attr] = instantiated
            else:
                for other in others:
                    if isinstance(instantiated, others[other]):
                        others[other] = instantiated
        if _my_name:
            # second part of recurse blow-up proofing...
            _already_instantiated[_my_name] = self
        for attr in others:
            if not isinstance(others[attr], type):
                continue  # prevents attempting double instantiation TypeError
            my_builder = others[attr](
                _your_name=attr, _already_instantiated=_already_instantiated)
            if hasattr(my_builder, 'am_duplicate'):
                my_builder = my_builder.am_duplicate
            self.other_builders[attr] = my_builder
            _already_instantiated[attr] = my_builder

    # builder constructor methods (may need to eventually create constructor
    # classes...
    @classmethod
    @pytest.fixture
    def standalone_builder(cls):
        """This standalone builder will simply create an instance of the class

        This is a simple builder that will construct the MockBuilder of
        whatever type as a standalone_builder.  This means that the builder is
        not safe to use as a functional or fully-integrated test as defined by
        the caller via this fixture.
        """
        instantiated = cls()
        instantiated.builder_type = 'standalone'
        return instantiated

    @classmethod
    def neutron_only_builder(cls):
        """This neutron only builder will handle neutron if its configured

        This is a builder that handles neutron interactions via a REST client.
        """
        raise NotImplementedError("This ABC does not handle this currently")

    @classmethod
    def bigip_only_builder(cls):
        """This bigip only builder will handle bigip if its configured

        This is a builder that handles bigip interactions via a REST client.
        """
        raise NotImplementedError("This ABC does not handle this currently")

    @classmethod
    def fully_int_only_builder(cls):
        """This fully_int only builder will handle fully_int if its configured

        This is a builder that handles fully_int interactions via a REST
        client.
        """
        raise NotImplementedError("This ABC does not handle this currently")

    @staticmethod
    @pytest.fixture
    def mocked_target(*args):
        """Mocks just the __init__ in a prod-class to instantiate"""
        raise NotImplementedError("This is an ABCM example")
        # see test_agent_manager.TestLbaasAgentManagerMockBuilder.
        # mocked_target for an example...

    def fully_mocked_target(self, mocked_target):
        """An ABC method for fully_mocked_target

        This method should be filled in as this method is filled in but
        without the raise and by setting the target as a mocked instance of
        the target object in production.
        """
        raise NotImplementedError("This is an ABCM example")
        return mock.Mock()

    def new_fully_mocked_target(self):
        new_mocked_target = self.mocked_target()
        return self.fully_mocked_target(new_mocked_target)

    def mock_method(self, target, call_cnt=1, expected_args=[],
                    static=None, **kwargs):
        """An example mock_{method} ABC method

        This is an ABC providing an example.  As a developer, to see how this
        framework works, simply...
            1. Comment out the raise (but please do not commit the raise)
            2. Comment out the raise in self.fully_mocked_target method
            3. Do a pytest.set_trace at the beginning of this method
                a. The beginning of check_mocks()
                b. The beginning of fully_mocked_target()
            4. Do the following python code in this directory:
                import conftest
                foo = conftest.MockBuilder()
                target = foo.fully_mocked_target()
                foo.mock_method(target, 1, tuple([]))
                target.method()
                foo.check_mocks()

        A standard test within a TesterClass should simply use one of the
        following:
            - fully_mocked_target
            - partially_mocked_target
            - standalone_builder
            - neutron_only_builder
            - bigip_only_builder
            - fully_int_builder
        Please see the ABCM for these.

        NOTE: this ABCM type cannot be a fixture becuase the builder is
        factoried after pytest performs its fixture isolation at compile time.

        NOTE: due to this the attributes starting with '_mock_' are considered
        as part of the algorithm; thus, please do not overload this attr type.

        Additional Kwargs and their meanings (as children should follow):
            - call_cnt: the number of times the mocked method is called in
              production
            - expected_args: the expected args for at least one call within
              the production code during the test.  Note that this means that
              only one of the mocked-method's calls... see check_mocks() for
              how this is validated
            - static: A static value that will be used in favor over setting
              the mocked method to a mock.Mock
        """
        raise NotImplementedError("This is only an example")
        if not target:
            target = MockBuilderBase.fully_mocked_target()
        self._mockfactory(target.method, static, call_cnt, expected_args,
                          kwargs)
        return target

    def _mockfactory(self, target, method_name, static, call_cnt,
                     expected_args, kwargs):
        """A mock_{method} implementor class method

        This method will perform the different actions as a cookie-cutter
        functionality covering what most MockBuilder.mock_{method} methods
        should do.
        """
        # 'mock_builder, call_cnt, expected_args, target_mod, target_obj, '
        # 'static'
        mock_stored = method_name
        if method_name.startswith('_mock_'):
            method_name = method_name.replace('_mock_', '', 1)
        else:
            mock_stored = '_mock_{}'.format(method_name)

        target_mod = self._strip_class_name(target.__class__)

        stored_list = [
            self, call_cnt, expected_args, target_mod, target, static, None]
        if not static:
            my_mock = mock.Mock(**kwargs)
            if call_cnt or expected_args:
                if call_cnt:
                    stored_list[1] = call_cnt
                if expected_args:
                    stored_list[2] = call_cnt
            stored_list[6] = my_mock
            setattr(target, method_name, my_mock)
        else:
            setattr(target, method_name, static)
        stored = self.StoredExpectedMockResult(*stored_list)
        attr = getattr(self, mock_stored, None)
        if not attr:
            stored_set = set()
            stored_set.add(stored)
            setattr(self, mock_stored, stored_set)
        else:
            attr.add(mock_stored)

    def list_currently_mocked(self):
        """Returns a StoredExpectedMockResult of each mock intiiated to date

        This method drills down into each builder object that's been initiated
        and grabs the total list of mocks that exist thus far.

        Then returns this list.
        """
        def drill_down(builder, traversed=set()):
            if builder in traversed:
                return set(), set()
            mocks = set()
            traversed.add(builder)
            other_builders = getattr(builder, 'other_builders', dict())
            for attr in other_builders:
                if attr.startswith('_mock_'):
                    mocks.union(getattr(builder, attr))
                elif attr in builder.other_builders:
                    other = builder.other_builders[attr]
                    more_mocks, more_traversed = \
                        drill_down(other, traversed)
                    mocks.union(more_mocks)
                    traversed.union(more_traversed)
            return mocks, traversed

        mocks, traversed = drill_down(self)
        return list(mocks)

    def check_mocks(self, target, not_called=[]):
        """Checks runtime mocks by validating against expected items provided

        This method should be rarely overloaded by a child and hosts the
        functionality for callers to validate that their mocked methods were,
        indeed, called by production code using a simple line rather than
        pour into each method that was expected.  This does not work for
        mocks created by ClassMocker classes.

        This method takes no arguments, but is an instantiated instance of
        MockBuilder; thus some types of MockBuilder might not have this
        capability.

        Negative cases of mocks not being called.  Here, it was a hard
        decision to make that there should be a negative case checker;
        however, it was decided that since a test would fail otherwise at
        different levels than expected without this, to implement such a
        thing.

        NOTE: mocks that are given 'static' values are NOT tracked in any way.
        This DOES NOT include the return_value= or side_effect= flags for
        Mock.  This only impacts builder.mock_{method}(..., static=...)
        scenarios.  Thus, it is up to the caller to impelment the necessary
        foo to validate on their own either via other mocks or by their own
        logic.

        kwargs:
            not_called: a list of methods (as seen in prod) that were mocked,
                but were not expected to be called; thus, a
                mock.Mock.assert_not_called() will be run against the mock.
        """
        all_mocks = self.list_currently_mocked()
        for stored in all_mocks:
            try:
                if stored.expected_args:
                    stored.mock_object.assert_called_with(
                        stored.expected_args)
            except AssertionError:
                raise AssertionError(
                    "Expected '{}.{}' method to be called with '{}' args.  "
                    "Associated builder: '{}'".format(
                        stored.target_mod, stored.mocked_method,
                        stored.expected.expected_args, stored.mock_builder))
            try:
                if stored.call_cnt:
                    assert stored.mock_object.call_cnt == \
                        stored.expected_call_cnt
            except AssertionError:
                raise AssertionError(
                    "Expected '{}.{}' method to be called {} times.  Was "
                    "actually called {} times.  Impacted builder: {}".format(
                        stored.target_mod, stored.mocked_method,
                        stored.expected.call_cnt, stored.mock_builder))

    def mock_other_builders_method(self, target, method, targets_attr=None,
                                   exclude=[], **kwargs):
        """Factory manager method for this builder's abstraction for mockery

        This method will take a target and attempt to drill down into its
        attributes as set in self.other_builders and use that target's
        builder to call it's mock_{method} with the provided arguments.

        NOTE: this algorithm only drills down into MockBuilders provided in
        this builder's (and lowers') other_builders attribute (should be a
        dict of targets' attr name and associated MockBuilder classes)

        Special kwargs and their meaning:
            - targets_attr: if this is specified, then it will use this
              target's attr only and stop there.  An AttributeError is
              expected if this other does not exist in the target
            - exclude: excludes a given other from all levels.  This can be
              either a MockBuilder of the target level or a target's attr name
              for the production code-level
            - static: This is a static value that will be set in favor of
              a mock.  In this case, call_cnt and expected_args are ignored
            - call_cnt: see mock_method() AMBCM for details
            - expected_args: see mock_method() ABCM for details
            - mock.Mock kwargs: these can be given and will be forwarded
              onward
        """
        matched = 0
        first_level = True if not exclude else False
        if not method:
            raise ValueError("Please specify a method to be mocked...")
        if not method.startswith('mock_'):
            method = 'mock_{}'.format(method)
        if targets_attr:
            if targets_attr in self.other_builders:
                to_call = getattr(self.other_builders[targets_attr], method)
                others_target = getattr(target, targets_attr)
                to_call(others_target, **kwargs)
                matched += 1
        else:
            exclude.append(self)
            for builder_key in self.other_builders:
                builder = self.other_builders[builder_key]
                if builder_key in exclude or builder in exclude:
                    # prevent recursive explosion:
                    continue
                to_call = getattr(builder, method, None)
                if to_call:
                    matched += 1
                    to_call(target, **kwargs)
                other_target = getattr(target, builder_key)
                matched += builder.mock_other_builders_method(
                    other_target, method, exclude=exclude, **kwargs)
        if not matched and first_level:
            raise NotImplementedError(
                "'{}' does not have an other_builder with method '{}'".format(
                    target, method))
        return matched
