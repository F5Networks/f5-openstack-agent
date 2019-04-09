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

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions \
    import NoActionFoundForPolicy
from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions \
    import PolicyHasNoRules
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter \
    import ServiceModelAdapter


LOG = logging.getLogger(__name__)


class Action(object):
    """Describes a single action for a rule."""

    def __init__(
            self, action, action_name, partition, env_prefix, action_val=None):
        action_map = {
            'REDIRECT_TO_POOL': {'forward': True,
                                 'pool': self._get_pool_name(
                                     partition, env_prefix, action_val)},
            'REDIRECT_TO_URL': {
                'redirect': True, 'location': action_val, 'httpReply': True},
            'REJECT': {'reset': True, 'forward': True}
        }
        self.request = True
        self.name = action_name
        self.__dict__.update(action_map[action])

    def _get_pool_name(self, partition, env_prefix, action_value):
        """Construct pool name from partition and OpenStack pool name."""
        return '/{0}/{1}{2}'.format(partition, env_prefix, action_value)


class Condition(object):
    """Describes a single condition for a rule."""

    cond_comp_type_map = {
        'STARTS_WITH': 'startsWith',
        'ENDS_WITH': 'endsWith',
        'CONTAINS': 'contains',
        'EQUAL_TO': 'equals'
    }

    def __init__(self, condition, cond_name):
        key = condition['key']
        val = condition['value']
        self.request = True
        self.name = cond_name
        cond_type_map = {
            'HOST_NAME': {'httpHost': True, 'values': [val], 'host': True},
            'PATH': {'httpUri': True, 'path': True, 'values': [val]},
            'FILE_TYPE': {'httpUri': True, 'extension': True, 'values': [val]},
            'HEADER': {'httpHeader': True, 'tmName': key, 'values': [val]},
            'COOKIE': {'httpCookie': True, 'tmName': key, 'values': [val]}
        }
        if condition['invert']:
            setattr(self, 'not', condition['invert'])
        self.__dict__.update(cond_type_map[condition['type']])
        if condition['compare_type'] in self.cond_comp_type_map:
            setattr(self,
                    self.cond_comp_type_map[condition['compare_type']],
                    True)
            setattr(self, "not_regex", True)


class iRule(object):
    """Describes a single iRule for REGEX l7policy"""

    action_mapping = {
        "REDIRECT_TO_POOL": '''when HTTP_REQUEST {
            if {[HTTP::%s] matches_regex "%s"} {
                pool %s
            }
        }''',
        "REDIRECT_TO_URL": '''when HTTP_REQUEST {
            if {[HTTP::%s] matches_regex "%s"} {
                HTTP::redirect "%s"
            }
        }'''
    }

    file_action_mapping = {
        "REDIRECT_TO_POOL": '''when HTTP_REQUEST {
            if {[HTTP::%s] ends_with "%s"} {
                pool %s
            }
        }''',
        "REDIRECT_TO_URL": '''when HTTP_REQUEST {
            if {[HTTP::%s] ends_with "%s"} {
                HTTP::redirect "%s"
            }
        }'''
    }

    type_mapping = {
        "HOST_NAME": "host",
        "PATH": "path",
        "FILE_TYPE": "uri",
        "HEADER": "header %s",
        "COOKIE": "cookie %s"
    }

    def __init__(self, policy):
        self.listener = policy["listener_id"]
        self.action = policy["action"]
        self.action_pool = policy.get("redirect_pool_id")
        self.action_uri = policy.get("redirect_url")
        self.value = None
        self.type = None
        self.apiAnonymous = None
        self.key = None
        self.template = None

    def adapt_regex_to_irule(
            self, policy, service, partition, env_prefix):
        """Adapt OpenStack rules into conditions and actions."""
        irule_list = []
        for os_rule_dict in policy['rules']:
            rule_id = os_rule_dict['id']
            os_rule = self._get_l7rule(rule_id, service)
            if os_rule['provisioning_status'] != 'PENDING_DELETE' and \
               os_rule['admin_state_up']:
                if os_rule['compare_type'] == "REGEX":
                    self.value = os_rule["value"]
                    self.key = os_rule.get("key")

                    if os_rule["type"] in ("HEADER", "COOKIE"):
                        self.type = self.type_mapping[
                            os_rule["type"]] % self.key
                    else:
                        self.type = self.type_mapping[os_rule["type"]]

                    if os_rule["type"] == "FILE_TYPE":
                        self.template = self.file_action_mapping[self.action]
                    else:
                        self.template = self.action_mapping[self.action]

                    irule_object = self._l7rule_to_irule(
                        partition,
                        env_prefix,
                        rule_id)

                    irule_list.append(irule_object)
        return irule_list

    def _l7rule_to_irule(self, partition, env_prefix, rule_id):
        irule_object = {}

        if self.action == "REDIRECT_TO_POOL":
            pool_name = self._get_pool_name(
                partition, env_prefix, self.action_pool)
            self.apiAnonymous = self.template % (self.type,
                                                 self.value,
                                                 pool_name)
        if self.action == "REDIRECT_TO_URL":
            self.apiAnonymous = self.template % (self.type,
                                                 self.value,
                                                 self.action_uri)
        irule_object["listener"] = self.listener
        irule_object["apiAnonymous"] = self.apiAnonymous
        # irule_object["action_pool"] = self.action_pool
        # irule_object["action_uri"] = self.action_uri
        irule_object["partition"] = partition
        irule_object["name"] = "irule_" + rule_id
        irule_object["fullPath"] = self._get_fullPath(partition, rule_id)
        return irule_object

    def _get_l7rule(self, rule_id, service):
        """Get rule dict from service list."""
        for rule in service['l7rules']:
            if rule['id'] == rule_id:
                return rule

    def _get_pool_name(self, partition, env_prefix, action_value):
        """Construct pool name from partition and OpenStack pool name."""
        return '/{0}/{1}{2}'.format(partition, env_prefix, action_value)

    def _get_fullPath(self, partition, name):
        return '/{0}/{1}'.format(partition, name)


