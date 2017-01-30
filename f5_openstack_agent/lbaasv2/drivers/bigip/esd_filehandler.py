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
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

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

    def readjson(self):
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


class EsdTagProcessor(EsdJSONValidation):
    """Class processes json dictionary

    It checks compares the tags from esdjson dictionary to list of valid tags
    """
    def __init__(self, bigip):
        super(EsdTagProcessor).__init__(bigip)
        self.validtags = []

    # this function will return intersection of known valid esd tags
    # and the ones that user provided
    def valid_tag_key_subset(self):
        self.validtags = list(set(self.esdJSONDict.keys()) &
                              set(valid_esd_tags.keys()))
        if not self.validtags:
            LOG.error("Intersect of valid esd tags and user esd tags is empty")

        if set(self.validtag) != set(self.esdJSONDict.keys()):
            LOG.error("invalid tags in the user esd tags")

    def resource_exists(self, bigip, tag_name, resource_type):
        helper = BigIPResourceHelper(resource_type)
        return helper.exists_in_collection(bigip, tag_name)

    def get_resource_type(self, bigip, resource_type, value):
        if resource_type == ResourceType.persistence:
            return self.get_persistence_type(bigip, value)
        else:
            return resource_type

    def get_persistence_type(self, bigip, value):
        resource_types = [
            ResourceType.cookie_persistence,
            ResourceType.dest_addr_persistence,
            ResourceType.source_addr_persistence,
            ResourceType.hash_persistence,
            ResourceType.msrdp_persistence,
            ResourceType.sip_persistence,
            ResourceType.ssl_persistence,
            ResourceType.universal_persistence]

        for resource_type in resource_types:
            if self.resource_exists(bigip, value, resource_type):
                return resource_type
        return None

    def is_valid_tag(self, tag):
        return (valid_esd_tags.get(tag, None) is not None)

    def is_valid_value_type(self, value, value_type):
        return isinstance(value, value_type)

    def is_valid_value(self, bigip, value, resource_type):
        return self.resource_exists(bigip, value, resource_type)

    def is_valid_value_list(self, bigip, value, resource_type):
        for v in value:
            if not self.resource_exists(bigip, v, resource_type):
                return False
        return True

# this dictionary contains all the tags
# that are listed in the esd confluence page:
# https://docs.f5net.com/display/F5OPENSTACKPROJ/Enhanced+Service+Definition
# we are implementing the tags that can be applied only to listeners

valid_esd_tags = {
    'lbaas_ctcp': {
        'resource_type': ResourceType.tcp_profile,
        'value_type': str},

    'lbaas_stcp': {
        'resource_type': ResourceType.tcp_profile,
        'value_type': str},

    'lbaas_cssl_profile': {
        'resource_type': ResourceType.client_ssl_profile,
        'value_type': str},

    'lbaas_cssl_parent': {
        'resource_type': ResourceType.client_ssl_profile,
        'value_type': str},

    'lbaas_cssl_chain_cert': {
        'resource_type': ResourceType.tcp_profile,
        'value_type': str},

    'lbaas_sssl_profile': {
        'resource_type': ResourceType.server_ssl_profile,
        'value_type': str},

    'lbaas_irule': {
        'resource_type': ResourceType.rule,
        'value_type': list},

    'lbaas_policy ': {
        'resource_type': ResourceType.l7policy,
        'value_type': list},

    'lbaas_persist': {
        'resource_type': ResourceType.persistence,
        'value_type': str},

    'lbaas_fallback_persist': {
        'resource_type': ResourceType.persistence,
        'value_type': str}
}
