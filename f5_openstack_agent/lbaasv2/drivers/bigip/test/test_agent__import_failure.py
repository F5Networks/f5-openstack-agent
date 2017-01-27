##!/usr/bin/env python
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

# import pytest

# needs to be run first for capture of 'success' for test_import
success = False
agent = None  # if importation works, then this will be defined as not None
try:
    import builtins
except ImportError:
    import __builtin__ as builtins
real_import = builtins.__import__


def my_custom_import(*args):
    if 'oslo_config' in args:
        raise ImportError('foodogzoo')
    return real_import(*args)


builtins.__import__ = my_custom_import
# get our test scenario:
try:
    import f5_openstack_agent.lbaasv2.drivers.bigip.agent as agent
    assert not agent, "No agent test"  # makes tox style happy...
except SystemExit:
    success = True
builtins.__import__ = real_import


def test_import():
    assert success, "Import Test"
