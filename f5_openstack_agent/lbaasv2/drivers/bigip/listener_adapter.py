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

from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter


class ListenerAdapter(ServiceModelAdapter):

    def translate(self, service, listener, l7policy=None):
        f5_vs = {'name': self.get_name(listener.get('id', '')),
                 'partition': self.get_folder_name(
                     listener.get('tenant_id', ''))}

        if l7policy:
            f5_vs['l7policy_name'] = "wrapper_policy"

        return f5_vs
