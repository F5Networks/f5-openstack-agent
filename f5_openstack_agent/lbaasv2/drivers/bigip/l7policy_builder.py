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

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType


LOG = logging.getLogger(__name__)


class L7PolicyBuilder(object):
    """Class supports CRUD for L7 policies and rules

    Handles both L7 policy and L7 rules for these events:
      - create l7 policy
      - delete l7 policy
    """
    def __init__(self, event, f5_l7policy):
        self.event = event
        self.f5_l7policy = f5_l7policy
        self.helper = BigIPResourceHelper(ResourceType.l7policy)

        if event == 'DELETE_L7POLICY':
            # both rules and policies handled by same method
            self.execute = self.delete
        else:
            # create and update event for both rules and polices
            self.execute = self.create

    def create(self, bigip):
        LOG.debug("L7PolicyBuilder: create")
        if self.helper.exists(bigip,
                              name=self.f5_l7policy['name'],
                              partition=self.f5_l7policy['partition']):
            self.helper.update(bigip, self.f5_l7policy)
        else:
            self.helper.create(bigip, self.f5_l7policy)

    def delete(self, bigip):
        LOG.debug("L7PolicyBuilder: delete")
        self.helper.delete(
            bigip, self.f5_l7policy['name'], self.f5_l7policy['partition'])