class Rule(object):
    """Describes a single rule for a policy."""

    def __init__(self, policy, service, partition, env_prefix):
        self._set_name(policy)
        self.ordinal = policy['position']
        self.actions = []
        self.conditions = []
        self._adapt_rule_to_conditions_and_actions(
            policy, service, partition, env_prefix)

    def _adapt_rule_to_conditions_and_actions(
            self, policy, service, partition, env_prefix):
        """Adapt OpenStack rules into conditions and actions."""
        for idx, os_rule_dict in enumerate(policy['rules']):
            os_rule = self._get_l7rule(os_rule_dict['id'], service)
            if os_rule['provisioning_status'] != 'PENDING_DELETE' and \
               os_rule['admin_state_up']:
                cond = Condition(os_rule, str(idx))
                if cond.__dict__.get("not_regex", False):
                    self.conditions.append(cond.__dict__)
        act_type, act_val = self._get_action_and_value(policy['id'], service)
        action = Action(act_type, '0', partition, env_prefix, act_val)
        self.actions.append(action.__dict__)

    def _get_l7rule(self, rule_id, service):
        """Get rule dict from service list."""
        for rule in service['l7rules']:
            if rule['id'] == rule_id:
                return rule

    def _set_name(self, policy):
        """Set name of rule to something intelligent."""
        name = ''
        if not policy['name']:
            name = policy['action'].lower()
            name += '_' + str(policy['position'])
        else:
            name = policy['name']
        self.name = name

    def _get_action_and_value(self, policy_id, service):
        """Get the action and action value associated with a policy."""
        for pol in service['l7policies']:
            if pol['id'] == policy_id:
                action = pol['action']
                action_val = None
                if action == 'REDIRECT_TO_POOL':
                    action_val = pol['redirect_pool_id']
                if action == 'REDIRECT_TO_URL':
                    action_val = pol['redirect_url']
                return action, action_val
        msg = "Could not find action for the following policy id: {}".format(
            policy_id)
        raise NoActionFoundForPolicy(msg)


class L7PolicyServiceAdapter(ServiceModelAdapter):
    """Map OpenStack policies and rules to policy and rules on device."""
    def _adapt_policies_to_rules(self):
        """OS Policies are translated into Rules on the device."""
        self.iRules = []
        for policy in self.service['l7policies']:
            if policy['provisioning_status'] != 'PENDING_DELETE' and \
               policy['admin_state_up']:
                bigip_rule = Rule(
                    policy, self.service, self.folder, self.prefix)
                self.policy_dict['rules'].append(bigip_rule.__dict__)
                irule = iRule(policy)
                self.iRules += irule.adapt_regex_to_irule(
                    policy, self.service, self.folder, self.prefix)
        if not self.policy_dict['rules']:
            msg = 'All policies were in a PENDING_DELETE or admin_state ' \
                'DOWN.  Deleting wrapper_policy.'
            raise PolicyHasNoRules(msg)
        self._check_if_adapted_rules_empty()

    def _check_if_adapted_rules_empty(self):
        """Delete wrapper policy if all rules in PENDING_DELETE state."""
        delete_wrapper_policy = True
        for os_rule in self.policy_dict['rules']:
            if os_rule['conditions']:
                delete_wrapper_policy = False
                break
        if delete_wrapper_policy:
            msg = 'All rules were in a PENDING_DELETE state. Deleting ' \
                'wrapper_policy.'
            raise PolicyHasNoRules(msg)

    def _adapt_policy(self):
        """Setup the wrapper policy, which will contain rules."""
        self.policy_dict = {}
        self.policy_dict['name'] = 'wrapper_policy_' + self.listener
        self.policy_dict['partition'] = self.folder

        self.policy_dict['strategy'] = 'first-match'
        self.policy_dict['rules'] = list()
        self.policy_dict['legacy'] = True
        self.policy_dict['requires'] = ['http']
        self.policy_dict['controls'] = ['forwarding']

        if not self.service['l7rules']:
            msg = 'No Rules given to implement. A Policy cannot be attached ' \
                'to a Virtual until it has one or more Rules.'
            raise PolicyHasNoRules(msg)
        self._adapt_policies_to_rules()

    def translate(self, service):

        self.service = service
        self.folder = self.get_folder_name(
            self.service['l7policies'][0]['tenant_id'])
        self.listener = \
            self.service['l7policies'][0]['listener_id']
        try:
            self._adapt_policy()
        except (PolicyHasNoRules, NoActionFoundForPolicy) as error:
            LOG.debug(error.message)
            self.policy_dict['rules'] = list()

        return self.policy_dict

    def translate_name(self, l7policy):
        return {'name': 'wrapper_policy',
                'partition': self.get_folder_name(l7policy['tenant_id'])}
