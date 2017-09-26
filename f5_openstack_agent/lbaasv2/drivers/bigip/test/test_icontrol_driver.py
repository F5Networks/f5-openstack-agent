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


class TestiControlDriverConstructor(object):
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


class TestiControlDriverBuilder(TestiControlDriverConstructor):
    @pytest.fixture
    def mock_logger(self, request):
        self.freeze_logger = target_mod.LOG
        request.addfinalizer(self.cleanup)
        logger = Mock()
        self.logger = logger
        target_mod.LOG = logger
        return logger

    def cleanup(self):
        target_mod.LOG = self.freeze_logger

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
