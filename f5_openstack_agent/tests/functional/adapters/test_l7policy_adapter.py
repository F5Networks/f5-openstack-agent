# coding=utf-8
# Copyright 2016 F5 Networks Inc.
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


# Running these tests:
# 1. Create a symbols file (.json or .yaml)
#       fill in bigip_ip, bigip_username, and bigip_password
# 2. From this directory run:
#       py.test --symbols=<symbols_file> test_l7policy_adapter.py

from f5_openstack_agent.lbaasv2.drivers.bigip import l7policy_adapter

import json
import mock
import os
import pytest

curdir = os.path.dirname(os.path.realpath(__file__))
POL_CONFIGS = json.load(open(os.path.join(curdir, 'policy_rules.json')))


@pytest.fixture
def fake_conf():
    mc = mock.MagicMock(name='fake_conf')
    mc.environment_prefix = 'Project'
    return mc


@pytest.fixture
def partition_setup(request, bigip):
    def teardown():
        if bigip.tm.sys.folders.folder.exists(name='Project_test'):
            partition = bigip.tm.sys.folders.folder.load(name='Project_test')
            partition.delete()
    request.addfinalizer(teardown)
    bigip.tm.sys.folders.folder.create(name='Project_test', subPath='/')


@pytest.fixture()
def policy_setup(request, bigip, partition_setup):
    pool = bigip.tm.ltm.pools.pool
    pol = bigip.tm.ltm.policys.policy
    pool_kwargs = {'name': 'Project_test_pool', 'partition': 'Project_test'}
    pol_kwargs = {'name': 'wrapper_policy', 'partition': 'Project_test'}

    def teardown():
        if pol.exists(**pol_kwargs):
            test_pol = pol.load(**pol_kwargs)
            test_pol.delete()
        if pool.exists(**pool_kwargs):
            test_pool = pool.load(**pool_kwargs)
            test_pool.delete()
    request.addfinalizer(teardown)
    pool.create(**pool_kwargs)


