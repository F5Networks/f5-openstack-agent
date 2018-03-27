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
from requests import HTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_adapter import \
    L7PolicyServiceAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType


LOG = logging.getLogger(__name__)


class L7PolicyService(object):
    """Handles requests to create, update, delete L7 policies on BIG-IPs."""

    def __init__(self, conf):
        self.conf = conf
        self.policy_helper = BigIPResourceHelper(ResourceType.l7policy)

    def create_l7policy(self, f5_l7policy, bigips):
        LOG.debug("L7PolicyService: create_l7policy")

        error = None
        for bigip in bigips:
            try:
                self.policy_helper.create(bigip, f5_l7policy)
                error = None
            except HTTPError as err:
                status_code = err.response.status_code
                if status_code == 409:
                    LOG.debug("L7 policy already exists...updating")
                    try:
                        self.policy_helper.update(bigip, f5_l7policy)
                    except Exception as err:
                        error = f5_ex.L7PolicyUpdateException(err.message)
                else:
                    error = f5_ex.L7PolicyCreationException(err.message)
            except Exception as err:
                error = f5_ex.L7PolicyCreationException(err.message)

            if error:
                LOG.error("L7 policy creation error: %s" %
                          error.message)

        return error

    def delete_l7policy(self, f5_l7policy, bigips):
        LOG.debug("L7PolicyService:delete_l7policy")

        error = False
        for bigip in bigips:
            try:
                self.policy_helper.delete(
                    bigip, f5_l7policy['name'], f5_l7policy['partition'])
            except HTTPError as err:
                status_code = err.response.status_code
                if status_code == 404:
                    LOG.warn("Deleting L7 policy failed...not found: %s",
                             err.message)
                elif status_code == 400:
                    LOG.debug("Deleting L7 policy failed...unknown "
                              "client error: %s", err.message)
                    error = f5_ex.L7PolicyDeleteException(err.message)
                else:
                    error = f5_ex.L7PolicyDeleteException(err.message)
            except Exception as err:
                LOG.exception(err)
                error = f5_ex.L7PolicyDeleteException(err.message)

            if error:
                LOG.error("L7 Policy deletion error: %s",
                          error.message)

        return error

    def build_policy(self, l7policy, lbaas_service):
        # build data structure for service adapter input
        LOG.debug("L7PolicyService: service")
        import pprint
        # LOG.debug(pprint.pformat(lbaas_service.service_object, indent=4))
        LOG.debug("L7PolicyService: l7policy")
        # LOG.debug(pprint.pformat(l7policy, indent=4))

        l7policy_adapter = L7PolicyServiceAdapter(self.conf)

        os_policies = {'l7rules': [], 'l7policies': [], 'f5_policy': {}}

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

        if os_policies['l7policies']:
            os_policies['f5_policy'] = l7policy_adapter.translate(os_policies)

        LOG.debug(pprint.pformat(os_policies, indent=2))
        return os_policies
