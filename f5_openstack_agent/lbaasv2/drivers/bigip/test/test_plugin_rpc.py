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
import uuid

from mock import Mock
from mock import patch

import oslo_messaging as messaging

import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 as constants
import f5_openstack_agent.lbaasv2.drivers.bigip.plugin_rpc as target_mod

import class_tester_base_class
import mock_builder_base_class


class TestPluginRpcMockBuilder(mock_builder_base_class.MockBuilderBase):
    """Builder class for Mock objects that mock LBaaSv2PluginRPC

    This class builds mock-module class objects for isolation of the
    LbaasAgentManager.  As such, all reference to `target` are pointing to
    either an instantiated instance of LBaaSv2PluginRPC or is a mocked
    instance of this class.

    Use:
        class Tester(object):
            my_mock_builder = TestLBaaSv2PluginRPCMockBuilder
            standalone = TestLBaaSv2PluginRPCMockBuilder.standalone
            neutron_only = TestLBaaSv2PluginRPCMockBuilder.neutron_only
            bigip_only = TestLBaaSv2PluginRPCMockBuilder.bigip_only
            fully_int = TestLBaaSv2PluginRPCMockBuilder.fully_int
            fixture = my_mock_builder.fixture

            def test_foo(fixture):
                # this then uses the pytest.fixture fixture from MockBuilder
    """
    # non-instantiated original:
    _other_builders = dict()

    @staticmethod
    @patch('f5_openstack_agent.lbaasv2.drivers.bigip.plugin_rpc.'
           'LBaaSv2PluginRPC.__init__')
    def mocked_target(init):
        init.return_value = None
        return target_mod.LBaaSv2PluginRPC()

    def fully_mocked_target(self, mocked_target):
        """Creates a mocked target that mocks all lower other_builders' targets

        This does not mean that the caller's black-box is limited to this
        target, but can drill further using a system of either mocks or
        non-mocks.  Please see conftest.MockBuilder for details.
        """
        # instantiate other_builders...
        self._construct_others()
        mocked_target.topic = None
        mocked_target.target = Mock()  # replace with logic for icontrol mocker
        mocked_target._client = Mock()  # replace with icontrol mocker later...
        mocked_target.context = 'context'
        mocked_target.env = 'env'
        mocked_target.group = 'group'
        mocked_target.host = 'host'
        return mocked_target

    def mock_get_clusterwide_agent(self, target=None, call_cnt=1,
                                   expected_args=None, static=None, **kwargs):
        """mocks LBaaSv2PluginRPC.get_clusterwide_agent method

        This will mock the method in the instantiated production target.
        """
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_clusterwide_agent', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock__call(self, target=None, call_cnt=1, expected_args=None,
                   static=None, **kwargs):
        """mocks LBaaSv2PluginRPC._call method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, '_call', static, call_cnt, expected_args,
                          kwargs)

    def mock_validate_loadbalancers_state(
            self, target=None, call_cnt=1, expected_args=None, static=None,
            **kwargs):
        """mocks LBaaSv2PluginRPC.validate_loadbalancers_state method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'validate_loadbalancers_state', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_validate_listeners_state(
            self, target=None, call_cnt=1, expected_args=None, static=None,
            **kwargs):
        """mocks LBaaSv2PluginRPC.validate_listeners_state method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'validate_listeners_state', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_validate_pools_state(
            self, target=None, call_cnt=1, expected_args=None, static=None,
            **kwargs):
        """mocks LBaaSv2PluginRPC.validate_pools_state method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'validate_pools_state', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_validate_health_monitors_state(
            self, target=None, call_cnt=1, expected_args=None, static=None,
            **kwargs):
        """mocks LBaaSv2PluginRPC.validate_health_monitors_state method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'validate_health_monitors_state', static,
                          call_cnt, expected_args, kwargs)
        return target


class TestPluginRpcConstructor(object):
    payload = dict(topic='topic', context='context', env='env', group='group',
                   host='host')
    payload_order = ('topic', 'context', 'env', 'group', 'host')

    @classmethod
    @patch('oslo_messaging.Target')
    @patch('neutron.common.rpc.get_client')
    def create_target(cls, payload, m_target, m_get_client):
        m_target.return_value = m_target
        m_get_client.return_value = m_get_client
        return target_mod.LBaaSv2PluginRPC(*payload)

    @classmethod
    @pytest.fixture
    def target(cls):
        payload = cls.payload_order
        return cls.create_target(payload)

    @classmethod
    @pytest.fixture
    def topic_less_target(cls):
        payload = list(cls.payload_order)
        payload.remove('topic')
        payload.insert(0, None)
        return cls.create_target(payload)

    @staticmethod
    @pytest.fixture
    def get_uuid():
        return uuid.uuid4()

    @pytest.fixture
    def mock_logger(self, request):
        logger = Mock()
        self.ice_log = target_mod.LOG
        target_mod.LOG = logger
        self.m_logger = logger
        request.addfinalizer(self.teardown)

    def teardown(self):
        log = getattr(self, 'ice_log', None)
        target_mod.LOG = log if log else target_mod.LOG


class TestPluginRpc(TestPluginRpcConstructor,
                    class_tester_base_class.ClassTesterBase):
    builder = TestPluginRpcMockBuilder

    def test__init__(self, target, topic_less_target):

        def positive_case_fully_populated(self, target, expected_args):
            assert target.target.called_once_with(
                topic=target.topic, version=constants.RPC_API_VERSION)
            assert target._client.called_once_with(
                target.target, version_cap=None)
            for item in expected_args:
                assert getattr(target, item) == item

        def positive_case_default_topic(self, target):
            assert target.topic == constants.TOPIC_PROCESS_ON_HOST_V2

        positive_case_fully_populated(self, target, self.payload.keys())
        positive_case_default_topic(self, topic_less_target)

    def test_get_loadbalancers_by_network(self, target, get_uuid, mock_logger):
        populated_payload = self.payload.copy()
        map(lambda x: populated_payload.pop(x), ['topic', 'context'])
        empty_payload = dict()
        target._make_msg = Mock()
        target._call = Mock()

        def positive_case_no_loadbalancers(target, network_id, payload):
            """Tests scenario where there are no loadbalancers

            This simply has _call return with an 'empty' object.  This also
            tests whether:
            * passed tuple matches with kwargs per expected orchestration
            """
            expected = 'expected'
            target._make_msg.return_value = expected
            payload = {x: x + "`" for x in payload}
            target._call.return_value = ''
            assert target.get_loadbalancers_by_network(
                network_id, **payload) == tuple()
            payload['network_id'] = network_id
            target._make_msg.assert_called_once_with(
                'get_loadbalancers_by_network', **payload)
            target._call.assert_called_once_with(
                target.context, expected, topic=target.topic)

        def positive_case_loadbalancers(target, network_id, payload):
            """Tests the scenario of loadbalancers being returned from _call

            This test scenario tests:
            * a populated loadbalancers list return as a tuple
            * the scenario where the target's attributes are used
              * When the payload does not have the right kwargs
            """
            expected = [1, 2, 3]
            target._call.return_value = expected
            assert target.get_loadbalancers_by_network(
                network_id, **payload) == tuple(expected)
            target._make_msg.assert_called_with(
                'get_loadbalancers_by_network', network_id=network_id,
                group=target.group, host=target.host, env=target.env)

        def negative_case(target, network_id, logger):
            """Tests the negative case of the target method

            This test method will concentrate on the one negative case where
            there is a MessageDeliveryFailure exception raised during the
            target's _call method call.
            """
            target._make_msg.side_effect = messaging.MessageDeliveryFailure
            target.get_loadbalancers_by_network(network_id)
            assert logger.error.call_count == 1

        positive_case_no_loadbalancers(target, get_uuid, populated_payload)
        positive_case_loadbalancers(target, get_uuid, empty_payload)
        negative_case(target, get_uuid, self.m_logger)
