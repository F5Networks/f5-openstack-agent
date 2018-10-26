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
    EsdJSONValidation
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
        reader = EsdJSONValidation('/as87awoiujasdf/')
        assert not reader.esdJSONFileList

    def test_no_files(self, get_relative_path):
        # verify no files in empty directory
        reader = EsdJSONValidation(
            '{}/{}/empty_dir'.format(get_relative_path, self.remaining_path))
        assert not reader.esdJSONFileList

    def test_no_json_files(self, get_relative_path):
        # verify no files are read in dir that contains non-JSON files
        reader = EsdJSONValidation(
            '{}/{}/no_json'.format(get_relative_path, self.remaining_path))
        assert not reader.esdJSONFileList

    def test_mix_json_files(self, get_relative_path):
        # verify single JSON file
        reader = EsdJSONValidation(
            '{}/{}/mix_json/'.format(get_relative_path, self.remaining_path))
        self.assertEqual(1, len(reader.esdJSONFileList))

    def test_json_only_files(self, get_relative_path):
        # expect three files
        reader = EsdJSONValidation(
            '{}/{}/valid'.format(get_relative_path, self.remaining_path))
        self.assertEqual(3, len(reader.esdJSONFileList))

    def test_invalid_json(self, get_relative_path):
        handler = EsdJSONValidation(
            '{}/{}/invalid'.format(get_relative_path, self.remaining_path))

        # verify exception raised
        with self.assertRaises(f5_ex.esdJSONFileInvalidException):
            handler.read_json()

    def test_valid_json(self, get_relative_path):
        handler = EsdJSONValidation(
            '{}/{}/valid/'.format(get_relative_path, self.remaining_path))
        dict = handler.read_json()

        # verify keys in the final dictionary
        self.assertIn('app_type_1', dict)
        self.assertIn('app_type_2', dict)
        self.assertIn('app_type_3', dict)

    def test_empty_json(self, get_relative_path):
        # verify empty file is read
        handler = EsdJSONValidation(
            '{}/{}/empty_file/'.format(get_relative_path, self.remaining_path))
        self.assertEqual(1, len(handler.esdJSONFileList))

        # verify empty dict is returned
        dict = handler.read_json()
        assert not dict
