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

import f5_openstack_agent.lbaasv2.drivers.bigip.utils as utils
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import IpNotInCidrNotation

import mock
import pytest


class TestUtils(object):
    def test_strip_domain_address_no_mask(self):
        addr = utils.strip_domain_address("192.168.1.1%20")
        assert addr == '192.168.1.1'

    def test_strip_domain_address_mask(self):
        domain = utils.strip_domain_address('192.168.1.1%20/24')
        assert domain == "192.168.1.1/24"

    def test_request_index_0(self):
        request_q = [
            [1, 2, 3],
            [2, 4, 6],
            [3, 6, 9]
        ]
        index = utils.request_index(request_q, 1)
        assert index == 0

    def test_request_index_1(self):
        request_q = [
            [1, 2, 3],
            [2, 4, 6],
            [3, 6, 9]
        ]
        index = utils.request_index(request_q, 2)
        assert index == 1

    def test_request_index_none(self):
        request_q = [
            [1, 2, 3],
            [2, 4, 6],
            [3, 6, 9]
        ]
        index = utils.request_index(request_q, 99)
        assert index == len(request_q)

    def test_get_filter_v11_5(self):
        bigip = mock.MagicMock()
        bigip.tmos_version = "11.5"
        f = utils.get_filter(bigip, 'partition', 'eq', 'Common')
        assert f == '$filter=partition+eq+Common'

    def test_get_filter_v11_5_4(self):
        bigip = mock.MagicMock()
        bigip.tmos_version = "11.5.4"
        f = utils.get_filter(bigip, 'partition', 'eq', 'Common')
        assert f == '$filter=partition+eq+Common'

    def test_get_filter_v11_6_0(self):
        bigip = mock.MagicMock()
        bigip.tmos_version = "11.6.0"
        f = utils.get_filter(bigip, 'partition', 'eq', 'Common')
        assert isinstance(f, dict)
        assert f == {'$filter': 'partition eq Common'}

    def test_get_filter_v12_1_0(self):
        bigip = mock.MagicMock()
        bigip.tmos_version = "12.1.0"
        f = utils.get_filter(bigip, 'partition', 'eq', 'Common')
        assert isinstance(f, dict)
        assert f == {'$filter': 'partition eq Common'}

    def test_strip_cidr_netmask(self):
        addy = utils.strip_cidr_netmask('10.1.1.1/21')
        assert addy == '10.1.1.1'

    def test_strip_cidr_netmask_exception(self):
        with pytest.raises(IpNotInCidrNotation) as ex:
            utils.strip_cidr_netmask('10.1.1.1')
        assert '' in ex.value.message

    def test_get_device_info(self):
        bigip = mock.MagicMock()
        device = mock.MagicMock()
        device.selfDevice = 'true'
        bigip.tm.cm.devices.get_collection.return_value = [device]
        ret = utils.get_device_info(bigip)
        assert ret is device
