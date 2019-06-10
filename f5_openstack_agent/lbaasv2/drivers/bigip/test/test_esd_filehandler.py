# coding=utf-8
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

from f5_openstack_agent.lbaasv2.drivers.bigip.esd_filehandler import \
    EsdTagProcessor
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex


class TestEsdFileHanlder(object):
    remaining_path = 'f5_openstack_agent/lbaasv2/drivers/bigip/test/json'

    @staticmethod
    def assertEqual(obj1, obj2, note=''):
        assert obj1 == obj2, note

    @staticmethod
    def assertRaises(exc):
        return pytest.raises(exc)

    @staticmethod
    def assertIn(obj1, dict_obj, note=''):
        assert obj1 in dict_obj, note

    def test_invalid_dir_name(self):
        # invliad directory name
        esd = EsdTagProcessor()
        reader = esd.read_json('/as87awoiujasdf/')
        assert not reader

    def test_no_files(self, get_relative_path):
        # verify no files in empty directory
        esd = EsdTagProcessor()
        reader = esd.read_json(
            '{}/{}/empty_dir'.format(get_relative_path, self.remaining_path))
        assert not reader

    def test_no_json_files(self, get_relative_path):
        # verify no files are read in dir that contains non-JSON files
        esd = EsdTagProcessor()
        reader = esd.read_json(
            '{}/{}/no_json'.format(get_relative_path, self.remaining_path))
        assert not reader

    def test_mix_json_files(self, get_relative_path):
        # verify single JSON file
        esd = EsdTagProcessor()
        reader = esd.read_json(
            '{}/{}/mix_json/'.format(get_relative_path, self.remaining_path))
        self.assertEqual(3, len(reader.keys()))

    def test_json_only_files(self, get_relative_path):
        # expect three files
        esd = EsdTagProcessor()
        reader = esd.read_json(
            '{}/{}/valid'.format(get_relative_path, self.remaining_path))
        self.assertEqual(3, len(reader.keys()))

    def test_invalid_json(self, get_relative_path):
        esd = EsdTagProcessor()
        with self.assertRaises(f5_ex.esdJSONFileInvalidException):
            esd.read_json(
                '{}/{}/invalid'.format(get_relative_path, self.remaining_path))

    def test_valid_json(self, get_relative_path):
        esd = EsdTagProcessor()
        result = esd.read_json(
            '{}/{}/valid/'.format(get_relative_path, self.remaining_path))

        # verify keys in the final dictionary
        self.assertIn('app_type_1', result)
        self.assertIn('app_type_2', result)
        self.assertIn('app_type_3', result)

    def test_empty_json(self, get_relative_path):
        # verify empty file is read
        esd = EsdTagProcessor()
        result = esd.read_json(
            '{}/{}/empty_file/'.format(get_relative_path, self.remaining_path))

        # verify empty dict is returned
        assert not result
