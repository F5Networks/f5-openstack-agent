# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class ACLHelper(object):
    """A class for all ACL relative process"""

    def __init__(self):

        self.irule_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule
        )
        self.irule_instructor = BigipInstructor(self.irule_helper)

    def enable_acl(self, acl_bind):
        enable = acl_bind.get("enabled")
        return enable

    def _acl_group_name(self, acl_bind):
        prefix = "acl_"
        uuid = acl_bind.get("acl_group_id")
        name = prefix + uuid
        return name

    def _get_acl_template(self, acl_bind):

        white_template = """when CLIENT_ACCEPTED {{
        if {{ !([class match [IP::client_addr] eq {}]) }} {{
        log local0. "Dropped connection: """ + \
            """client IP [IP::client_addr] is restricted."
            drop}}
        }}"""

        black_template = """when CLIENT_ACCEPTED {{
        if {{ [class match [IP::client_addr] eq {}] }} {{
        log local0. "Dropped connection: """ + \
            """client IP [IP::client_addr] is restricted."
            drop}}
        }}"""

        bind_type = acl_bind.get("type")
        if bind_type == "whitelist":
            return white_template
        else:
            return black_template

    def get_acl_irule_context(self, acl_bind):

        irule_template = self._get_acl_template(acl_bind)
        data_group_name = self._acl_group_name(acl_bind)

        irule = irule_template.format(data_group_name)
        return irule

    def get_acl_irule_payload(self, acl_bind, vs_info):
        irule_payload = {}
        irule_ctxt = self.get_acl_irule_context(acl_bind)
        irule_partition = vs_info["partition"]
        irule_name = "acl_irule_" + acl_bind["listener_id"]
        irule_fullPath = "/{0}/{1}".format(irule_partition, irule_name)

        irule_payload["apiAnonymous"] = irule_ctxt
        irule_payload["partition"] = irule_partition
        irule_payload["name"] = irule_name
        irule_payload["fullPath"] = irule_fullPath

        return irule_payload

    def create_acl_irule(self, bigip, irule_payload):
        self.irule_instructor.create(bigip, irule_payload)

    def remove_acl_irule(self, bigip, irule_payload):
        self.irule_instructor.delete(bigip, irule_payload)


class BigipInstructor(object):
    """An iControl SDK call instructor"""

    def __init__(self, resource_helper):
        self.resource_helper = resource_helper
        self.resource_type = resource_helper.__class__

    def create(self, bigip, payload, **kwargs):
        overwrite = kwargs.get("overwrite", True)
        if self.resource_helper.exists(bigip, name=payload['name'],
                                       partition=payload['partition']):
            if overwrite:
                LOG.debug("%s %s already exists ... updating",
                          self.resource_type, payload['name'])
                self.resource_helper.update(bigip, payload)
            else:
                LOG.debug("%s %s already exists, do not update.",
                          self.resource_type, payload['name'])
        else:
            LOG.debug("%s %s does not exist ... creating",
                      self.resource_type, payload['name'])
            self.resource_helper.create(bigip, payload)

    def update(self, bigip, payload):
        if self.resource_helper.exists(bigip, name=payload['name'],
                                       partition=payload['partition']):
            LOG.debug("%s already exists ... updating", self._resource)
            self.resource_helper.update(bigip, payload)
        else:
            LOG.debug("%s does not exist ... creating", self._resource)
            self.resource_helper.create(bigip, payload)

    def delete(self, bigip, payload):
        self.resource_helper.delete(bigip, name=payload['name'],
                                    partition=payload['partition'])
