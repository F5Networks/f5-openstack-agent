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

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class VirtualServerBuilder(object):
    """Class supports CRUD for virtual servers

    Handles these events:
      - create l7 policy (update virtual server)
      - delete l7 policy (update virtual server)
    """
    def __init__(self, event, f5_vs):

        # get BIG-IP attributes for virtual server update
        self.f5_vs = f5_vs

        # map execute() methods based on event
        if event == 'DELETE_L7POLICY':
            # remove policy from virtual server
            self.execute = self.remove_l7policy
        else:
            # create/update: add policy to virtual server
            self.execute = self.add_l7policy

    def add_l7policy(self, bigip):
        # L7 policies require http profile. Make sure vs has http profile.
        self.add_profile('http', bigip)
        self.add_policy(bigip, self.f5_vs['l7policy_name'])

    def remove_l7policy(self, bigip):
        # Do not remove http profile -- might be needed for other reasons
        self.remove_policy(bigip, self.f5_vs['l7policy_name'])

    def add_policy(self, bigip, policy_name):
        vs_name = self.f5_vs['name']
        vs_partition = self.f5_vs['partition']
        policy_partition = vs_partition

        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name,
                     partition=vs_partition)
        p = obj.policies_s
        policies = p.get_collection()

        # see if policy already added to virtual server
        for policy in policies:
            if policy.name == policy_name:
                LOG.debug("L7Policy found. Not adding.")
                return

        try:
            # not found -- add policy to virtual server
            p.policies.create(name=policy_name,
                              partition=policy_partition)
        except Exception as exc:
            # Bug in TMOS 12.1 will return a 404 error, but the request
            # succeeded. Verify that policy was added, and ignore exception.
            LOG.debug(exc.message)
            if not p.policies.exists(name=policy_name,
                                     partition=policy_partition):
                # really failed, raise original exception
                raise

        # success
        LOG.debug("Added L7 policy {0} for virtual sever {1}".format(
            policy_name, vs_name))

    def add_profile(self, profile_name, bigip, context='all'):
        vs_name = self.f5_vs['name']
        vs_partition = self.f5_vs['partition']
        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name, partition=vs_partition)
        p = obj.profiles_s
        profiles = p.get_collection()

        # see if profile exists
        for profile in profiles:
            if profile.name == profile_name:
                return

        # not found -- add profile (assumes Common partition)
        p.profiles.create(name=profile_name,
                          partition='Common',
                          context=context)
        LOG.debug("Added profile {0} for virtual sever {1}".
                  format(profile_name, vs_name))

    def remove_policy(self, bigip, policy_name):
        vs_name = self.f5_vs['name']
        vs_partition = self.f5_vs['partition']
        policy_partition = vs_partition

        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name,
                     partition=vs_partition)
        p = obj.policies_s
        policies = p.get_collection()

        # find policy and remove from virtual server
        for policy in policies:
            if policy.name == policy_name:
                l7 = p.policies.load(name=policy_name,
                                     partition=policy_partition)
                l7.delete()
                LOG.debug("Removed L7 policy {0} for virtual sever {1}".
                          format(policy_name, vs_name))
