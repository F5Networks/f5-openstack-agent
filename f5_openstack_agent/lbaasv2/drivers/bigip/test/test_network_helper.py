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

import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 as const
import f5_openstack_agent.lbaasv2.drivers.bigip.network_helper


class TestNetworkHelperBuilder(object):
    payload = dict(name='name', partition='partition')

    @staticmethod
    @pytest.fixture
    def conf_less_target():
        return f5_openstack_agent.lbaasv2.drivers.bigip.network_helper. \
            NetworkHelper()

    @staticmethod
    @pytest.fixture
    def m_bigip():
        bigip = Mock()
        return bigip


class TestNetworkHelperConstructor(TestNetworkHelperBuilder):

    def build_test(self, test_type=None):
        manipulated_object = None
        if test_type == 'route':
            manipulated_object = self.route
        elif test_type == 'route_domain':
            manipulated_object = self.route_domain
        return tuple([self.target, self.bigip, manipulated_object,
                      self.payload.copy()])

    @pytest.fixture
    def mock_get_route_domain_name(self, target):
        self.target = target
        self.target._get_route_domain_name = Mock()

    @pytest.fixture
    def mock_get_route_name(self, target):
        self.target = target
        self.target._get_route_name = Mock()

    @pytest.fixture
    def populated_bigip(self, m_bigip):
        self.bigip = m_bigip
        self.route = m_bigip.tm.net.routes.route
        self.route_domain = m_bigip.tm.net.route_domains.route_domain

    @staticmethod
    @pytest.fixture
    def target():
        config = Mock()
        return \
            f5_openstack_agent.lbaasv2.drivers.bigip.network_helper. \
            NetworkHelper(config)


