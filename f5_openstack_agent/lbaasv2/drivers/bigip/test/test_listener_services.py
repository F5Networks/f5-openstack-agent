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

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from requests import HTTPError

import f5_openstack_agent.lbaasv2.drivers.bigip.listener_service \
    as listener_service
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


class TestListenerServiceBuilderConstructor(ct.TestingWithServiceConstructor):
    # contains all quick service-related creation items
    # contains all static, class, or non-intelligent object manipulations
    @staticmethod
    def creation_mode_listener(svc, listener):
        svc['listener'] = listener
        svc['listener']['provisioning_status'] = constants_v2.F5_PENDING_CREATE
        svc['loadbalancer']['provisioning_status'] = \
            constants_v2.F5_PENDING_UPDATE


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
        assert self.logger.debug.call_count == 1
        assert 'ListenerServiceBuilder' in self.logger.debug.call_args[0][0]
        assert isinstance(target.cert_manager, Mock)
        assert isinstance(target.parent_ssl_profile, Mock)
        assert isinstance(target.parent_ssl_profile, Mock)
        self.resource_bigip.assert_called_once_with(
            self.resource_type.virtual)

    def test_create_listener(self, target, service_with_loadbalancer,
                             service_with_listener):
        svc = service_with_listener

        def clean_target(self, target):
            target.vs_helper.reset_mock()
            target.vs_helper.update.reset_mock()
            target.vs_helper.create.reset_mock()
            svc = self.clean_svc_with_listener()
            self.creation_mode_listener(svc, svc['listeners'][0])
            return target, svc

        def create_basic_listener_200(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            bigips = [Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert not retval
            assert not target.vs_helper.update.called

        def create_basic_listener_200_two_bigip(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            bigips = [Mock(), Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert not retval
            assert not target.vs_helper.update.called

        def create_basic_listener_409(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse409())
            bigips = [Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert not retval
            assert target.vs_helper.update.called

        def create_basic_listener_400(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse400())
            bigips = [Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert retval
            assert not target.vs_helper.update.called

        def create_basic_listener_exception(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = MockError()

            bigips = [Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert retval
            assert not target.vs_helper.update.called

        def create_basic_listener_update_exception(target,
                                                   service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = MockHTTPError(
                MockHTTPErrorResponse409())
            target.vs_helper.update.side_effect = MockError()

            bigips = [Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert retval
            assert target.vs_helper.update.called

        self.creation_mode_listener(svc, svc['listeners'][0])
        create_basic_listener_200(target, svc)
        create_basic_listener_200_two_bigip(target, svc)
        create_basic_listener_409(target, svc)
        clean_target(self, target)
        create_basic_listener_400(target, svc)
        create_basic_listener_exception(target, svc)
        create_basic_listener_update_exception(target, svc)

    def test_delete_listener(self, target, service_with_loadbalancer,
                             service_with_listener):
        svc = service_with_listener

        def clean_target(self, target):
            target.vs_helper.reset_mock()
            target.vs_helper.create.reset_mock()
            target.vs_helper.update.reset_mock()
            target.vs_helper.delete.reset_mock()

            svc = self.clean_svc_with_listener()
            self.creation_mode_listener(svc, svc['listeners'][0])
            return target, svc

        def delete_listener_200(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual_name.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            bigips = [Mock()]
            retval = target.delete_listener(service_with_listener, bigips)

            assert not retval

        def delete_listener_200_two_bigip(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual_name.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            bigips = [Mock(), Mock()]
            retval = target.delete_listener(service_with_listener, bigips)

            assert not retval

        def delete_listener_404(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual_name.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.delete.side_effect = MockHTTPError(
                MockHTTPErrorResponse404())
            bigips = [Mock()]
            retval = target.delete_listener(service_with_listener, bigips)

            assert not retval

        def delete_listener_400(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual_name.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.delete.side_effect = MockHTTPError(
                MockHTTPErrorResponse400())
            bigips = [Mock()]
            retval = target.delete_listener(service_with_listener, bigips)

            assert retval

        def delete_listener_exception(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual_name.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.delete.side_effect = MockError()

            bigips = [Mock()]
            retval = target.delete_listener(service_with_listener, bigips)

            assert retval

        self.creation_mode_listener(svc, svc['listeners'][0])
        delete_listener_200(target, svc)
        delete_listener_200_two_bigip(target, svc)
        delete_listener_404(target, svc)
        clean_target(self, target)
        delete_listener_400(target, svc)
        delete_listener_exception(target, svc)

    def test_create_listener_two_bigip(self, target, service_with_loadbalancer,
                                       service_with_listener):
        svc = service_with_listener

        def clean_target(self, target):
            target.vs_helper.reset_mock()
            target.vs_helper.update.reset_mock()
            target.vs_helper.create.reset_mock()
            svc = self.clean_svc_with_listener()
            self.creation_mode_listener(svc, svc['listeners'][0])
            return target, svc

        def create_listener_two_bigip_noerror(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            bigips = [Mock(), Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert not retval
            assert not target.vs_helper.update.called

        def create_listener_two_bigip_error_noerror(target,
                                                    service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = [MockError(), None]
            bigips = [Mock(), Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert retval
            assert not target.vs_helper.update.called

        def create_listener_two_bigip_409_noerror(target,
                                                  service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = [
                MockHTTPError(MockHTTPErrorResponse409()), None]
            bigips = [Mock(), Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert not retval
            assert target.vs_helper.update.called

        def create_listener_two_bigip_409_409(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            vs = dict(name='name', partition='partition')
            tls = dict()
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = tls
            target.vs_helper.create.side_effect = [
                MockHTTPError(MockHTTPErrorResponse409()),
                MockHTTPError(MockHTTPErrorResponse409())]
            bigips = [Mock(), Mock()]
            retval = target.create_listener(service_with_listener, bigips)

            assert not retval
            assert target.vs_helper.update.called

        self.creation_mode_listener(svc, svc['listeners'][0])
        create_listener_two_bigip_noerror(target, svc)
        clean_target(self, target)
        create_listener_two_bigip_error_noerror(target, svc)
        target, svc = clean_target(self, target)
        create_listener_two_bigip_409_noerror(target, svc)

        target, svc = clean_target(self, target)
        create_listener_two_bigip_409_noerror(target, svc)

    def test_add_ssl_profile(self, target, service_with_listener):
        svc = service_with_listener

        def add_ssl_profile_no_tls_or_sni(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            tls = dict(name='name', partition='partition')
            bigip = Mock()
            target._create_ssl_profile = Mock()
            vip = {}

            target.add_ssl_profile(tls, vip, bigip)

            assert not target._create_ssl_profile.called

        def add_ssl_profile_one_tls_no_sni(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            tls = dict(name='name', partition='partition')
            tls['default_tls_container_id'] = '12345'
            bigip = Mock()
            target._create_ssl_profile = Mock()
            vip = dict(name='name', partition='partition')

            target.add_ssl_profile(tls, vip, bigip)

            assert target._create_ssl_profile.call_count == 1
            target._create_ssl_profile.assert_called_once_with(
                '12345', bigip, dict(name='name', partition='partition'),
                True)

        def add_ssl_profile_no_tls_one_sni(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            tls = dict(name='name', partition='partition')
            sni_container = dict(tls_container_id="12345")
            tls['sni_containers'] = [sni_container]
            bigip = Mock()
            target._create_ssl_profile = Mock()
            vip = dict(name='name', partition='partition')

            target.add_ssl_profile(tls, vip, bigip)

            assert target._create_ssl_profile.call_count == 1
            target._create_ssl_profile.assert_called_once_with(
                '12345', bigip, dict(name='name', partition='partition'),
                False)

        self.creation_mode_listener(svc, svc['listeners'][0])
        add_ssl_profile_no_tls_or_sni(target, svc)
        add_ssl_profile_one_tls_no_sni(target, svc)
        add_ssl_profile_no_tls_one_sni(target, svc)

    def test_remove_ssl_profile(self, target, service_with_listener):
        svc = service_with_listener

        def delete_ssl_profile_no_tls_or_sni(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            tls = dict(name='name', partition='partition')
            bigip = Mock()
            target._remove_ssl_profile = Mock()

            target.remove_ssl_profiles(tls, bigip)

            assert not target._remove_ssl_profile.called

        def delete_ssl_profile_one_tls_no_sni(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            tls = dict(name='name', partition='partition')
            tls['default_tls_container_id'] = '12345/6789'
            bigip = Mock()
            target._remove_ssl_profile = Mock()
            target.service_adapter.prefix = "pre_"

            target.remove_ssl_profiles(tls, bigip)

            assert target._remove_ssl_profile.call_count == 1
            target._remove_ssl_profile.assert_called_once_with(
                'pre_6789', bigip)

            tls['default_tls_container_id'] = '123456789'
            target._remove_ssl_profile.reset_mock()

            target.remove_ssl_profiles(tls, bigip)

            assert not target._remove_ssl_profile.called

        def delete_ssl_profile_no_tls_one_sni(target, service_with_listener):
            svc['listener']['protocol'] = 'HTTP'
            tls = dict(name='name', partition='partition')
            bigip = Mock()
            target._remove_ssl_profile = Mock()
            target.service_adapter = Mock()
            target.service_adapter.prefix = "pre_"

            sni_container = dict(tls_container_id="123/45")
            tls['sni_containers'] = [sni_container]

            target.remove_ssl_profiles(tls, bigip)

            assert target._remove_ssl_profile.call_count == 1
            target._remove_ssl_profile.assert_called_once_with(
                'pre_45', bigip)

            sni_container = dict(tls_container_id="12345")
            tls['sni_containers'] = [sni_container]
            target._remove_ssl_profile.reset_mock()

            target.remove_ssl_profiles(tls, bigip)

            assert not target._remove_ssl_profile.called

        self.creation_mode_listener(svc, svc['listeners'][0])
        delete_ssl_profile_no_tls_or_sni(target, svc)
        delete_ssl_profile_one_tls_no_sni(target, svc)
        delete_ssl_profile_no_tls_one_sni(target, svc)

    @pytest.mark.skip(reason="ESD implementation not valid")
    def test_apply_esd(self, target, service_with_loadbalancer, esd,
                       service_with_listener):
        svc = service_with_listener

        def clean_target(self, target):
            target.vs_helper.update.reset_mock()
            svc = self.clean_svc_with_listener()
            self.creation_mode_listener(svc, svc['listeners'][0])
            esd = self.esd()
            return target, svc, esd

        def setup_profiles(esd):
            context = 'clientside'
            partition = 'Common'
            profiles_ref = \
                {'lbaas_stcp': dict(name=esd['lbaas_stcp'],
                                    partition=partition, context='serverside'),
                 'lbaas_ctcp': dict(name=esd['lbaas_ctcp'],
                                    partition=partition, context=context),
                 'lbaas_cssl_profile': dict(name=esd['lbaas_cssl_profile'],
                                            partition=partition,
                                            context=context),
                 'lbaas_sssl_profile': dict(name=esd['lbaas_sssl_profile'],
                                            partition=partition,
                                            context='serverside')}
            profiles = \
                [profiles_ref['lbaas_stcp'], profiles_ref['lbaas_ctcp'],
                 profiles_ref['lbaas_cssl_profile'],
                 profiles_ref['lbaas_sssl_profile']]
            return profiles, profiles_ref

        def setup_update_attrs(esd, profiles=None):
            irules = map(lambda x: '/Common/{}'.format(x), esd['lbaas_irule'])
            policies = map(lambda x: dict(name=x, partition='Common'),
                           esd['lbaas_policy'])
            update_attrs = {'persist': [dict(name=esd['lbaas_persist'])],
                            'fallbackPersistence':
                            esd['lbaas_fallback_persist'],
                            'rules': irules,
                            'policies': policies}
            if profiles:
                update_attrs['profiles'] = profiles
            return update_attrs

        def positive_non_tcp_stcp_ctcp(target, svc, esd):
            target.service_adapter.get_virtual_name.return_value = dict()
            expected_profiles, profiles_ref = setup_profiles(esd)
            expected_profiles.append(dict(name='http', partition='Common',
                                          context='all'))
            expected_profiles.append(dict(name='oneconnect',
                                          partition='Common', context='all'))
            expected_update_attrs = setup_update_attrs(esd, expected_profiles)
            bigips = [Mock()]
            target.apply_esd(svc, esd, bigips)
            target.vs_helper.update.assert_called_once_with(
                bigips[0], expected_update_attrs)

        def positive_tcp(target, svc, esd):
            target.service_adapter.get_virtual_name.return_value = dict()
            svc['listener']['protocol'] = 'TCP'
            expected_profiles, profiles_ref = setup_profiles(esd)
            map(lambda x: esd.pop(x), ['lbaas_stcp', 'lbaas_ctcp'])
            expected_profiles.remove(profiles_ref['lbaas_stcp'])
            profiles_ref['lbaas_ctcp']['name'] = 'tcp'
            profiles_ref['lbaas_ctcp']['context'] = 'all'
            expected_update_attrs = setup_update_attrs(esd, expected_profiles)
            bigips = [Mock()]
            target.apply_esd(svc, esd, bigips)
            target.vs_helper.update.assert_called_once_with(
                bigips[0], expected_update_attrs)

        def positive_no_listener(target, svc, esd):
            # based upon the original code, this is a repeat in logic...
            svc.pop('listener')
            positive_non_tcp_stcp_ctcp(target, svc, esd)

        self.creation_mode_listener(svc, svc['listeners'][0])
        positive_non_tcp_stcp_ctcp(target, svc, esd)
        positive_tcp(*clean_target(self, target))
        target, svc, esd = clean_target(self, target)
        positive_no_listener(target, service_with_loadbalancer, esd)

    @pytest.mark.skip(reason="ESD implementation changed")
    def test_remove_esd(self, target, service_with_listener, esd):
        svc = service_with_listener

        def negative_full_path(target, svc, esd):
            svc['listener']['protocol'] = 'TCP'
            vs = dict(name='name', partition='partition')
            expected_tls = vs.copy()
            tls = dict(foo='bar')
            expected_tls.update(tls)
            target.service_adapter.get_virtual.return_value = vs
            target.service_adapter.get_tls.return_value = dict(foo='bar')
            target.service_adapter.get_session_persistence.return_value = tls
            bigips = ['foobar']
            svc['pool'] = 'foobar'  # may want more intelligence later...
            target.add_ssl_profile = Mock(side_effect=AssertionError)
            with pytest.raises(AssertionError):
                target.remove_esd(svc, esd, bigips)
            assert self.logger.exception.call_count == 1
            target.service_adapter.get_virtual.assert_called_once_with(svc)
            target.service_adapter.get_session_persistence.\
                assert_called_once_with(svc)
            target.vs_helper.update.assert_called_once_with(
                bigips[0], vs)
            target.service_adapter.get_tls.assert_called_once_with(svc)
            target.add_ssl_profile.assert_called_once_with(
                expected_tls, bigips[0])

        self.creation_mode_listener(svc, svc['listeners'][0])
        negative_full_path(target, svc, esd)
