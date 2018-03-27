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
import urllib

from mock import Mock

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from requests import HTTPError

import f5_openstack_agent.lbaasv2.drivers.bigip.pool_service \
    as pool_service
import f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper

import f5_openstack_agent.lbaasv2.drivers.bigip.test.conftest as ct


class MockError(Exception):
    pass


class MockHTTPError(HTTPError):
    def __init__(self, response_obj, message=''):
        self.response = response_obj
        self.message = message


class MockHTTPErrorResponse400(HTTPError):
    def __init__(self):
        self.status_code = 400


class MockHTTPErrorResponse404(HTTPError):
    def __init__(self):
        self.status_code = 404


class MockHTTPErrorResponse409(HTTPError):
    def __init__(self):
        self.status_code = 409


class MockHTTPErrorResponse500(HTTPError):
    def __init__(self):
        self.status_code = 500


class TestPoolServiceBuilderConstructor(ct.TestingWithServiceConstructor):
    # contains all quick service-related creation items
    # contains all static, class, or non-intelligent object manipulations
    @staticmethod
    def creation_mode_pool(svc, pool):
        svc['pool'] = pool
        svc['pool']['provisioning_status'] = constants_v2.F5_PENDING_CREATE
        svc['loadbalancer']['provisioning_status'] = \
            constants_v2.F5_PENDING_UPDATE


class TestPoolServiceBuilderBuilder(TestPoolServiceBuilderConstructor):
    # contains all intelligence-based memory manipulations
    @pytest.fixture
    def mock_logger(self, request):
        self.freeze_log = pool_service.LOG
        pool_service.LOG = Mock()
        request.addfinalizer(self.cleanup)
        return pool_service.LOG

    def cleanup(self):
        pool_service.LOG = self.freeze_log

    def clean_svc_with_pool(self):
        svc = self.service_with_network(self.new_id())
        svc = self.service_with_subnet(self.new_id(), svc)
        svc = self.service_with_loadbalancer(self.new_id(), svc)
        svc = self.service_with_listener(self.new_id(), svc)
        svc = self.service_with_pool(self.new_id(), svc)
        return svc

    @pytest.fixture
    def target(self, mock_logger):

        service_adapter = Mock()
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

        target = pool_service.PoolServiceBuilder(service_adapter)

        return target


