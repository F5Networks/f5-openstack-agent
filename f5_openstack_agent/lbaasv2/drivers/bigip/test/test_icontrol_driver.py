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
import uuid

from mock import Mock
from mock import patch

import neutron.plugins.common.constants as plugin_const
import neutron_lbaas.services.loadbalancer.constants as lb_const

import f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver as target_mod
import f5_openstack_agent.lbaasv2.drivers.bigip.utils

import conftest as ct


class TestiControlDriverConstructor(ct.TestingWithServiceConstructor):
    @staticmethod
    @pytest.fixture
    @patch('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
           'iControlDriver.__init__')
    def fully_mocked_target(init):
        init.return_value = None
        return target_mod.iControlDriver()

    @staticmethod
    @pytest.fixture
    def new_uuid():
        return str(uuid.uuid4())

    @staticmethod
    @pytest.fixture
    def dumb_svc_obj(new_uuid):
        return dict(id=new_uuid)

    @classmethod
    def basic_svc_obj(cls, provisioning_status):
        svc_obj = dict(provisioning_status=provisioning_status)
        svc_obj.update(cls.dumb_svc_obj(cls.new_uuid()))
        return svc_obj

    @classmethod
    @pytest.fixture
    def svc_obj_pending_update(cls):
        svc_obj = cls.basic_svc_obj(plugin_const.PENDING_UPDATE)
        return [svc_obj]

    @classmethod
    @pytest.fixture
    def svc_obj_pending_create(cls):
        svc_obj = cls.basic_svc_obj(plugin_const.PENDING_CREATE)
        return [svc_obj]

    @classmethod
    @pytest.fixture
    def svc_obj_active(cls):
        svc_obj = cls.basic_svc_obj(plugin_const.ACTIVE)
        return [svc_obj]

    @staticmethod
    @pytest.fixture
    def positive_svc_obj_list(svc_obj_pending_update,
                              svc_obj_pending_create, svc_obj_active):
        positive_members = svc_obj_pending_update
        positive_members.extend(svc_obj_pending_create)
        positive_members.extend(svc_obj_active)
        return positive_members

    @staticmethod
    def mock_targets_plugin_rpc(target):
        target.plugin_rpc = Mock()

    @staticmethod
    @pytest.fixture
    def mocked_target_with_connection(fully_mocked_target):
        fully_mocked_target.operational = True
        return fully_mocked_target


class TestiControlDriverBuilder(TestiControlDriverConstructor):
    @pytest.fixture
    def mock_is_operational(self, request):
        request.addfinalizer(self.cleanup)
        self.freeze_is_operational = target_mod.is_operational
        is_operational = Mock()
        target_mod.is_operational = is_operational
        self.is_operational = is_operational

    @pytest.fixture
    def mock_logger(self, request):
        # Useful for tracking logger events in icontrol_driver.py
        self.freeze_logger = target_mod.LOG
        request.addfinalizer(self.cleanup)
        logger = Mock()
        self.logger = logger
        target_mod.LOG = logger
        return logger

    @pytest.fixture
    def mock_log_utils(self, request):
        # Necessary for by-passing @serialized cleanly
        logger = Mock()
        request.addfinalizer(self.cleanup)
        self.freeze_log_utils = \
            f5_openstack_agent.lbaasv2.drivers.bigip.utils.LOG
        f5_openstack_agent.lbaasv2.drivers.bigip.utils.LOG = logger

    def cleanup(self):
        if hasattr(self, 'freeze_log_utils'):
            f5_openstack_agent.lbaasv2.drivers.bigip.utils.LOG = \
                self.freeze_log_utils
        if hasattr(self, 'freeze_logger'):
            target_mod.LOG = self.freeze_logger
        if hasattr(self, 'freeze_is_operational'):
            target_mod.is_operational = self.freeze_is_operational

    def update_svc_obj_positive_path(self, target, positive_svc_objs, method,
                                     test_method, timeout=None):
        self.mock_targets_plugin_rpc(target)
        method = getattr(target, method)
        if isinstance(timeout, type(None)):
            method(positive_svc_objs)
        else:
            method(positive_svc_objs, timeout)
        if test_method:
            called_method = getattr(target.plugin_rpc, test_method)
            args_list = called_method.call_args_list
            assert called_method.call_count == 3
            all(map(lambda x: lb_const.ONLINE in x, args_list))


