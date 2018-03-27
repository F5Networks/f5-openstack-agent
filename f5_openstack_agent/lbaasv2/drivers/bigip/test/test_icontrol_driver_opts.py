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

import re

import f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver as target

import oslo_config.cfg as cfg

opts = target.OPTS

# For new entries, put the expected default and help=True or False for whether
# it should have a help statement.
expected = {'f5_common_networks': dict(default=False, help=True),
            'external_gateway_mode': dict(defualt=False, help=True)}


def test_opts_type():
    """Check that all opts are a oslo_config.cfg.* object"""
    type_check = re.compile('oslo_config\.cfg\.(\w+Opt)')
    for opt in opts:
        match = type_check.search(str(opt))
        assert match, str("{} is not recognized as a oslo_config.cfg.*"
                          " object!").format(opt)
        assert hasattr(cfg, match.group(1)), \
            str("{} is not a subclass of oslo_config.cfg").format(opt)


def test_expected():
    """test_expected - goes through the expected and validates

    This test function will run through the expected dict and attempt to
    determine that:
    -   'key' is in the collected opts from build time
    -   opts[x].name == 'key'
    -   opts[x].help exits if expected['key']['help'] exists
    -   opts[x].default == expected['key']['default']
    This may not yet reflect all options in the opts; however, it should
    reflect newly-added items.
    """
    global expected
    collected = dict()
    for opt in opts:
        if opt.name in expected:
            collected[opt.name] = opt
    for exp_name in expected:
        assert exp_name in collected, "{} not found in opts!".format(exp_name)
        exp_result = expected[exp_name]
        opt = collected[exp_name]
        assert opt.help or not exp_result['help'], "{} help test".format(
            exp_name)
        if 'default' in exp_result:
            assert opt.default == exp_result['default'], \
                "{} default test".format(exp_name)
