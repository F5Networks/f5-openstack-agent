# coding=utf-8
# Copyright (c) 2021, F5 Networks, Inc.
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

from requests import HTTPError

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class LTMPolicy(object):

    def __init__(self, **kwargs):
        self.policy_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.l7policy)
        self.rule_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule)
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)

        self.bigip = kwargs.get("bigip", None)
        self.vs_partition = kwargs.get("vs_partition", "")
        self.vs_name = kwargs.get("vs_name", "")
        self.partition = kwargs.get("partition", "")
        self.name = kwargs.get("name", "")
        self.payload = kwargs.get("payload", {})
        if not self.partition and self.vs_partition:
            self.partition = self.vs_partition
        elif not self.vs_partition and self.partition:
            self.vs_partition = self.partition

    def default_name(self, **kwargs):
        return self.name

    def default_payload(self, **kwargs):
        return self.payload

    def create(self, **kwargs):
        bigip = kwargs.get("bigip", self.bigip)
        payload = kwargs.get("payload", self.payload)
        if not payload:
            payload = self.default_payload(**kwargs)
        try:
            self.policy_helper.create(bigip, payload, ignore=[])
        except HTTPError as ex:
            if ex.response.status_code == 409:
                # Policy already exist. Overwrite it.
                self.policy_helper.update(bigip, payload)
            else:
                raise ex

    def update(self, **kwargs):
        bigip = kwargs.get("bigip", self.bigip)
        payload = kwargs.get("payload", self.payload)
        if not payload:
            payload = self.default_payload(**kwargs)
        try:
            self.policy_helper.update(bigip, payload)
        except HTTPError as ex:
            if ex.response.status_code == 404:
                # Policy does not exist. Create it.
                self.policy_helper.create(bigip, payload)
            else:
                raise ex

    def delete(self, **kwargs):
        bigip = kwargs.get("bigip", self.bigip)
        name = kwargs.get("name", self.name)
        if not name:
            name = self.default_name(**kwargs)
        partition = kwargs.get("partition", self.partition)
        try:
            self.policy_helper.delete(bigip, name=name, partition=partition)
        except HTTPError as ex:
            if ex.response.status_code == 404:
                # Policy does not exist. Needn't do anything.
                return
            else:
                raise ex

    def attach_to_vs(self, **kwargs):
        bigip = kwargs.get("bigip", self.bigip)
        name = kwargs.get("name", self.name)
        if not name:
            name = self.default_name(**kwargs)
        partition = kwargs.get("partition", self.partition)
        vs_name = kwargs.get("vs_name", self.vs_name)
        vs_partition = kwargs.get("vs_partition", self.vs_partition)
        if not vs_partition:
            vs_partition = partition

        try:
            vs = self.vs_helper.load(bigip, name=vs_name,
                                     partition=vs_partition)
        except HTTPError as ex:
            if ex.response.status_code == 404:
                # VS does not exist. Log an error.
                LOG.error("VS %s does not exsits under partition %s",
                          vs_name, vs_partition)
                return
            else:
                raise ex

        try:
            vs.policies_s.policies.create(
                name="/" + partition + "/" + name,
                partition=partition
            )
        except HTTPError as ex:
            if ex.response.status_code == 409:
                # LTM Policy is already attached.
                return
            else:
                raise ex

    def detach_from_vs(self, **kwargs):
        bigip = kwargs.get("bigip", self.bigip)
        name = kwargs.get("name", self.name)
        if not name:
            name = self.default_name(**kwargs)
        partition = kwargs.get("partition", self.partition)
        vs_name = kwargs.get("vs_name", self.vs_name)
        vs_partition = kwargs.get("vs_partition", self.vs_partition)
        if not vs_partition:
            vs_partition = partition

        try:
            vs = self.vs_helper.load(bigip, name=vs_name,
                                     partition=vs_partition)
        except HTTPError as ex:
            if ex.response.status_code == 404:
                # VS does not exist. Needn't to do anything.
                return
            else:
                raise ex

        try:
            policy = vs.policies_s.policies.load(name=name,
                                                 partition=partition)
        except HTTPError as ex:
            if ex.response.status_code == 404:
                # LTM policy is not attached.
                return
            else:
                raise ex

        policy.delete()


class LTMPolicyRedirect(LTMPolicy):

    def __init__(self, **kwargs):
        super(LTMPolicyRedirect, self).__init__(**kwargs)
        self.location = kwargs.get("location", "")

    def default_name(self, **kwargs):
        vs_name = kwargs.get("vs_name", self.vs_name)
        return "redirect-policy-" + vs_name

    def default_payload(self, **kwargs):
        name = kwargs.get("name", self.default_name(**kwargs))
        partition = kwargs.get("partition", self.partition)
        location = kwargs.get("location", self.location)
        payload = {
            "name": name,
            "rules": [{
                "conditions": [],
                "name": "redirect",
                "actions": [{
                    "name": "0",
                    "httpReply": True,
                    "location": location,
                    "redirect": True,
                    "request": True
                }]
            }],
            "partition": partition,
            "controls": ["forwarding"],
            "strategy": "first-match",
            "legacy": True,
            "requires": ["http"]
        }
        return payload
