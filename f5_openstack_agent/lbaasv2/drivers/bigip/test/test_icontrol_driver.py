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

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2

import f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver as target_mod
import f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper
import f5_openstack_agent.lbaasv2.drivers.bigip.utils

import class_tester_base_class
import conftest as ct
import mock_builder_base_class
import test_plugin_rpc


class TestiControlDriverMockBuilder(mock_builder_base_class.MockBuilderBase,
                                    ct.TestingWithServiceConstructor):
    """This class creates targets for icontrol_driver.iControlDriver

    This MockBuilder class (see contest.MockBuilder for details) provides the
    TesterClass different levels of abstraction to provide a mock-builder
    factory that is driven by layering of targets.  This class will provide
    the targets (currently) listed in the _other_builders attribute.
    """
    _other_builders = dict(
        plugin_rpc=test_plugin_rpc.TestPluginRpcMockBuilder)

    @staticmethod
    @patch('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
           'iControlDriver.__init__')
    def mocked_target(init):
        init.return_value = None
        return target_mod.iControlDriver()

    def fully_mocked_target(self, mocked_target):
        """Creates a mocked target that mocks all lower other_builders' targets

        This does not mean that the caller's black-box is limited to this
        target, but can drill further using a system of either mocks or
        non-mocks.  Please see conftest.MockBuilder for details.
        """
        self._construct_others()
        # continue to fill in other_builders as needed...
        mocked_target.operational = True
        mocked_target.service_queue = []
        mocked_target.hostnames = []
        mocked_target.conf = Mock()  # may need to be a shared one...
        mocked_target.hostnames = None
        mocked_target.device_type = None
        mocked_target.plugin_rpc = None
        mocked_target.agent_report_state = None
        mocked_target.driver_name = 'f5-lbaasv2-icontrol'
        mocked_target.__bigips = {}
        mocked_target.__last_connect_attempt = None
        mocked_target.ha_validated = False
        mocked_target.tg_initialized = False
        mocked_target._traffic_groups = dict()
        mocked_target.agent_configurations = {}
        mocked_target.agent_configurations['device_drivers'] = \
            ['mocked_target.driver_name']
        mocked_target.agent_configurations['icontrol_endpoints'] = {}
        mocked_target.tenant_manager = None
        mocked_target.cluster_manager = None
        mocked_target.system_helper = Mock()
        mocked_target.lbaas_builder = Mock()
        mocked_target.service_adapter = Mock()
        mocked_target.service_adapter.prefix = 'UNIT_TEST'
        mocked_target.vlan_binding = None
        mocked_target.l3_binding = None
        mocked_target.cert_manager = None  # overrides register_OPTS
        mocked_target.stat_helper = None
        mocked_target.network_helper = None
        mocked_target.vs_manager = None
        mocked_target.pool_manager = None
        mocked_target.agent_configurations['tunnel_types'] = []
        mocked_target.agent_configurations['bridge_mappings'] = {}
        mocked_target.agent_configurations['tunnel_types'] = \
            'advertised_tunnel_types'
        mocked_target.agent_configurations['common_networks'] = \
            'common_network_ids'
        mocked_target.agent_configurations['f5_common_external_networks'] = \
            'f5_common_external_networks'
        mocked_target.initialized = True

    def new_fully_mocked_target(self):
        mocked_target = self.mocked_target()
        self.fully_mocked_target(mocked_target)
        return mocked_target

    def mock__init_bigips(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """mocks iControlDriver._init_bigips method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, '_init_bigips', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock_get_all_bigips(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """mocks iControlDriver.get_all_bigips method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_all_bigips', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock_backup_configuration(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """mocks iControlDriver.backup_configuration method"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'backup_configuration', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock_get_all_deployed_pools(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks iControlDriver.get_all_deployed_pools"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_all_deployed_pools', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_get_all_deployed_health_monitors(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks iControlDriver.get_all_deployed_health_monitors"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_all_deployed_health_monitors', static,
                          call_cnt, expected_args, kwargs)
        return target


class TestiControlDriverMocker(object):

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
        svc_obj = cls.basic_svc_obj(constants_v2.F5_PENDING_UPDATE)
        return [svc_obj]

    @classmethod
    @pytest.fixture
    def svc_obj_pending_create(cls):
        svc_obj = cls.basic_svc_obj(constants_v2.F5_PENDING_CREATE)
        return [svc_obj]

    @classmethod
    @pytest.fixture
    def svc_obj_active(cls):
        svc_obj = cls.basic_svc_obj(constants_v2.F5_ACTIVE)
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
        if hasattr(self, 'freeze_BigIPResourceHelper'):
            f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
                BigIPResourceHelper = self.freeze_BigIPResourceHelper

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
            all(map(lambda x: constants_v2.F5_ONLINE in x, args_list))

    @pytest.fixture
    def mock_resource_helper(self, request):
        request.addfinalizer(self.cleanup)
        mock_resource_helper = Mock()
        self.freeze_BigIPResourceHelper =  \
            f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            BigIPResourceHelper
        f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            BigIPResourceHelper = mock_resource_helper
        self.resource_helper = mock_resource_helper
        return mock_resource_helper


class TestiControlDriver(TestiControlDriverMocker,
                         class_tester_base_class.ClassTesterBase):
    builder = TestiControlDriverMockBuilder

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
