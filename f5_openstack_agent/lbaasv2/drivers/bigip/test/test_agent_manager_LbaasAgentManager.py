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

import datetime
import pytest

from mock import Mock
from mock import patch

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2

import f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager as agent_manager
import f5_openstack_agent.lbaasv2.drivers.bigip.plugin_rpc as plugin_rpc

import f5_openstack_agent.lbaasv2.drivers.bigip.test.conftest as ct


class TestLbaasAgentManagerConstructor(ct.TestingWithServiceConstructor):
    @staticmethod
    @pytest.fixture
    def target_class():
        return agent_manager.LbaasAgentManager

    @staticmethod
    @pytest.fixture
    @patch('f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager.'
           'LbaasAgentManager.__init__')
    def fully_mocked_target(init):
        """Get target instance without executing the init

        This object method is meant to grab the fully blessed instance of the
        target code without running any of the target.Target.__init__() method.
        This can be handy in that the returned target instance is completely
        free of the __init__'s tasks or overhead.

        SHOULD ONLY BE USED FOR COMPLETELY-ISOLATING WHITE-BOX TESTS!
        """
        init.return_value = None
        cfg = Mock()
        return agent_manager.LbaasAgentManager(cfg)

    @staticmethod
    @pytest.fixture
    @patch('f5_openstack_agent.lbaasv2.drivers.bigip.plugin_rpc.'
           'LBaaSv2PluginRPC.__init__')
    def fully_mocked_plugin_rpc(init):
        init.return_value = None
        return plugin_rpc.LBaaSv2PluginRPC()


class TestLbaasAgentManagerBuilder(TestLbaasAgentManagerConstructor):
    @pytest.fixture
    def mock_logger(self, request):
        request.addfinalizer(self.cleanup)
        logger = Mock()
        self.freeze_logger = agent_manager.LOG
        self.logger = logger
        agent_manager.LOG = logger

    def cleanup(self):
        agent_manager.LOG = self.freeze_logger


