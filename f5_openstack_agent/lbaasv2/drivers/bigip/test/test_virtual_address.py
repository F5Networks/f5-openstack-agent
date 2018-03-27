# coding=utf-8
# Copyright (c) 2014-2018, F5 Networks, Inc.
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

import f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address as \
    virtual_address

from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address import \
    VirtualAddress

import mock
import pytest
import uuid


class TestVirtualAddressConstructor(object):

    @staticmethod
    @pytest.fixture
    def bigip():
        bigip = mock.Mock()

        return bigip

    @staticmethod
    @pytest.fixture
    def adapter():
        conf = mock.MagicMock()
        conf.environment_prefix = "Project"

        return ServiceModelAdapter(conf)

    @staticmethod
    @pytest.fixture
    def new_uuid():
        return str(uuid.uuid4())

    @staticmethod
    @pytest.fixture
    def loadbalancer(new_uuid):
        loadbalancer = {"name": "lb1",
                        "tenant_id": new_uuid,
                        "id": "loadbalancer_id",
                        "traffic_group": "traffic-group-local-only",
                        "vip_address": "192.168.100.5",
                        "admin_state_up": True}

        return loadbalancer

    @staticmethod
    @pytest.fixture
    def virtual_address(adapter, loadbalancer):
        va = VirtualAddress(adapter, loadbalancer)
        return va


class TestVirtualAddressBuilder(TestVirtualAddressConstructor):

    @pytest.fixture
    def mock_logger(self, request):
        logger = mock.Mock()
        request.addfinalizer(self.cleanup)
        self.freeze_log = virtual_address.LOG
        virtual_address.LOG = logger
        self.logger = logger
        return logger

    def cleanup(self):
        virtual_address.LOG = self.freeze_log

    @staticmethod
    def mock_scenario(virtual_address):
        m_remote = mock.Mock()
        m_remote.address = virtual_address.model().get('address')
        virtual_address.load = mock.Mock(return_value=m_remote)
        virtual_address.virtual_address = mock.Mock()
        virtual_address.delete = mock.Mock(side_effect=AssertionError)
        virtual_address.create = mock.Mock(return_value=mock.Mock())
        virtual_address.virtual_address.update = \
            mock.Mock(return_value=mock.Mock())


class TestVirtualAddress(TestVirtualAddressBuilder):

    def test_create_va(self, virtual_address):
        assert(virtual_address is not None)
        assert(virtual_address.name == "Project_loadbalancer_id")
        assert virtual_address.partition.startswith(
            virtual_address.adapter.prefix)
        assert(virtual_address.address == "192.168.100.5")
        assert(virtual_address.traffic_group == "traffic-group-local-only")
        assert(virtual_address.description == "lb1:")
        assert(virtual_address.enabled == "yes")

    def test_iwb_update(self, virtual_address, bigip, mock_logger):
        def negative_delete_path(virtual_address, bigip):
            TestVirtualAddressBuilder.mock_scenario(virtual_address)
            virtual_address.load.return_value.address = 'xx.xx.xx.xx'
            result = virtual_address.update(bigip)
            virtual_address.load.assert_called_once_with(bigip)
            assert result is virtual_address.create.return_value
            assert self.logger.error.call_count == 1

        def positive_update(virtual_address, bigip):
            TestVirtualAddressBuilder.mock_scenario(virtual_address)
            result = virtual_address.update(bigip)
            expected = virtual_address.model()
            expected.pop('address')
            virtual_address.virtual_address.update.assert_called_once_with(
                bigip, expected)
            assert result is \
                virtual_address.virtual_address.update.return_value

        negative_delete_path(virtual_address, bigip)
        virtual_address = \
            self.virtual_address(self.adapter(),
                                 self.loadbalancer(self.new_uuid()))
        positive_update(virtual_address, bigip)
