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


class LbaasServiceObject(object):
    """Wrapper for service object created by F5 lbaas driver.

    Provides methods for accessing service object data. Intended to
    abstract service object so that it can be replaced with some other
    equivalent service (e.g., Neutron REST)
    """
    def __init__(self, service_object):
        self.service_object = service_object

    def get(self, obj_type, obj_id):
        """Returns a single object from service object.

        :param obj_type: object type (e.g., "listeners", "pools", etc.)
        :param obj_id: UUID of object to find
        :return: object or None if not found
        """
        objects = self.get_all(obj_type)
        if objects:
            for obj in objects:
                if obj['id'] == obj_id:
                    return obj

        return None

    def get_all(self, obj_type):
        if obj_type in self.service_object:
            return self.service_object[obj_type]
        else:
            return None

    def get_healthmonitor(self, uuid):
        return self.get('healthmonitors', uuid)

    def get_healthmonitors(self):
        return self.get_all('healthmonitors')

    def get_loadbalancer(self):
        return self.service_object.get('loadbalancer', None)

    def get_l7policy(self, uuid):
        return self.get('l7policies', uuid)

    def get_l7policies(self):
        return self.get_all('l7policies')

    def get_l7rule(self, uuid):
        return self.get('l7policy_rules', uuid)

    def get_l7rules(self):
        return self.get_all('l7policy_rules')

    def get_listener(self, uuid):
        return self.get('listeners', uuid)

    def get_listeners(self):
        return self.get_all('listeners')

    def get_member(self, uuid):
        return self.get('members', uuid)

    def get_members(self):
        return self.get_all('members')

    def get_pool(self, uuid):
        return self.get('pools', uuid)

    def get_pools(self):
        return self.get_all('pools')
