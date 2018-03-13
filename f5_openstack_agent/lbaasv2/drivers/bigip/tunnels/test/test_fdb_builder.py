"""Handles testing of the fdb_builder.py production module

This module's target-under-test, or fdb_builder.py, hosts the FdbBuilder
object.  This builder object constructs, orchestrates, and delivers Fdb
objects.

Thus, this test module handles all items surrounding the direct testing of
FdbBuilder.
"""
# Copyright 2018 F5 Networks Inc.
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

import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.fdb as fdb

from ...test.class_tester_base_class import ClassTesterBase
from ...test.mock_builder_base_class import MockBuilderBase

target_mod = 'f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.fdb.FdbBuilder'


class TestFdbMockBuilder(MockBuilderBase):
    """This is the MockBuilder for the Fdb object

    This follows the standard mock factory framework for unit testing in the
    agent.
    """
    @mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.fdb.'
                'Fdb.__init__')
    def mocked_target(self, init):
        """Creates and returns a mocked Fdb object"""
        init.return_value = None
        return fdb.Fdb()

    def fully_mocked_target(self, mocked_target):
        """Creates and returns a fully mocked Fdb object"""
        mocked_target._Fdb__ip_address = '192.168.1.6'
        mocked_target._Fdb__segment_id = 33
        mocked_target._Fdb__mac_address = 'ma:ca:dd:re:ss:es'
        mocked_target._Fdb__vtep_ip = '10.22.22.6'
        mocked_target._Fdb__network_type = 'vxlan'
        return mocked_target

    def set_network_id(self, target, network_id):
        """Wrapper to set the target's network_id bypassing prod"""
        target._Fdb__network_id = network_id

    def set_network_type(self, target, m_type):
        """Wrapper to set the target's network_type bypassing prod"""
        target._Fdb__network_type = m_type


class TestFdbBuilderMockBuilder(MockBuilderBase):
    """This is the MockBuilder for the FdbBuilder object

    This is not you're typical MockBuilder in that the other_builders of
    modules that use this are actually still referencing the code-space
    methods.  These can be, and will be mocked; however, there is a chance
    that a cross-reference will occur with this builder; thus, its destructor
    will not be called.  In that instance, the mocks are not cleared nor are
    the mock holder cleaned.  This WILL result in test pollutions.  Please
    read logged instructions below for troubleshoot this occurence.
    """
    def __init__(self, **kwargs):
        # freeze all of the target class's methods for later thaw
        print("""
Lucky you!  You're in the process of using FdbBuilder's MockBuilder!  Please
look for a 'Destroying FdbBulder' line to be printed at the end of your test.
If you don't, you're leaving cruft behind, and the framework is failing you...
Take a look at python's gc library.  Essentially, you'll want to drop into
the debugger just before the teardown of your test (end) and place a
pytest.set_trace(), then run again.  When you get to the debug screen, you'll
want to execute gc.get_referrers(builder).  This will return a list of
referrers that point to the builder... there should only be 1 that is not a
weakref.  If there are more, then the builder will not destruct properly.
""")
        super(TestFdbBuilderMockBuilder, self).__init__(**kwargs)
        self.freeze_target = dict()
        for attr in dir(fdb.FdbBuilder):
            self.freeze_target[attr] = getattr(fdb.FdbBuilder, attr)

    def __del__(self):
        # This object is factory-ing for a class-based library class that
        # should never be instantiated under test (or ever); thus, this needs
        # to be delicately handled to restore the class perminently to what it
        # was before testing...  This is in case someone decides not to use
        # the mock factory and does not handle their mock-restore properly.
        # Restore our frozen code under test that needs it
        print("Destroying {}".format(self.__class__))
        for attr in self.freeze_target:
            target = self.freeze_target.get(attr)
            if getattr(fdb.FdbBuilder, attr) is not target:
                setattr(fdb.FdbBuilder, attr, self.freeze_attr[attr])
        # Destroy all mock handles from factory...
        for attr in dir(fdb.FdbBuilder):
            if 'mock' in attr:
                delattr(fdb.FdbBuilder, attr)

    @mock.patch(target_mod + '.__init__')
    def mocked_target(self, init):
        """This will generate an instance of FdbBuilder

        As the code-under test here is a Builder object, only local tests
        might use this appropriately... this is due to the fact that the
        code-under test inhibits actual instantiation in production.
        """
        init.return_value = None
        target = fdb.FdbBuilder()
        return target

    def fully_mocked_target(self, mocked_target):
        """Generates a fully_mocked_target of FdbBuilder

        As the code-under test here is a Builder object, only local tests
        might use this appropriately... this is due to the fact that the
        code-under test inhibits actual instantiation in production.

        Note that as such, this returned target will not have any working
        attributes added, but instead, will simply be a good entry point for
        test methods.
        """
        return mocked_target

    def teardown(self):
        """This is picked up at the class_tester_base_class's fixture

        This method will attempt to execute teardowns on all MockBuilders.
        """
        self.__del__()
        super(TestFdbBuilderMockBuilder, self).teardown()


class TestFdbMocker(object):
    pass


class TestFdb(ClassTesterBase, TestFdbMocker):
    _builder = TestFdbBuilderMockBuilder
    pass
