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

from mock import Mock

from requests import HTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip import l7policy_service


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


@pytest.fixture
def policy_service():
    policy_service = l7policy_service.L7PolicyService(Mock())
    policy_service.policy_helper = Mock()
    policy_service.policy_helper.create = Mock()
    policy_service.policy_helper.update = Mock()
    policy_service.policy_helper.delete = Mock()

    return policy_service


def test_create_l7policy_no_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]

    return_value = target.create_l7policy(test_policy, bigips)

    assert not return_value


def test_create_l7policy_409(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    target.policy_helper.create.side_effect = MockHTTPError(
        MockHTTPErrorResponse409())

    return_value = target.create_l7policy(test_policy, bigips)

    assert target.policy_helper.create.called
    assert target.policy_helper.update.called

    assert not return_value


def test_create_l7policy_404(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    target.policy_helper.create.side_effect = MockHTTPError(
        MockHTTPErrorResponse404(), "not found")

    return_value = target.create_l7policy(test_policy, bigips)

    assert target.policy_helper.create.called
    assert not target.policy_helper.update.called

    assert isinstance(return_value, f5_ex.L7PolicyCreationException)


def test_create_l7policy_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    target.policy_helper.create.side_effect = MockError()

    return_value = target.create_l7policy(test_policy, bigips)

    assert target.policy_helper.create.called
    assert not target.policy_helper.update.called

    assert isinstance(return_value, f5_ex.L7PolicyCreationException)


def test_create_l7policy_update_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    target.policy_helper.create.side_effect = MockHTTPError(
        MockHTTPErrorResponse409())
    target.policy_helper.update.side_effect = MockError()

    return_value = target.create_l7policy(test_policy, bigips)

    assert target.policy_helper.create.called
    assert target.policy_helper.update.called

    assert isinstance(return_value, f5_ex.L7PolicyUpdateException)


def test_delete_l7policy(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    test_policy = dict(name='test_policy', partition='test')

    return_value = target.delete_l7policy(test_policy, bigips)

    assert target.policy_helper.delete.called

    assert not return_value


def test_delete_l7policy_404_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    test_policy = dict(name='test_policy', partition='test')
    target.policy_helper.delete.side_effect = MockHTTPError(
        MockHTTPErrorResponse404())

    return_value = target.delete_l7policy(test_policy, bigips)

    assert target.policy_helper.delete.called

    assert not return_value


def test_delete_l7policy_400_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    test_policy = dict(name='test_policy', partition='test')
    target.policy_helper.delete.side_effect = MockHTTPError(
        MockHTTPErrorResponse400())

    return_value = target.delete_l7policy(test_policy, bigips)

    assert target.policy_helper.delete.called
    assert isinstance(return_value, f5_ex.L7PolicyDeleteException)


def test_delete_l7policy_500_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    test_policy = dict(name='test_policy', partition='test')
    target.policy_helper.delete.side_effect = MockHTTPError(
        MockHTTPErrorResponse500())

    return_value = target.delete_l7policy(test_policy, bigips)

    assert target.policy_helper.delete.called
    assert isinstance(return_value, f5_ex.L7PolicyDeleteException)


def test_delete_l7policy_general_error(policy_service):

    target = policy_service
    test_policy = Mock()
    bigips = [Mock()]
    test_policy = dict(name='test_policy', partition='test')
    target.policy_helper.delete.side_effect = MockError()

    return_value = target.delete_l7policy(test_policy, bigips)

    assert target.policy_helper.delete.called
    assert isinstance(return_value, f5_ex.L7PolicyDeleteException)