class TestLbaasAgentManager(TestLbaasAgentManagerBuilder):
    @pytest.mark.skip(reason="no longer agrees with implementation")
    def test_sync_state(self, fully_mocked_target, mock_logger):
        target = fully_mocked_target

        def populate_target(target):
            known_services, owned_services = set(), set(['foo'])
            loadbalancers = tuple([])
            lb_ids = set()
            target._all_vs_known_services = \
                Mock(return_value=tuple([known_services, owned_services]))
            target._get_remote_loadbalancers = \
                Mock(return_value=tuple([loadbalancers, lb_ids]))
            target._validate_services = \
                Mock()
            target._refresh_pending_services = Mock(return_value=True)
            target.agent_host = 'host'

        def positive_path(target, logger):
            populate_target(target)
            expected = True
            assert expected == target.sync_state()
            assert logger.debug.call_count == 3
            assert logger.error.called
            assert target._all_vs_known_services.call_count == 2
            assert target._get_remote_loadbalancers.call_count == 2
            target._get_remote_loadbalancers.assert_any_call(
                'get_active_loadbalancers', host=target.agent_host)
            target._get_remote_loadbalancers.assert_called_with(
                'get_all_loadbalancers', host=target.agent_host)
            target._validate_services.assert_called_once_with(set([]))
            target._refresh_pending_services.assert_called_once_with()

        def negative_path(target, logger):
            populate_target(target)
            expected = 'expected'
            target._get_remote_loadbalancers.side_effect = \
                AssertionError(expected)
            assert target.sync_state() is False
            assert logger.error.call_count == 1
            assert expected in logger.error.call_args[0][0]

        positive_path(target, self.logger)
        self.logger.error.reset_mock()
        self.logger.debug.reset_mock()
        positive_path(target, self.logger)

    def test_all_vs_known_services(self, fully_mocked_target):
        target = fully_mocked_target
        service = Mock()
        service2 = Mock()
        lb_id = 'lb_id'
        lb_id2 = lb_id + '2'
        agent_host = 'agent_host'
        target.agent_host = agent_host
        service.agent_host = agent_host
        services = tuple([tuple([lb_id, service]), tuple([lb_id2, service2])])
        target.cache = Mock()
        target.cache.services.iteritems = Mock(return_value=services)
        result0, result1 = target._all_vs_known_services()
        assert set([lb_id, lb_id2]) == result0
        assert set([lb_id]) == result1

    def test_refresh_pending_services(self, fully_mocked_target):

        def setup_target(target):
            now = datetime.datetime.now()
            timeout_val = now - datetime.timedelta(seconds=800)
            target.agent_host = 'host'
            lb_id = 'lb_id'
            lb_id2 = lb_id + '2'
            lb_id3 = lb_id + '3'
            lb, lb2, lb3 = Mock(), Mock(), Mock()
            pending_lbs = tuple([[lb, lb2, lb3], set([lb_id, lb_id2, lb_id3])])
            target.conf = Mock()
            target.conf.f5_pending_services_timeout = 100
            target._get_remote_loadbalancers = Mock(return_value=pending_lbs)
            target.pending_services = dict(lb_id=timeout_val, lb_id3=now)
            target.refresh_service = Mock(return_value=True)
            target.service_timeout = Mock()

        def all_paths(target):
            setup_target(target)
            target._refresh_pending_services()
            target.service_timeout.assert_called_once_with('lb_id')
            assert 'lb_id' not in target.pending_services
            assert 'lb_id2' in target.pending_services
            assert 'lb_id3' in target.pending_services

        all_paths(fully_mocked_target)

    def test_get_remote_loadbalancers(self, fully_mocked_target):

        def setup_target(target):
            lbs = [dict(lb_id=0), dict(lb_id=2)]
            expected = tuple([tuple(lbs), set([0, 2])])
            call_method = Mock(return_value=lbs)
            target.plugin_rpc = Mock()
            target.plugin_rpc.call_method = call_method
            return expected

        def full_path(target):
            expected = setup_target(fully_mocked_target)
            host = 'host'
            assert target._get_remote_loadbalancers('call_method', host=host) \
                == expected

        full_path(fully_mocked_target)

    def test_validate_service(self, fully_mocked_target, mock_logger):
        def setup_target(target):
            target.plugin_rpc = Mock()
            target.lbdriver = Mock()
            target.has_provisioning_status_of_error = Mock(return_value=True)
            target.lbdriver.service_exists.return_value = True
            target.lbdriver.service_rename_required.return_value = False
            target.cache = Mock()
            target.agent_host = 'host'

        def reset_target(target):
            target.lbdriver.sync.reset_mock()
            self.logger.debug.reset_mock()

        def negative_path(target):
            # needs to be fix to cover all logical paths...
            setup_target(target)
            lb_id = 1
            target.validate_service(lb_id)
            target.lbdriver.sync.assert_called_once_with(
                target.plugin_rpc.get_service_by_loadbalancer_id.return_value)

        def positive_path(target):
            # needs to be fixed to coverall logical paths...
            lb_id = 1
            target.has_provisioning_status_of_error.return_value = False
            target.validate_service(lb_id)
            target.lbdriver.sync.assert_not_called
            assert 'Found service' in self.logger.debug.call_args[0][0]

        negative_path(fully_mocked_target)
        reset_target(fully_mocked_target)
        positive_path(fully_mocked_target)

    def test_validate_services(self, fully_mocked_target):
        lb_ids = [1, 2]
        fully_mocked_target.cache = Mock()
        fully_mocked_target.cache.get_by_loadbalancer_id.side_effect = \
            [True, False]
        fully_mocked_target.validate_service = Mock()
        fully_mocked_target._validate_services(lb_ids)
        fully_mocked_target.validate_service.assert_called_once_with(2)
        fully_mocked_target.cache.get_by_loadbalancer_id.assert_any_call(1)
        fully_mocked_target.cache.get_by_loadbalancer_id.assert_called_with(2)
        assert fully_mocked_target.cache.get_by_loadbalancer_id.call_count == 2

    @pytest.mark.skip(reason="TypeError from mock redirecting rpc_calls.")
    def test_lbb_sync_state(self, fully_mocked_target,
                            fully_mocked_plugin_rpc, mock_logger):
        """A limited black-box functional test for testing flow of sync_state

        This test method is only meant to orchestrate a functional flow test
        across a common agent_manager.LbaasAgentManager.sync_state() runtime
        might actually look like through the many methods it runs through.

        This is also testing very basic, peripheral orchestration events that
        are expected to occur.

        Where the limits of the test are...
            Since this is a black-box standalone test, this test does have its
            limits.  Although it can run in any environment via tox, it cannot
            touch or be touched by a full openstack system "in the wild".  To
            fascilitate this, this test is limited to the
            plugin_rpc.LBaaSv2PluginRPC.__call_rpc_method method call which is
            heavily mocked as well as the f5_openstack_lbaasv2_driver's code.
        """

        def setup_test(target, plugin_rpc):
            host = 'host'
            now = datetime.datetime.now()
            timed_out = now + datetime.timedelta(seconds=80)
            service1 = Mock()
            service1.agent_host = host
            service2 = Mock()
            service2.agent_host = 'host1'
            # manage target's base...
            target.pending_services = {1: timed_out}
            target.conf = Mock()
            target.conf.f5_pending_services_timeout = 30
            target.cache = Mock()
            target.agent_host = host
            target.cache.get_by_loadbalancer_id.side_effect = \
                [False, True, True]
            target.cache.services = dict(one=service1, two=service2)
            # modify plugin_rpc items...
            target.plugin_rpc = plugin_rpc
            target.plugin_rpc.env = Mock()
            target.plugin_rpc.context = Mock()
            target.plugin_rpc.topic = Mock()
            target.plugin_rpc._client = Mock()
            target.plugin_rpc.host = host
            caller = Mock()
            target.plugin_rpc._client.prepare.return_value = caller
            caller.call.side_effect = \
                [tuple([dict(lb_id=1), dict(lb_id=2)]),
                 tuple([dict(lb_id=1), dict(lb_id=2)]), service1,
                 tuple([dict(lb_id=1), dict(lb_id=3)]), service1, service1,
                 service1]
            # target.validate_service protections...
            target.lbdriver = Mock()
            target.lbdriver.service_exists.return_value = True
            return caller.call

        def functional_path(target, plugin_rpc):
            rpc_call = setup_test(target, plugin_rpc)
            assert target.sync_state()
            assert 3 in target.pending_services
            assert isinstance(target.pending_services[3], datetime.datetime)
            assert rpc_call.call_count == 7
            call_args_list = rpc_call.call_args_list
            call_order = ['get_active_loadbalancers',
                          'get_all_loadbalancers',
                          'get_service_by_loadbalancer_id',
                          'get_pending_loadbalancers',
                          'get_service_by_loadbalancer_id',
                          'get_service_by_loadbalancer_id',
                          'get_service_by_loadbalancer_id']
            for cnt, expected_call in enumerate(call_order):
                assert expected_call in call_args_list[cnt][0]

        functional_path(fully_mocked_target, fully_mocked_plugin_rpc)

    def test_has_provisioning_error(self, target_class, service_with_listener):
        svc = service_with_listener

        def reset_svc(svc):
            listener = svc['listeners'][0]
            loadbalancer = svc['loadbalancer']
            listener['provisioning_status'] = constants_v2.F5_ACTIVE
            loadbalancer['provisioning_status'] = constants_v2.F5_ACTIVE

        def negative_list_scenario(target, svc):
            reset_svc(svc)
            svc['listeners'][0]['provisioning_status'] = constants_v2.F5_ERROR
            assert target.has_provisioning_status_of_error(svc)
            assert svc['loadbalancer']['provisioning_status'] == \
                constants_v2.F5_ERROR

        def negative_dict_scenario(target, svc):
            reset_svc(svc)
            svc['loadbalancer']['provisioning_status'] = constants_v2.F5_ERROR
            assert target.has_provisioning_status_of_error(svc)
            assert svc['loadbalancer']['provisioning_status'] == \
                constants_v2.F5_ERROR

        def awkward_network_nest(target, svc):
            reset_svc(svc)
            svc['loadbalancer']['provisioning_status'] = constants_v2.F5_ERROR
            listener_id = svc['listeners'][0]['id']
            awkward = {listener_id: svc['listeners'][0]}
            svc['listeners'][0] = awkward
            assert target.has_provisioning_status_of_error(svc)
            assert svc['loadbalancer']['provisioning_status'] == \
                constants_v2.F5_ERROR

        negative_list_scenario(target_class, svc)
        negative_dict_scenario(target_class, svc)
        awkward_network_nest(target_class, svc)
