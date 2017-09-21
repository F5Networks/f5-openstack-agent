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

from mock import Mock

import neutron.plugins.common.constants as plugin_const

import f5_openstack_agent.lbaasv2.drivers.bigip.listener_service \
    as listener_service
import f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper

import f5_openstack_agent.lbaasv2.drivers.bigip.test.conftest as ct


class TestListenerServiceBuilderConstructor(ct.TestingWithServiceConstructor):
    # contains all quick service-related creation items
    # contains all static, class, or non-intelligent object manipulations
    @staticmethod
    def creation_mode_listener(svc, listener):
        svc['listener'] = listener
        svc['listener']['provisioning_status'] = plugin_const.PENDING_CREATE
        svc['loadbalancer']['provisioning_status'] = \
            plugin_const.PENDING_UPDATE


class TestListenerServiceBuilderBuilder(TestListenerServiceBuilderConstructor):
    # contains all intelligence-based memory manipulations
    @pytest.fixture
    def mock_logger(self, request):
        self.freeze_log = listener_service.LOG
        listener_service.LOG = Mock()
        request.addfinalizer(self.cleanup)
        return listener_service.LOG

    def cleanup(self):
        listener_service.LOG = self.freeze_log
        f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            BigIPResourceHelper = self.freeze_resource_bigip
        f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            ResourceType = self.freeze_resource_type

    def clean_svc_with_listener(self):
        svc = self.service_with_network(self.new_id())
        svc = self.service_with_subnet(self.new_id(), svc)
        svc = self.service_with_loadbalancer(self.new_id(), svc)
        svc = self.service_with_listener(self.new_id(), svc)
        return svc

    @pytest.fixture
    def target(self, mock_logger):
        resource_bigip = Mock()
        resource_type = Mock()
        self.freeze_resource_bigip = \
            f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            BigIPResourceHelper
        self.freeze_resource_type = \
            f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            ResourceType
        f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            BigIPResourceHelper = resource_bigip
        f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper.\
            ResourceType = resource_type
        self.resource_bigip = resource_bigip
        self.resource_type = resource_type
        self.logger = mock_logger
        service_adapter = Mock()
        cert_maanger = Mock()
        parent_ssl_profile = Mock()
        parent_ssl_profile.__str__ = Mock(return_value='parent_ssl_profile')
        target = listener_service.ListenerServiceBuilder(
            service_adapter, cert_maanger,
            parent_ssl_profile=parent_ssl_profile)
        return target


class TestListenerServiceBuilder(TestListenerServiceBuilderBuilder):
    def test__init__(self, target):
        self.logger.debug.assert_called_once()
        assert 'ListenerServiceBuilder' in self.logger.debug.call_args[0][0]
        assert isinstance(target.cert_manager, Mock)
        assert isinstance(target.parent_ssl_profile, Mock)
        assert isinstance(target.parent_ssl_profile, Mock)
        self.resource_bigip.assert_called_once_with(
            self.resource_type.virtual)