def test_adapter_reject_beginswith(bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['reject_path'])
    assert pol == {
        'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'ordinal': 1, 'conditions': [
                    {
                        'values': [u'/api'], 'httpUri': True, 'name': '0',
                        'startsWith': True, 'request': True, 'path': True
                    }
                ],
                'name': u'reject_1', 'actions': [
                    {
                        'request': True, 'name': '0', 'reset': True,
                        'forward': True
                    }
                ]
            }],
        'partition': u'Project_test',
        'name': 'wrapper_policy', 'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_pool_file_type_beginswith(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_pool_file_type'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'forward': True, 'name': 0, 'request': True,
                        'pool': u'/Project_test/Project_test_pool'
                    }
                ],
                'conditions': [
                    {
                        'startsWith': True, 'extension': True, 'httpUri': True,
                        'request': True, 'values': [u'txt'], "name": '0'
                    }
                ],
                'name': u'redirect_to_pool_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_url_cookie_contains(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_url_cookie'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'name': '0', 'redirect': True,
                        'location': u'http://www.example.com',
                        'httpReply': True, 'request': True
                    }
                ],
                'conditions': [
                    {
                        'contains': True, 'httpCookie': True, 'request': True,
                        'values': [u'test_cookie'], 'name': '0',
                        'tmName': 'cookie', 'request': True
                    }
                ],
                'name': u'redirect_to_url_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_url_header_ends_with(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_url_header'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'request': True, 'name': '0', 'httpReply': True,
                        'redirect': True, 'location': 'http://www.example.com'
                    }
                ],
                'conditions': [
                    {
                        'endsWith': True, 'request': True, 'httpHeader': True,
                        'values': [u'test_header'], 'name': '0',
                        'tmName': 'X-HEADER'
                    }
                ],
                'name': u'redirect_to_url_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_pool_hostname_equal_to(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_pool_hostname'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'request': True, 'name': '0', 'forward': True,
                        'pool': '/Project_test/Project_test_pool'
                    }
                ],
                'conditions': [
                    {
                        'equals': True, 'request': True, 'httpHost': True,
                        'values': [u'10.10.10.10'], 'name': '0', 'host': True
                    }
                ],
                'name': u'redirect_to_pool_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_pool_many_rules(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_pool_many_rules'])
    assert pol == \
        {
            "controls": ["forwarding"],
            "legacy": True,
            "name": "wrapper_policy",
            "partition": "Project_test",
            "requires": ["http"],
            "rules": [{
                "actions": [{
                    "forward": True,
                    "name": "0",
                    "pool": "/Project_test/Project_test_pool",
                    "request": True
                }],
                "conditions": [{
                    "equals": True,
                    "httpHeader": True,
                    "name": "0",
                    "request": True,
                    "tmName": "X-HEADER",
                    "values": ["test_header"]
                }, {
                    "contains": True,
                    "httpCookie": True,
                    "name": "1",
                    "request": True,
                    "tmName": "cookie",
                    "values": ["test_cookie"]
                }, {
                    "httpUri": True,
                    "name": "2",
                    "path": True,
                    "request": True,
                    "startsWith": True,
                    "values": ["/api/cool/site"]
                }],
                "name": "redirect_to_pool_1",
                "ordinal": 1
            }],
            "strategy": "first-match"
        }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_many_policies_rules(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['many_policies_and_rules'])
    from pprint import pprint
    pprint(pol)
    assert pol == \
        {
            "controls": ["forwarding"],
            "legacy": True,
            "name": "wrapper_policy",
            "partition": "Project_test",
            "requires": ["http"],
            "rules": [{
                "actions": [{
                    "forward": True,
                    "name": "0",
                    "pool": "/Project_test/Project_test_pool",
                    "request": True
                }],
                "conditions": [{
                    "equals": True,
                    "httpHeader": True,
                    "name": "0",
                    "request": True,
                    "tmName": "X-HEADER",
                    "values": ["test_header"]
                }, {
                    "contains": True,
                    "httpCookie": True,
                    "name": "1",
                    "request": True,
                    "tmName": "cookie",
                    "values": ["test_cookie"]
                }],
                "name": "redirect_to_pool_1",
                "ordinal": 1
            }, {
                "actions": [{
                    "forward": True,
                    "name": "0",
                    "request": True,
                    "reset": True
                }],
                "conditions": [{
                    "httpUri": True,
                    "name": "0",
                    "path": True,
                    "request": True,
                    "startsWith": True,
                    "values": ["/api/cool/site"]
                }],
                "name": "reject_2",
                "ordinal": 2
            }, {
                "actions": [{
                    "forward": True,
                    "name": "0",
                    "request": True,
                    "reset": True
                }],
                "conditions": [],
                "name": "reject_3",
                "ordinal": 3
            }, {
                "actions": [{
                    "httpReply": True,
                    "location": "http://www.example.com",
                    "name": "0",
                    "request": True,
                    "redirect": True
                }],
                "conditions": [],
                "name": "redirect_to_url_4",
                "ordinal": 4
            }],
            "strategy": "first-match"
        }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_pool_hostname_not_equal_to(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_pool_hostname_invert'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'request': True, 'name': '0', 'forward': True,
                        'pool': '/Project_test/Project_test_pool'
                    }
                ],
                'conditions': [
                    {
                        'equals': True, 'request': True, 'httpHost': True,
                        'values': [u'10.10.10.10'], 'name': '0', 'host': True,
                        'not': True
                    }
                ],
                'name': u'redirect_to_pool_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_reject_not_beginswith(bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['reject_not_path'])
    assert pol == {
        'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'ordinal': 1, 'conditions': [
                    {
                        'values': [u'/api'], 'httpUri': True, 'name': '0',
                        'startsWith': True, 'request': True, 'path': True,
                        'not': True
                    }
                ],
                'name': u'reject_1', 'actions': [
                    {
                        'request': True, 'name': '0',
                        'reset': True, 'request': True, 'forward': True
                    }
                ]
            }],
        'partition': u'Project_test',
        'name': 'wrapper_policy', 'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_pool_file_type_not_beginswith(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_pool_not_file_type'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'forward': True, 'name': 0, 'request': True,
                        'pool': u'/Project_test/Project_test_pool'
                    }
                ],
                'conditions': [
                    {
                        'startsWith': True, 'extension': True, 'httpUri': True,
                        'request': True, 'values': [u'txt'], "name": '0',
                        'not': True
                    }
                ],
                'name': u'redirect_to_pool_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_url_cookie_not_contains(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_url_not_cookie'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'name': '0', 'redirect': True,
                        'location': u'http://www.example.com',
                        'httpReply': True, 'request': True
                    }
                ],
                'conditions': [
                    {
                        'contains': True, 'httpCookie': True, 'request': True,
                        'values': [u'test_cookie'], 'name': '0',
                        'tmName': 'cookie', 'request': True, 'not': True
                    }
                ],
                'name': u'redirect_to_url_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_redirect_to_url_header_not_ends_with(
        bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(POL_CONFIGS['redirect_to_url_not_header'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'request': True, 'name': '0', 'httpReply': True,
                        'redirect': True, 'location': 'http://www.example.com'
                    }
                ],
                'conditions': [
                    {
                        'endsWith': True, 'request': True, 'httpHeader': True,
                        'values': [u'test_header'], 'name': '0',
                        'tmName': 'X-HEADER', 'not': True
                    }
                ],
                'name': u'redirect_to_url_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)


def test_adapter_remove_rule(bigip, fake_conf, policy_setup):
    adapter = l7policy_adapter.L7PolicyServiceAdapter(fake_conf)
    pol = adapter.translate(
        POL_CONFIGS['redirect_to_url_not_header_remove_rule'])
    assert pol == {
        'name': 'wrapper_policy', 'partition': u'Project_test', 'legacy': True,
        'requires': ['http'], 'controls': ['forwarding'],
        'rules': [
            {
                'actions': [
                    {
                        'request': True, 'name': '0', 'httpReply': True,
                        'redirect': True, 'location': 'http://www.example.com'
                    }
                ],
                'conditions': [],
                'name': u'redirect_to_url_1', 'ordinal': 1
            }
        ],
        'strategy': 'first-match'
    }
    bigip.tm.ltm.policys.policy.create(**pol)