class TestiControlDriver(TestiControlDriverBuilder):
    def test_update_member_status(self, fully_mocked_target,
                                  positive_svc_obj_list):
        self.update_svc_obj_positive_path(
            fully_mocked_target, positive_svc_obj_list,
            '_update_member_status', 'update_member_status', timeout=False)

    def test_update_health_monitor_status(self, fully_mocked_target,
                                          positive_svc_obj_list):
        self.update_svc_obj_positive_path(
            fully_mocked_target, positive_svc_obj_list,
            '_update_health_monitor_status', 'update_health_monitor_status')

    def test_update_pool_status(self, fully_mocked_target,
                                positive_svc_obj_list):
        self.update_svc_obj_positive_path(
            fully_mocked_target, positive_svc_obj_list,
            '_update_pool_status', 'update_pool_status')

    def test_update_listener_status(self, fully_mocked_target,
                                    positive_svc_obj_list):
        for svc_obj in positive_svc_obj_list:
            svc_obj['operating_status'] = Mock()
        svc = dict(listeners=positive_svc_obj_list)
        self.update_svc_obj_positive_path(
            fully_mocked_target, svc, '_update_listener_status',
            'update_listener_status')

    def test_update_l7rule_status(self, fully_mocked_target,
                                  positive_svc_obj_list):
        for svc_obj in positive_svc_obj_list:
            svc_obj['policy_id'] = self.new_uuid()
        self.update_svc_obj_positive_path(
            fully_mocked_target, positive_svc_obj_list,
            '_update_l7rule_status', 'update_l7rule_status')

    def test_update_l7policy_status(self, fully_mocked_target,
                                    positive_svc_obj_list):
        self.update_svc_obj_positive_path(
            fully_mocked_target, positive_svc_obj_list,
            '_update_l7policy_status', 'update_l7policy_status')

    def test_sync(self, mocked_target_with_connection,
                  service_with_loadbalancer, mock_logger, mock_is_operational,
                  mock_log_utils):

        def setup_target(target, svc):
            target.service_queue = list()
            target._common_service_handler = Mock(return_value='pass')

        def setup_plugin_rpc(target, svc):
            target.plugin_rpc = Mock()
            target.plugin_rpc.get_service_by_loadbalancer_id = \
                Mock(return_value=svc)

        def without_plugin_rpc(target, svc):
            setup_target(target, svc)
            assert target.sync(svc) == 'pass'
            target._common_service_handler.assert_called_once_with(svc)

        def with_plugin_rpc(target, svc):
            setup_target(target, svc)
            setup_plugin_rpc(target, svc)
            assert target.sync(svc) == 'pass'
            target.plugin_rpc.get_service_by_loadbalancer_id.\
                assert_called_with(svc['loadbalancer']['id'])
            target._common_service_handler.assert_called_once_with(svc)

        def without_lb(target, svc):
            setup_target(target, svc)
            setup_plugin_rpc(target, svc)
            assert not target.sync({})
            target.plugin_rpc.get_service_by_loadbalancer_id.\
                assert_not_called()
            target._common_service_handler.assert_not_called()
        without_plugin_rpc(mocked_target_with_connection,
                           service_with_loadbalancer)
        with_plugin_rpc(
            self.mocked_target_with_connection(self.fully_mocked_target()),
            service_with_loadbalancer)
        without_lb(
            self.mocked_target_with_connection(self.fully_mocked_target()),
            service_with_loadbalancer)
