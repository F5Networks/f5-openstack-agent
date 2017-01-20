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

import glob
import json
import os

from oslo_log import log as logging


from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex


LOG = logging.getLogger(__name__)


class EsdJSONFileRead(object):
    """Class reads the directory that json file(s) exists

    It looks for the json file under /etc/neutron/services/f5/esd
    """
    def __init__(self, esddir):
        self.esdJSONFileList = glob.glob(os.path.join(esddir, '*.json'))


class EsdJSONValidation(EsdJSONFileRead):
    """Class reads the json file(s)

    It checks and parses the content of json file(s) to a dictionary
    """
    def __init__(self, esddir):
        super(EsdJSONValidation, self).__init__(esddir)
        self.esdJSONDict = {}

    def readJson(self):
        for fileList in self.esdJSONFileList:
            try:
                with open(fileList) as json_file:
                    # Reading each file to a dictionary
                    fileJSONDict = json.load(json_file)
                    # Combine all dictionaries to one
                    self.esdJSONDict.update(fileJSONDict)

            except ValueError as err:
                    LOG.error('ESD JSON File is invalid: %s', err)
                    raise f5_ex.esdJSONFileInvalidException()

        return self.esdJSONDict
