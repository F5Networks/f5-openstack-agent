# coding=utf-8
# Copyright 2014-2016 F5 Networks Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address import \
    VirtualAddress

import mock
import pytest


class TestVirtualAddress(object):

    @pytest.fixture
    def bigip(self):
        bigip = mock.MagicMock()

        return bigip

    @pytest.fixture
    def adapter(self):
        conf = mock.MagicMock()
        conf.environment_prefix = "Project"

        return ServiceModelAdapter(conf)

    @pytest.fixture
    def loadbalancer(self):
        loadbalancer = {"name": "lb1",
                        "tenant_id": "123456789",
                        "id": "loadbalancer_id",
                        "traffic_group": "traffic-group-local-only",
                        "vip_address": "192.168.100.5"}

        return loadbalancer

    def test_create_va(self, bigip, adapter, loadbalancer):
        va = VirtualAddress(adapter, loadbalancer)

        assert(va is not None)
        assert(va.name == "Project_loadbalancer_id")
        assert(va.partition == "Project_123456789")
        assert(va.address == "192.168.100.5")
        assert(va.traffic_group == "traffic-group-local-only")
        assert(va.description == "lb1:")
