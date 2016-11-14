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

from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions \
    import NoActionFoundForPolicy
from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions \
    import PolicyHasNoRules
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter \
    import ServiceModelAdapter


class Action(object):
    '''Describes a single action for a rule.'''

    def __init__(self, action, action_name, partition, action_val=None):
        action_map = {
            'REDIRECT_TO_POOL': {'forward': True,
                                 'pool': self._get_pool_name(
                                     partition, action_val)},
            'REDIRECT_TO_URL': {
                'redirect': True, 'location': action_val, 'httpReply': True},
            'REJECT': {'reset': True, 'forward': True}
        }
        self.request = True
        self.name = action_name
        self.__dict__.update(action_map[action])

    def _get_pool_name(self, partition, action_value):
        '''Construct pool name from partition and OpenStack pool name.'''

        return '/{0}/{1}'.format(partition, action_value)


class Condition(object):
    '''Describes a single condition for a rule.'''

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
        setattr(self, self.cond_comp_type_map[condition['compare_type']], True)


class Rule(object):
    '''Describes a single rule for a policy.'''

    def __init__(self, policy, service, partition):
        self._set_name(policy)
        self.ordinal = policy['position']
        self.actions = []
        self.conditions = []
        self._adapt_rule_to_conditions_and_actions(policy, service, partition)

    def _adapt_rule_to_conditions_and_actions(
            self, policy, service, partition):
        '''Adapt OpenStack rules into conditions and actions.'''

        for idx, os_rule_dict in enumerate(policy['rules']):
            os_rule = self._get_l7rule(os_rule_dict['id'], service)
            cond = Condition(os_rule, str(idx))
            self.conditions.append(cond.__dict__)
        act_type, act_val = self._get_action_and_value(policy['id'], service)
        action = Action(act_type, '0', partition, act_val)
        self.actions.append(action.__dict__)

    def _get_l7rule(self, rule_id, service):
        '''Get rule dict from service list.'''

        for rule in service['l7rules']:
            if rule['id'] == rule_id:
                return rule

    def _set_name(self, policy):
        '''Set name of rule to something intelligent.'''

        name = ''
        if not policy['name']:
            name = policy['action'].lower()
            name += '_' + str(policy['position'])
        else:
            name = policy['name']
        self.name = name

    def _get_action_and_value(self, policy_id, service):
        '''Get the action and action value associated with a policy.'''

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
    '''Map OpenStack policies and rules to policy and rules on device.'''

    def _adapt_policies_to_rules(self):
        '''OS Policies are translated into Rules on the device.'''

        for policy in self.service['l7policies']:
            bigip_rule = Rule(policy, self.service, self.folder)
            self.policy_dict['rules'].append(bigip_rule.__dict__)

    def _adapt_policy(self):
        '''Setup the wrapper policy, which will contain rules.'''

        if not self.service['l7rules']:
            msg = 'No Rules given to implement. A Policy cannot be attached ' \
                'to a Virtual until it has one or more Rules.'
            raise PolicyHasNoRules(msg)
        self.policy_dict = {}
        self.policy_dict['name'] = 'wrapper_policy'
        self.policy_dict['partition'] = self.folder
        self.policy_dict['strategy'] = 'first-match'
        self.policy_dict['rules'] = []
        self.policy_dict['legacy'] = True
        self.policy_dict['requires'] = ['http']
        self.policy_dict['controls'] = ['forwarding']
        self._adapt_policies_to_rules()

    def translate(self, service):
        self.service = service
        self.folder = self.get_folder_name(
            self.service['l7policies'][0]['tenant_id'])
        self._adapt_policy()
        return self.policy_dict