class TestNetworkHelper(TestNetworkHelperConstructor):
    def test__init__(self, target, conf_less_target):
        assert hasattr(target, 'conf')
        assert not hasattr(conf_less_target, 'conf')

    def test__get_route_domain_name(self, target, conf_less_target):
        name = 'foo'
        target.conf.external_gateway_mode = True
        rd_name = target._get_route_domain_name(name)
        assert rd_name == 'rd-{}'.format(name)
        non_rd_name = conf_less_target._get_route_domain_name(name)
        assert non_rd_name != \
            rd_name
        assert non_rd_name == name
        assert rd_name == target._get_route_domain_name(name)
        target.conf.external_gateway_mode = False
        assert rd_name != target._get_route_domain_name(name)

    def test__get_route_name(self, target, conf_less_target):
        name = 'foo'
        target.conf.external_gateway_mode = True
        rt_name = target._get_route_name(name)
        assert rt_name == 'rt-{}'.format(name)
        with pytest.raises(NotImplementedError):
            conf_less_target._get_route_name(name)
        target.conf.external_gateway_mode = False
        with pytest.raises(NotImplementedError):
            target._get_route_name(name)

    def test_route_defailts(self, conf_less_target):
        target = conf_less_target
        """Tests the default template attribute 'route_defaults'"""
        assert not target.route_defaults.get('name', 'something')
        assert target.route_defaults.get('partition', 'diff') \
            == "/{}".format(const.DEFAULT_PARTITION)

    def test_route_domain_exists(self, mock_get_route_domain_name,
                                 populated_bigip):
        test_args = self.build_test('route_domain')
        my_target, my_bigip, route_domain, payload = test_args
        payload.update(dict(domain_id='domain_id'))

        def positive_case_with_domain_id(my_target, my_bigip, route_domain,
                                         payload):
            my_target.conf.external_gateway_mode = True
            my_target._get_route_domain_name.return_value = payload['name']
            route_domain.exists.return_value = True
            assert my_target.route_domain_exists(my_bigip, **payload)
            route_domain.exists.called_once_with(
                partition=payload['partition'],
                name="{}_aux_{}".format(payload.pop('name'),
                                        payload.pop('domain_id')))

        def name_e_partition_negative_case(my_target, my_bigip, route_domain,
                                           payload):
            # test name == partition negative case
            route_domain.exists.reset_mock()
            route_domain.exists.return_value = False  # sets our negative
            assert not my_target.route_domain_exists(my_bigip, **payload)
            route_domain.exists.called_once_with(
                partition=payload['partition'], name=payload['partition'])
            # test short-cut case of Common
            # delattr(self, 'conf')
            my_target.conf.external_gateway_mode = False
            assert my_target.route_domain_exists(my_bigip, partition='Common')

        positive_case_with_domain_id(*test_args)
        name_e_partition_negative_case(*test_args)

    def test_get_route_domain(self, mock_get_route_domain_name,
                              populated_bigip):
        test_args = self.build_test(test_type='route_domain')
        my_target, my_bigip, route_domain, payload = test_args

        def reset_load(rout_domain):
            route_domain.load.reset_mock()

        def positive_case_differing_name(
                my_target, my_bigip, route_domain, payload):
            my_target.conf.external_gateway_mode = True
            route_domain.load.return_value = True
            my_target._get_route_domain_name.return_value = payload['name']
            assert my_target.get_route_domain(my_bigip, **payload)
            route_domain.load.assert_called_once_with(**payload)

        def positive_case_same_name_common_networks(
                my_target, my_bigip, route_domain, payload):
            assert my_target.get_route_domain(
                my_bigip, partition=payload['partition'])
            route_domain.load.assert_called_once_with(
                name=payload['partition'], partition=payload['partition'])

        def positive_case_same_name(
                my_target, my_bigip, route_domain, payload):
            delattr(my_target, 'conf')
            assert my_target.get_route_domain(my_bigip, payload['partition'])
            route_domain.load.assert_called_once_with(
                name=payload['partition'], partition=payload['partition'])

        def negative_case_partition_is_common(
                my_target, my_bigip, route_domain, payload):
            route_domain.load.reset_mock()
            route_domain.load.return_value = False
            assert not my_target.get_route_domain(my_bigip)
            route_domain.load.assert_called_once_with(
                name='0',
                partition=const.DEFAULT_PARTITION)

        for test in [positive_case_differing_name,
                     positive_case_same_name_common_networks,
                     positive_case_same_name,
                     negative_case_partition_is_common]:
            test(*test_args)
            reset_load(route_domain)

    def test_delete_route_domain_by_id(self, mock_get_route_domain_name,
                                       populated_bigip):
        test_args = list(self.build_test(test_type='route_domain'))
        my_target, my_bigip, route_domain, payload = test_args
        delete = route_domain.load().delete
        test_args.append(delete)
        route_domain.load.reset_mock()

        def reset_load(rout_domain, delete):
            delete.reset_mock()
            route_domain.load.reset_mock()

        def case_differing_name(
                my_target, my_bigip, route_domain, payload, delete):
            my_target.conf.external_gateway_mode = True
            my_target._get_route_domain_name.return_value = payload['name']
            my_target.delete_route_domain(my_bigip, **payload)
            my_target._get_route_domain_name.assert_called_once_with(
                payload['name'])
            delete.assert_called_once_with()
            route_domain.load.assert_called_once_with(**payload)

        def case_same_name_common_networks(
                my_target, my_bigip, route_domain, payload, delete):
            my_target.delete_route_domain(
                my_bigip, partition=payload['partition'])
            delete.assert_called_once_with()
            route_domain.load.assert_called_once_with(
                name=payload['partition'], partition=payload['partition'])

        def case_same_name(
                my_target, my_bigip, route_domain, payload, delete):
            delattr(my_target, 'conf')
            my_target.delete_route_domain(my_bigip, payload['partition'])
            delete.assert_called_once_with()
            route_domain.load.assert_called_once_with(
                name=payload['partition'], partition=payload['partition'])

        def case_partition_is_common(
                my_target, my_bigip, route_domain, payload, delete):
            my_target.delete_route_domain(my_bigip)
            delete.assert_called_once_with()
            route_domain.load.called_once_with(
                name=const.DEFAULT_PARTITION,
                partition=const.DEFAULT_PARTITION)

        for test in [case_differing_name,
                     case_same_name_common_networks,
                     case_same_name,
                     case_partition_is_common]:
            test(*test_args)
            reset_load(route_domain, delete)

    def test_route_exists(self, mock_get_route_name, populated_bigip):
        test_args = self.build_test('route')

        def positive_case(my_target, my_bigip, route, payload):
            route_name = "foo-{}".format(payload['name'])
            route.exists.return_value = True
            my_target._get_route_name.return_value = route_name
            assert my_target.route_exists(my_bigip, **payload)
            route.exists.assert_called_once_with(
                name=route_name, partition=payload['partition'])

        positive_case(*test_args)

    def test_get_route(self, mock_get_route_name, populated_bigip):
        test_args = self.build_test('route')

        def positive_case(my_target, my_bigip, route, payload):
            route_name = "foo-{}".format(payload['name'])
            my_target._get_route_name.return_value = route_name
            expected = 'expected'
            route.load.return_value = expected
            assert my_target.get_route(my_bigip, **payload) == expected
            route.load.assert_called_once_with(
                name=route_name, partition=payload['partition'])

        positive_case(*test_args)

    def test_create_route(self, mock_get_route_name, populated_bigip):
        test_args = self.build_test('route')
        my_target, my_bigip, route, payload = test_args
        payload.update(dict(gateway_ip='gateway', rd_id='rd_id',
                            destination_ip='destination', netmask='netmask'))
        my_target.route_exists = Mock()

        def clear_values(my_target, route, my_bigip, payload):
            my_target.route_exists.reset_mock()
            route.create.reset_mock()
            my_target._get_route_name.reset_mock()

        def already_exists(my_target, route, my_bigip, payload):
            my_target.route_exists.return_value = True
            expected_name = "foo-{}".format(payload['name'])
            my_target._get_route_name.return_value = expected_name
            my_target.create_route(my_bigip, **payload)
            my_target.route_exists.assert_called_once_with(
                my_bigip, name=expected_name, partition=payload['partition'])
            route.create.assert_not_called()
            my_target._get_route_name.assert_called_once_with(payload['name'])

        def positive_case(my_target, my_bigip, route, payload):
            my_target.route_exists.return_value = False
            expected_name = "foo-{}".format(payload['name'])
            my_target._get_route_name.return_value = expected_name
            expected_destination = '{}%{}/{}'.format(
                payload['destination_ip'], payload['rd_id'],
                payload['netmask'])
            expected_gateway = '{}%{}'.format(payload['gateway_ip'],
                                              payload['rd_id'])
            expected_payload = dict(
                name=expected_name, partition=payload['partition'])
            my_target.create_route(my_bigip, **payload)
            my_target.route_exists.assert_called_once_with(
                my_bigip, **expected_payload)
            my_target._get_route_name.assert_called_once_with(payload['name'])
            expected_payload.update(dict(network=expected_destination,
                                         gw=expected_gateway))
            route.create.assert_called_once_with(**expected_payload)

        already_exists(*test_args)
        clear_values(*test_args)
        positive_case(*test_args)

    def test_delete_route(self, mock_get_route_name, populated_bigip):
        test_args = list(self.build_test('route'))
        my_target, my_bigip, route, payload = test_args
        my_target._get_route_name = Mock()
        my_target.get_route = Mock()
        my_target.route_exists = Mock()
        delete = my_target.get_route().delete
        my_target.get_route.reset_mock()
        test_args.append(delete)
        expected_name = "rt-{}".format(payload['name'])
        my_target._get_route_name.return_value = expected_name

        def reset_tests(my_target, my_bigip, route, payload, delete):
            delete.reset_mock()
            my_target._get_route_name.reset_mock()
            my_target.get_route.reset_mock()
            my_target.route_exists.reset_mock()

        def negative_case(my_target, my_bigip, route, payload, delete):
            my_target.route_exists.return_value = False
            my_target.delete_route(my_bigip, **payload)
            my_target.route_exists.assert_called_once_with(
                my_bigip, partition=payload['partition'], name=expected_name)
            my_target.get_route.assert_not_called()

        def positive_case(my_target, my_bigip, route, payload, delete):
            my_target.route_exists.return_value = True
            my_target.delete_route(my_bigip, **payload)
            expected_payload = payload.copy()
            expected_payload.update(dict(name=expected_name))
            my_target.get_route.assert_called_once_with(
                my_bigip, **expected_payload)
            delete.assert_called_once()

        negative_case(*test_args)
        reset_tests(*test_args)
        positive_case(*test_args)
