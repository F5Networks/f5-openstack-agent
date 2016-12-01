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

from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions import \
    PolicyHasNoRules
from f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_adapter import \
    L7PolicyServiceAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_builder import \
    L7PolicyBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_service import \
    LbaasServiceObject
from f5_openstack_agent.lbaasv2.drivers.bigip.listener_adapter import \
    ListenerAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.vs_builder import \
    VirtualServerBuilder

LOG = logging.getLogger(__name__)


class L7PolicyService(object):
    """Handles requests to create, update, delete L7 policies on BIG-IPs."""
    def __init__(self, conf):
        self.conf = conf

    def create_l7policy(self, l7policy, service_object, bigips):
        LOG.debug("L7PolicyService: create_l7policy")

        stack = []
        event = 'CREATE_L7POLICY'
        lbaas_service = LbaasServiceObject(service_object)

        if l7policy['listener_id']:
            # add L7 policy to virtual server
            listener = lbaas_service.get_listener(l7policy['listener_id'])
            listener_adapter = ListenerAdapter(self.conf)
            f5_vs = listener_adapter.translate(
                lbaas_service, listener, l7policy=l7policy)
            stack.append(VirtualServerBuilder(event, f5_vs))

        # create L7 policy
        try:
            l7policy_adapter = L7PolicyServiceAdapter(self.conf)
            policies = self.build_policy(l7policy, lbaas_service)
            if policies['l7policies']:
                f5_l7policy = l7policy_adapter.translate(policies)
                stack.append(L7PolicyBuilder(event, f5_l7policy))
            else:
                # empty policy -- delete wrapper policy on BIG-IPs
                self.delete_l7policy(l7policy, service_object, bigips)
                return

        except PolicyHasNoRules as exc:
            # For OpenStack, creating policies and rules are independent
            # commands, so this exception is valid. Delete policy because
            # it has no rules.
            LOG.debug(exc.message)
            self.delete_l7policy(l7policy, service_object, bigips)
            return
        except Exception:
            import traceback
            LOG.error(traceback.format_exc())
            raise

        self._process_stack(stack, bigips)

    def delete_l7policy(self, l7policy, service_object, bigips):
        LOG.debug("L7PolicyService:delete_l7policy")
        stack = []
        event = 'DELETE_L7POLICY'
        lbaas_service = LbaasServiceObject(service_object)

        # only need name/partition for delete
        l7policy_adapter = L7PolicyServiceAdapter(self.conf)
        f5_l7policy = l7policy_adapter.translate_name(l7policy)

        stack.append(L7PolicyBuilder(event, f5_l7policy))

        if l7policy['listener_id']:
            # remove L7 policy from virtual server
            listener = lbaas_service.get_listener(l7policy['listener_id'])
            listener_adapter = ListenerAdapter(self.conf)
            f5_vs = listener_adapter.translate(
                lbaas_service, listener, l7policy=l7policy)
            stack.append(VirtualServerBuilder(event, f5_vs))

        self._process_stack(stack, bigips)

    def update_l7policy(self, l7policy, service_object, bigips):
        LOG.debug("L7PolicyService:update_l7policy")

        stack = []
        event = 'UPDATE_L7POLICY'
        lbaas_service = LbaasServiceObject(service_object)

        try:
            l7policy_adapter = L7PolicyServiceAdapter(self.conf)
            policies = self.build_policy(l7policy, lbaas_service)
            if policies['l7policies']:
                f5_l7policy = l7policy_adapter.translate(policies)
                stack.append(L7PolicyBuilder(event, f5_l7policy))
            else:
                # empty policy -- delete wrapper policy on BIG-IPs
                self.delete_l7policy(l7policy, service_object, bigips)
                return
        except PolicyHasNoRules:
            # Because this is an update, assume an existing policy
            # and if the update results in a policy without rules,
            # delete the policy.
            LOG.debug("No rules for policy, deleting policy.")
            self.delete_l7policy(l7policy, service_object, bigips)
            return

        self._process_stack(stack, bigips)

    def create_l7rule(self, l7rule, service_object, bigips):
        LOG.debug("L7PolicyService:create_l7rule")

        # get l7policy for rule
        lbaas_service = LbaasServiceObject(service_object)
        l7policy = lbaas_service.get_l7policy(l7rule.get('policy_id', ''))
        if l7policy:
            # re-create policy with new rule
            self.create_l7policy(l7policy, service_object, bigips)

    def delete_l7rule(self, l7rule, service_object, bigips):
        LOG.debug("L7PolicyService:delete_l7rule")

        # get l7policy for rule
        lbaas_service = LbaasServiceObject(service_object)
        l7policy = lbaas_service.get_l7policy(l7rule.get('policy_id', ''))
        if l7policy:
            # update policy without rule
            self.update_l7policy(l7policy, service_object, bigips)

    def update_l7rule(self, l7rule, service_object, bigips):
        LOG.debug("L7PolicyService:update_l7rule")

        # get l7policy for rule
        lbaas_service = LbaasServiceObject(service_object)
        l7policy = lbaas_service.get_l7policy(l7rule.get('policy_id', ''))
        if l7policy:
            # re-create policy with updated rule
            self.update_l7policy(l7policy, service_object, bigips)

    @staticmethod
    def build_policy(l7policy, lbaas_service):
        # build data structure for service adapter input
        LOG.debug("L7PolicyService: service")
        import pprint
        LOG.debug(pprint.pformat(lbaas_service.service_object, indent=4))
        LOG.debug("L7PolicyService: l7policy")
        LOG.debug(pprint.pformat(l7policy, indent=4))

        os_policies = {'l7rules': [],
                       'l7policies': []}

        # get all policies and rules for listener referenced by this policy
        listener = lbaas_service.get_listener(l7policy['listener_id'])
        for policy_id in listener['l7_policies']:
            policy = lbaas_service.get_l7policy(policy_id['id'])
            if policy:
                os_policies['l7policies'].append(policy)
                for rule in policy['rules']:
                    l7rule = lbaas_service.get_l7rule(rule['id'])
                    if l7rule:
                        os_policies['l7rules'].append(l7rule)

        LOG.debug(pprint.pformat(os_policies, indent=4))
        return os_policies

    @staticmethod
    def _process_stack(stack, bigips):
        """Execute BIG-IP operations for builders in a stack

        :param stack:
        :return:
        """
        while len(stack):
            builder = stack.pop()
            for bigip in bigips:
                builder.execute(bigip)
