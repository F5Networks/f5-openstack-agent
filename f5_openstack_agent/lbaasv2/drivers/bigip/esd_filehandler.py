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

import glob
import json
import os
import types

from oslo_log import log as logging


from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

LOG = logging.getLogger(__name__)


class EsdJSONValidation(object):
    """Class reads the json file(s)

    It checks and parses the content of json file(s) to a dictionary
    """
    def __init__(self, esddir):
        self.esdJSONFileList = glob.glob(os.path.join(esddir, '*.json'))
        self.esdJSONDict = {}

    def read_json(self):
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
    def __init__(self, esddir):
        super(EsdTagProcessor, self).__init__(esddir)

    # this function will return intersection of known valid esd tags
    # and the ones that user provided
    def valid_tag_key_subset(self):
        self.validtags = list(set(self.esdJSONDict.keys()) &
                              set(self.valid_esd_tags.keys()))
        if not self.validtags:
            LOG.error("Intersect of valid esd tags and user esd tags is empty")

        if set(self.validtags) != set(self.esdJSONDict.keys()):
            LOG.error("invalid tags in the user esd tags")

    def process_esd(self, bigips):
        try:
            dict = self.read_json()
            self.esd_dict = self.verify_esd_dict(bigips, dict)
        except f5_ex.esdJSONFileInvalidException:
            self.esd_dict = {}
            raise

    def get_esd(self, name):
        return self.esd_dict.get(name, None)

    def is_esd(self, name):
        return self.get_esd(name) is not None

    def resource_exists(self, bigip, tag_name, resource_type):
        helper = BigIPResourceHelper(resource_type)
        name = tag_name

        # allow user to define chain cert name with or without '.crt'
        if resource_type == ResourceType.ssl_cert_file and not \
                name.endswith('.crt'):
            name += '.crt'
        return helper.exists_in_collection(bigip, name)

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
        return self.valid_esd_tags.get(tag, None) is not None

    def is_valid_value(self, bigip, value, resource_type):
        return self.resource_exists(bigip, value, resource_type)

    def is_valid_value_list(self, bigip, value, resource_type):
        for v in value:
            if not self.resource_exists(bigip, v, resource_type):
                return False
        return True

    def verify_esd_dict(self, bigips, esd_dict):
        valid_esd_dict = {}
        for esd in esd_dict:
            # check that ESD is valid for every BIG-IP
            valid_esd = True
            for bigip in bigips:
                valid_esd = self.verify_esd(bigip, esd, esd_dict[esd])
                if not valid_esd:
                    break

            if valid_esd:
                # add non-empty valid ESD to return dict
                valid_esd_dict[esd] = valid_esd

        return valid_esd_dict

    def verify_esd(self, bigip, name, esd):
        valid_esd = {}
        for tag in esd:
            try:
                self.verify_tag(tag)
                self.verify_value(bigip, tag, esd[tag])

                # add tag to valid ESD
                valid_esd[tag] = esd[tag]
                LOG.debug("Tag {0} is valid for ESD {1}.".format(tag, name))
            except f5_ex.esdJSONFileInvalidException as err:
                LOG.error('Tag {0} failed validation for ESD {1} and was not '
                          'added to ESD. Error: {2}'.
                          format(tag, name, err.message))

        return valid_esd

    def verify_value(self, bigip, tag, value):
        tag_def = self.valid_esd_tags.get(tag)

        # verify resource type
        resource_type = self.get_resource_type(
            bigip, tag_def['resource_type'], value)
        if not resource_type:
            msg = 'Unable to determine resource type for tag {0} and ' \
                  'value {1}'.format(tag, value)
            raise f5_ex.esdJSONFileInvalidException(msg)

        # verify value type
        value_type = tag_def['value_type']
        if not isinstance(value, value_type):
            msg = 'Invalid value {0} for tag {1}. ' \
                  'Type must be {2}.'.format(value, tag, value_type)
            raise f5_ex.esdJSONFileInvalidException(msg)

        # verify value exists on BIG-IP
        if isinstance(value, list):
            is_valid = self.is_valid_value_list(bigip, value, resource_type)
        else:
            is_valid = self.is_valid_value(bigip, value, resource_type)

        if not is_valid:
            msg = ("Invalid value {0} for tag {1}".format(value, tag))
            raise f5_ex.esdJSONFileInvalidException(msg)

    def verify_tag(self, tag):
        if not self.is_valid_tag(tag):
            msg = 'Tag {0} is not valid.'.format(tag)
            raise f5_ex.esdJSONFileInvalidException(msg)

    # This dictionary contains all the tags
    # that are listed in the esd confluence page.
    # We are implementing the tags that can be applied only to listeners.

    valid_esd_tags = {
        'lbaas_ctcp': {
            'resource_type': ResourceType.tcp_profile,
            'value_type': types.StringTypes},

        'lbaas_stcp': {
            'resource_type': ResourceType.tcp_profile,
            'value_type': types.StringTypes},

        'lbaas_cssl_profile': {
            'resource_type': ResourceType.client_ssl_profile,
            'value_type': types.StringTypes},

        'lbaas_sssl_profile': {
            'resource_type': ResourceType.server_ssl_profile,
            'value_type': types.StringTypes},

        'lbaas_irule': {
            'resource_type': ResourceType.rule,
            'value_type': types.ListType},

        'lbaas_policy': {
            'resource_type': ResourceType.l7policy,
            'value_type': types.ListType},

        'lbaas_persist': {
            'resource_type': ResourceType.persistence,
            'value_type': types.StringTypes},

        'lbaas_fallback_persist': {
            'resource_type': ResourceType.persistence,
            'value_type': types.StringTypes}
    }
