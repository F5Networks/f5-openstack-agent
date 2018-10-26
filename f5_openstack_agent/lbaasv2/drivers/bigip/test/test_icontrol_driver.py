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
from requests import HTTPError

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
        mocked_target.__traffic_groups = []
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

    def mock_purge_orphaned_loadbalancer(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks icontrol_driver.iControlDriver.purge_orphaned_loadbalancer"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'purge_orphaned_loadbalancer', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_purge_orphaned_listener(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks icontrol_driver.iControlDriver.purge_orphaned_listener"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'purge_orphaned_listener', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock_get_all_deployed_l7_policys(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks icontrol_driver.iControlDriver.purge_orphaned_l7_policy"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_all_deployed_l7_policys', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_purge_orphaned_pool(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks icontrol_driver.iControlDriver.purge_orphaned_pool"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'purge_orphaned_pool', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock_purge_orphaned_health_monitor(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks iControlDriver.purge_orphaned_health_monitor"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'purge_orphaned_health_monitor', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_purge_orphaned_l7_policy(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks icontrol_driver.iControlDriver.purge_orphaned_l7_policy"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'purge_orphaned_l7_policy', static, call_cnt,
                          expected_args, kwargs)
        return target

    def mock_get_all_deployed_loadbalancers(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks iControlDriver.get_all_deployed_loadbalancers"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_all_deployed_loadbalancers', static,
                          call_cnt, expected_args, kwargs)
        return target

    def mock_get_all_deployed_listeners(
            self, target=None, call_cnt=1, static=None, expected_args=None,
            **kwargs):
        """Mocks iControlDriver.get_all_deployed_listeners"""
        if not target:
            target = self.new_fully_mocked_target()
        self._mockfactory(target, 'get_all_deployed_listeners', static,
                          call_cnt, expected_args, kwargs)
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

    def test_purge_orphaned_loadbalancer(self, standalone_builder,
                                         fully_mocked_target,
                                         mock_logger,
                                         service_with_loadbalancer,
                                         service_with_pool,
                                         mock_resource_helper):
        builder = standalone_builder
        target = fully_mocked_target

        def virtual_with_pool(target, builder, svc, resource_helper):
            bigip = Mock()
            builder.mock_get_all_bigips(target, return_value=[bigip])
            va = Mock()
            va.load.return_value = va
            va.name = svc['loadbalancer']['id']
            vses = Mock()
            vses.get_resources.return_value = [vses]
            vses.pool = svc['pools'][0]['id']
            pool = Mock()
            pool.load.return_value = pool
            bigip_resource_helpers_returns = [va, vses, pool, va]
            resource_helper.side_effect = bigip_resource_helpers_returns
            tenant_id = svc['loadbalancer']['tenant_id']
            lb_id = svc['loadbalancer']['id']
            hostnames = ['foobyyou']
            bigip.hostname = hostnames[0]
            builder.mock__init_bigips(target)
            vses.destination = "/{}{}/{}".format(
                target.service_adapter.prefix, tenant_id, va.name)
            target.purge_orphaned_loadbalancer(
                tenant_id=tenant_id, loadbalancer_id=lb_id,
                hostnames=hostnames)
            builder.check_mocks(target)
            assert resource_helper.call_count == 4
            assert vses.delete.call_count
            assert va.delete.call_count
            assert pool.delete.call_count

        def virtual(target, builder, svc, resource_helper):
            bigip = Mock()
            builder.mock_get_all_bigips(target, return_value=[bigip])
            va = Mock()
            va.load.return_value = va
            va.name = svc['loadbalancer']['id']
            vses = Mock()
            vses.get_resources.return_value = [vses]
            bigip_resource_helpers_returns = [va, vses, va]
            resource_helper.side_effect = bigip_resource_helpers_returns
            tenant_id = svc['loadbalancer']['tenant_id']
            lb_id = svc['loadbalancer']['id']
            hostnames = ['foobyyou']
            bigip.hostname = hostnames[0]
            builder.mock__init_bigips(target)
            vses.destination = "/{}{}/{}".format(
                target.service_adapter.prefix, tenant_id, va.name)
            delattr(vses, 'pool')
            target.purge_orphaned_loadbalancer(
                tenant_id=tenant_id, loadbalancer_id=lb_id,
                hostnames=hostnames)
            builder.check_mocks(target)
            assert resource_helper.call_count == 3
            assert vses.delete.call_count
            assert va.delete.call_count

        def error(target, builder, resource_helper, logger, error):
            bigip = Mock()
            builder.mock_get_all_bigips(target, return_value=[bigip])
            va = Mock()
            vses = error
            bigip_resource_helpers_returns = [va, vses]
            resource_helper.side_effect = bigip_resource_helpers_returns
            assert logger.exceptions.call_cnt

        virtual_with_pool(target, builder, service_with_pool,
                          mock_resource_helper)
        mock_resource_helper.reset_mock()
        virtual(target, builder, service_with_loadbalancer,
                mock_resource_helper)
        error(target, builder, mock_resource_helper, self.logger, HTTPError)
        error(target, builder, mock_resource_helper, self.logger, Exception)

    def test_purge_orphaned_listener(self, standalone_builder,
                                     fully_mocked_target, mock_logger,
                                     service_with_listener,
                                     mock_resource_helper):
        svc = service_with_listener
        builder = standalone_builder
        target = fully_mocked_target

        def main_path(target, builder, svc, resource_helper):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostname = hostnames[0]
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['listeners'][0]['id']
            t_id = svc['listeners'][0]['tenant_id']
            target.purge_orphaned_listener(t_id, li_id, hostnames)
            builder.check_mocks(target)
            assert resource_helper.return_value.load.call_count
            assert resource_helper.call_count

        def error(target, svc, builder, resource_helper, logger, error):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostnames = hostnames
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['listeners'][0]['id']
            t_id = svc['listeners'][0]['tenant_id']
            target.purge_orphaned_listener(t_id, li_id, hostnames)
            assert logger.exceptions.call_cnt

        main_path(target, builder, svc, mock_resource_helper)
        mock_resource_helper.reset_mock()
        error(target, svc, builder, mock_resource_helper, self.logger,
              HTTPError)
        error(target, svc, builder, mock_resource_helper, self.logger,
              Exception)

    def test_purge_orphaned_l7_policy(self, standalone_builder,
                                      fully_mocked_target, mock_logger,
                                      service_with_l7_policy,
                                      mock_resource_helper):
        svc = service_with_l7_policy
        builder = standalone_builder
        target = fully_mocked_target

        def main_path(target, builder, svc, resource_helper):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostname = hostnames[0]
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['l7_policies'][0]['id']
            t_id = svc['l7_policies'][0]['tenant_id']
            target.purge_orphaned_l7_policy(t_id, li_id, hostnames)
            builder.check_mocks(target)
            assert resource_helper.return_value.load.call_count
            assert resource_helper.call_count

        def error(target, svc, builder, resource_helper, logger, error):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostnames = hostnames
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['l7_policies'][0]['id']
            t_id = svc['l7_policies'][0]['tenant_id']
            target.purge_orphaned_l7_policy(t_id, li_id, hostnames)
            assert logger.exceptions.call_cnt

        main_path(target, builder, svc, mock_resource_helper)
        mock_resource_helper.reset_mock()
        error(target, svc, builder, mock_resource_helper, self.logger,
              HTTPError)
        error(target, svc, builder, mock_resource_helper, self.logger,
              Exception)

    def test_purge_orphaned_pool(self, standalone_builder,
                                 fully_mocked_target, mock_logger,
                                 service_with_pool,
                                 mock_resource_helper):
        svc = service_with_pool
        builder = standalone_builder
        target = fully_mocked_target

        def main_path(target, builder, svc, resource_helper):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostname = hostnames[0]
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['pools'][0]['id']
            t_id = svc['pools'][0]['tenant_id']
            target.purge_orphaned_pool(t_id, li_id, hostnames)
            builder.check_mocks(target)
            assert resource_helper.return_value.load.call_count
            assert resource_helper.call_count

        def error(target, svc, builder, resource_helper, logger, error):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostnames = hostnames
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['pools'][0]['id']
            t_id = svc['pools'][0]['tenant_id']
            target.purge_orphaned_pool(t_id, li_id, hostnames)
            assert logger.exceptions.call_cnt

        main_path(target, builder, svc, mock_resource_helper)
        mock_resource_helper.reset_mock()
        error(target, svc, builder, mock_resource_helper, self.logger,
              HTTPError)
        error(target, svc, builder, mock_resource_helper, self.logger,
              Exception)

    def test_purge_orphaned_health_monitor(self, standalone_builder,
                                           fully_mocked_target, mock_logger,
                                           service_with_health_monitor,
                                           mock_resource_helper):
        svc = service_with_health_monitor
        builder = standalone_builder
        target = fully_mocked_target

        def main_path(target, builder, svc, resource_helper):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostname = hostnames[0]
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['healthmonitors'][0]['id']
            t_id = svc['healthmonitors'][0]['tenant_id']
            target.purge_orphaned_health_monitor(t_id, li_id, hostnames)
            builder.check_mocks(target)
            assert resource_helper.return_value.load.call_count
            assert resource_helper.call_count == 4

        def error(target, svc, builder, resource_helper, logger, error):
            bigip = Mock()
            hostnames = ['foodoozoo']
            bigip.hostname = hostnames[0]
            builder.mock_get_all_bigips(target, return_value=[bigip])
            li_id = svc['healthmonitors'][0]['id']
            t_id = svc['healthmonitors'][0]['tenant_id']
            resource_helper.return_value.load.side_effect = error
            target.purge_orphaned_health_monitor(t_id, li_id, hostnames)

        main_path(target, builder, svc, mock_resource_helper)
        mock_resource_helper.reset_mock()
        response = Mock()
        response.status_code = 404
        http_error = HTTPError("foo")
        http_error.response = response
        error(target, svc, builder, mock_resource_helper, self.logger,
              http_error)
        assert self.logger.exception.call_count
        self.logger.reset_mock()
        error(target, svc, builder, mock_resource_helper, self.logger,
              Exception)
        assert self.logger.exception.call_count

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
