# coding=utf-8
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

from f5_openstack_agent.lbaasv2.drivers.bigip.esd_filehandler import \
    EsdTagProcessor


@pytest.fixture(scope='session')
def bigips(mgmt_root):
    return [mgmt_root]


class TestEsd(object):
    def test_invalid_esd_name(self, bigips):
        processor = EsdTagProcessor('tests/functional/esd/json/')
        processor.process_esd(bigips)

        # validate that invalid ESD name is handled correctly
        assert processor.get_esd('abc') is None

    def test_valid_esd_name(self, bigips):
        processor = EsdTagProcessor('tests/functional/esd/json/')
        processor.process_esd(bigips)

        # app_type_1 should be valid
        app_type_1 = processor.get_esd('app_type_1')
        assert app_type_1 is not None
        assert 'lbaas_cssl_profile' in app_type_1

    def test_invalid_tag_value(self, bigips):
        processor = EsdTagProcessor('tests/functional/esd/json/')
        processor.process_esd(bigips)

        # app_type_2 only has one tag with an invalid value; should not be
        # in final set of ESDs
        assert processor.get_esd('app_type_2') is None

    def test_invalid_tag_name(self, bigips):
        processor = EsdTagProcessor('tests/functional/esd/json/')
        processor.process_esd(bigips)

        # app_type_4 has a mix of both valid and invalid tag values
        app_type_4 = processor.get_esd('app_type_4')
        assert app_type_4 is not None

        # invalid tag name
        assert 'lbaas_invalid_tag_name' not in app_type_4

    def test_valid_tag_values(self, bigips):
        processor = EsdTagProcessor('tests/functional/esd/json/')
        processor.process_esd(bigips)

        # app_type_4 has a mix of both valid and invalid tag values
        app_type_4 = processor.get_esd('app_type_4')
        assert app_type_4 is not None

        # valid tag value
        assert 'lbaas_sssl_profile' in app_type_4
        assert 'lbaas_cssl_chain_cert' in app_type_4