class TestPoolServiceBuilder(TestPoolServiceBuilderBuilder):

    def test_create_pool(self, target, service_with_loadbalancer,
                         service_with_pool):
        svc = service_with_pool

        def clean_target(self, target):
            target.pool_helper.reset_mock()
            target.pool_helper.update.reset_mock()
            target.pool_helper.create.reset_mock()
            svc = self.clean_svc_with_pool()
            # self.creation_mode_listener(svc, svc['listeners'][0])
            return target, svc

        def create_pool_200(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]
            retval = target.create_pool(service_with_pool, bigips)

            assert not retval
            assert not target.pool_helper.update.called

        def create_pool_409(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse409())

            retval = target.create_pool(service_with_pool, bigips)

            assert not retval
            assert target.pool_helper.update.called

        def create_pool_400(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse400())

            retval = target.create_pool(service_with_pool, bigips)

            assert retval
            assert not target.pool_helper.update.called

        def create_pool_error(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.create.side_effect = MockError()

            retval = target.create_pool(service_with_pool, bigips)

            assert retval
            assert not target.pool_helper.update.called

        def create_pool_409_and_error(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse409())
            target.pool_helper.update.side_effect = MockError()

            retval = target.create_pool(service_with_pool, bigips)

            assert retval
            assert target.pool_helper.update.called

        self.creation_mode_pool(svc, svc['pools'][0])

        create_pool_200(target, svc)
        target, svc = clean_target(self, target)
        create_pool_409(target, svc)
        target, svc = clean_target(self, target)
        create_pool_400(target, svc)
        target, svc = clean_target(self, target)
        create_pool_error(target, svc)
        target, svc = clean_target(self, target)
        create_pool_409_and_error(target, svc)

    def test_delete_pool(self, target, service_with_loadbalancer,
                         service_with_pool):
        svc = service_with_pool

        def clean_target(self, target):
            target.pool_helper.reset_mock()
            target.pool_helper.update.reset_mock()
            target.pool_helper.delete.reset_mock()
            svc = self.clean_svc_with_pool()
            # self.creation_mode_listener(svc, svc['listeners'][0])
            return target, svc

        def delete_pool_200(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]
            retval = target.delete_pool(service_with_pool, bigips)

            assert not retval

        def delete_pool_404(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.delete.side_effect = MockHTTPError(
                MockHTTPErrorResponse404())

            retval = target.delete_pool(service_with_pool, bigips)

            assert not retval

        def delete_pool_400(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.delete.side_effect = MockHTTPError(
                MockHTTPErrorResponse400())

            retval = target.delete_pool(service_with_pool, bigips)

            assert retval
            assert not target.pool_helper.update.called

        def delete_pool_error(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.delete.side_effect = MockError()

            retval = target.delete_pool(service_with_pool, bigips)

            assert retval
            assert not target.pool_helper.update.called

        self.creation_mode_pool(svc, svc['pools'][0])

        delete_pool_200(target, svc)
        target, svc = clean_target(self, target)
        delete_pool_404(target, svc)
        target, svc = clean_target(self, target)
        delete_pool_400(target, svc)
        target, svc = clean_target(self, target)
        delete_pool_error(target, svc)

    def test_update_pool(self, target, service_with_loadbalancer,
                         service_with_pool):
        svc = service_with_pool

        def clean_target(self, target):
            target.pool_helper.reset_mock()
            target.pool_helper.update.reset_mock()
            svc = self.clean_svc_with_pool()

            return target, svc

        def update_pool_200(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]
            retval = target.update_pool(service_with_pool, bigips)

            assert not retval

        def update_pool_error(target, service_with_pool):
            pool = dict(name='name', partition='partition')
            target.service_adapter.get_pool.return_value = pool
            bigips = [Mock()]

            target.pool_helper.update.side_effect = MockError()

            retval = target.update_pool(service_with_pool, bigips)

            assert retval

        update_pool_200(target, svc)
        update_pool_error(target, svc)

    def test_create_monitor(self, target, service_with_loadbalancer,
                            service_with_pool):
        svc = service_with_pool

        def clean_target(self, target):
            target.hm_helper.reset_mock()
            target.hm_helper.update.reset_mock()
            target.hm_helper.create.reset_mock()
            svc = self.clean_svc_with_pool()

            return target, svc

        def create_monitor_200(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            bigips = [Mock()]
            retval = target.create_healthmonitor(service_with_pool, bigips)

            assert not retval
            assert not hm_helper.update.called

        def create_monitor_409(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse409())

            bigips = [Mock()]
            retval = target.create_healthmonitor(service_with_pool, bigips)

            assert not retval
            assert hm_helper.update.called

        def create_monitor_400(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse400())

            bigips = [Mock()]
            retval = target.create_healthmonitor(service_with_pool, bigips)

            assert retval
            assert not hm_helper.update.called

        def create_monitor_error(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.create.side_effect = MockError()

            bigips = [Mock()]
            retval = target.create_healthmonitor(service_with_pool, bigips)

            assert retval
            assert not hm_helper.update.called

        def create_monitor_409_error(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse409())
            hm_helper.update.side_effect = MockError()

            bigips = [Mock()]
            retval = target.create_healthmonitor(service_with_pool, bigips)

            assert retval
            assert hm_helper.update.called

        self.creation_mode_pool(svc, svc['pools'][0])

        create_monitor_200(target, svc)
        create_monitor_409(target, svc)
        create_monitor_400(target, svc)
        create_monitor_error(target, svc)
        create_monitor_409_error(target, svc)

    def test_delete_monitor(self, target, service_with_loadbalancer,
                            service_with_pool):
        svc = service_with_pool

        def clean_target(self, target):
            target.hm_helper.reset_mock()
            target.hm_helper.update.reset_mock()
            target.hm_helper.delete.reset_mock()
            svc = self.clean_svc_with_pool()

            return target, svc

        def delete_monitor_200(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            bigips = [Mock()]
            retval = target.delete_healthmonitor(service_with_pool, bigips)

            assert not retval

        def delete_monitor_404(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.delete.side_effect = MockHTTPError(
                MockHTTPErrorResponse404())

            bigips = [Mock()]
            retval = target.delete_healthmonitor(service_with_pool, bigips)

            assert not retval

        def delete_monitor_400(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.delete.side_effect = MockHTTPError(
                MockHTTPErrorResponse400())

            bigips = [Mock()]
            retval = target.delete_healthmonitor(service_with_pool, bigips)

            assert retval

        def delete_monitor_error(target, service_with_pool):
            monitor = dict(name='name', partition='partition')
            target.service_adapter.get_healthmonitor.return_value = \
                monitor
            hm_helper = Mock()
            target._get_monitor_helper = Mock()
            target._get_monitor_helper.return_value = hm_helper

            hm_helper.delete.side_effect = MockError()

            bigips = [Mock()]
            retval = target.delete_healthmonitor(service_with_pool, bigips)

            assert retval

        self.creation_mode_pool(svc, svc['pools'][0])

        delete_monitor_200(target, svc)
        delete_monitor_404(target, svc)
        delete_monitor_400(target, svc)
        delete_monitor_error(target, svc)

    def test_delete_member_node(self, target, pool_member_service):
        node = {'name': "name", 'partition': "partition"}
        loadbalancer = pool_member_service['loadbalancer']
        member = pool_member_service['members'][0]
        target.service_adapter.get_member_node.return_value = node
        bigip = Mock()

        error = target._delete_member_node(loadbalancer, member, bigip)

        assert target.node_helper.delete.called
        assert not error

    def test_delete_member_node_400(self, target, pool_member_service,
                                    mock_logger):
        node = {'name': "name", 'partition': "partition"}
        loadbalancer = pool_member_service['loadbalancer']
        member = pool_member_service['members'][0]
        target.service_adapter.get_member_node.return_value = node
        bigip = Mock()
        target.node_helper.delete.side_effect = MockHTTPError(
            MockHTTPErrorResponse400())

        error = target._delete_member_node(loadbalancer, member, bigip)

        assert target.node_helper.delete.called_once_with(
            bigip, urllib.quote(node['name']), node['partition'])
        assert not error

    def test_delete_member_node_404(self, target, pool_member_service,
                                    mock_logger):
        node = {'name': "name", 'partition': "partition"}
        loadbalancer = pool_member_service['loadbalancer']
        member = pool_member_service['members'][0]
        target.service_adapter.get_member_node.return_value = node
        bigip = Mock()
        target.node_helper.delete.side_effect = MockHTTPError(
            MockHTTPErrorResponse404())

        error = target._delete_member_node(loadbalancer, member, bigip)

        assert target.node_helper.delete.called_once_with(
            bigip, urllib.quote(node['name']), node['partition'])
        assert not error

    def test_delete_member_node_500(self, target, pool_member_service,
                                    mock_logger):
        node = {'name': "name", 'partition': "partition"}
        loadbalancer = pool_member_service['loadbalancer']
        member = pool_member_service['members'][0]
        target.service_adapter.get_member_node.return_value = node
        bigip = Mock()
        target.node_helper.delete.side_effect = MockHTTPError(
            MockHTTPErrorResponse500())

        error = target._delete_member_node(loadbalancer, member, bigip)

        assert target.node_helper.delete.called_once_with(
            bigip, urllib.quote(node['name']), node['partition'])
        assert error

    def test_assure_pool_members_exists(self, target, pool_member_service):
        service = pool_member_service
        pool = dict(name='name', partition='partition')
        target.service_adapter.get_pool.return_value = pool
        target.service_adapter.get_member.return_value = \
            dict(name='member_name', partition='partition')
        p_obj = Mock()
        target.pool_helper.load.return_value = p_obj
        p_obj.members_s.members.exists.return_value = True
        bigips = [Mock()]

        target.assure_pool_members(service, bigips)

        assert target.service_adapter.get_member.call_count == 2
        for member in service['members']:
            assert 'missing' not in member

    def test_assure_pool_members_1_missing(self, target, pool_member_service):
        service = pool_member_service
        pool = dict(name='name', partition='partition')
        target.service_adapter.get_pool.return_value = pool
        target.service_adapter.get_member.return_value = \
            dict(name='member_name', partition='partition')
        p_obj = Mock()
        target.pool_helper.load.return_value = p_obj
        p_obj.members_s.members.exists.side_effect = [False, True]
        bigips = [Mock()]

        target.assure_pool_members(service, bigips)

        assert target.service_adapter.get_member.call_count == 2
        assert 'missing' in service['members'][0]
        assert 'missing' not in service['members'][1]

    def test_assure_pool_members_2_missing(self, target, pool_member_service):
        service = pool_member_service
        pool = dict(name='name', partition='partition')
        target.service_adapter.get_pool.return_value = pool
        target.service_adapter.get_member.return_value = \
            dict(name='member_name', partition='partition')
        p_obj = Mock()
        target.pool_helper.load.return_value = p_obj
        p_obj.members_s.members.exists.return_value = False
        bigips = [Mock()]

        target.assure_pool_members(service, bigips)

        assert target.service_adapter.get_member.call_count == 2
        for member in service['members']:
            assert 'missing' in member

    def test_assure_pool_members_no_pool(self, target, pool_member_service):
        service = pool_member_service
        pool = dict(name='name', partition='partition')
        target.service_adapter.get_pool.return_value = pool
        target.service_adapter.get_member.return_value = \
            dict(name='member_name', partition='partition')
        p_obj = Mock()
        target.pool_helper.load.side_effect = \
            MockHTTPError(MockHTTPErrorResponse400())
        p_obj.members_s.members.exists.return_value = False
        bigips = [Mock()]

        target.assure_pool_members(service, bigips)

        assert target.service_adapter.get_member.call_count == 2
        assert not p_obj.members_s.members.exists.called
        for member in service['members']:
            assert 'missing' in member

    def test_assure_pool_members_pending_delete(
            self, target, pool_member_service):
        service = pool_member_service
        pool = dict(name='name', partition='partition')
        target.service_adapter.get_pool.return_value = pool
        target.service_adapter.get_member.return_value = \
            dict(name='member_name', partition='partition')
        p_obj = Mock()
        target.pool_helper.load.side_effect = \
            MockHTTPError(MockHTTPErrorResponse400())
        p_obj.members_s.members.exists.return_value = False
        target._delete_member_node = Mock()
        bigips = [Mock()]
        service['members'][0]['provisioning_status'] = \
            "PENDING_DELETE"
        target.assure_pool_members(service, bigips)

        assert target.service_adapter.get_member.call_count == 1
        assert target._delete_member_node.call_count == 1
        assert not p_obj.members_s.members.exists.called

        assert 'missing' not in service['members'][0]
        assert 'missing' in service['members'][1]
