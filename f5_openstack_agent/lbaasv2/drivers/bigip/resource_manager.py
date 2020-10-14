# coding=utf-8
# Copyright (c) 2020, F5 Networks, Inc.
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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper

LOG = logging.getLogger(__name__)


class ResourceManager(object):

    def __init__(self, driver):
        self.driver = driver
        self.mutable_props = {}

    def _create_payload(self, resource, service):
        return {}

    def _update_payload(self, old_resource, resource, service, **kwargs):
        payload = kwargs.get('payload', {})
        create_payload = kwargs.get('create_payload',
                                    self._create_payload(resource, service))

        for key in self.mutable_props.keys():
            old = old_resource.get(key)
            new = resource.get(key)
            if old != new:
                prop = self.mutable_props[key]
                payload[prop] = create_payload[prop]

        if len(payload.keys()) > 0:
            payload['name'] = create_payload['name']
            payload['partition'] = create_payload['partition']

        return payload

    def _create(self, bigip, payload, resource, service):
        if self.resource_helper.exists(bigip, name=payload['name'],
                                       partition=payload['partition']):
            LOG.debug("%s already exists ... updating", self._resource)
            self.resource_helper.update(bigip, payload)
        else:
            LOG.debug("%s does not exist ... creating", self._resource)
            self.resource_helper.create(bigip, payload)

    def _update(self, bigip, payload, old_resource, resource, service):
        if self.resource_helper.exists(bigip, name=payload['name'],
                                       partition=payload['partition']):
            LOG.debug("%s already exists ... updating", self._resource)
            self.resource_helper.update(bigip, payload)
        else:
            LOG.debug("%s does not exist ... creating", self._resource)
            payload = self._create_payload(resource, service)
            LOG.debug("%s payload is %s", self._resource, payload)
            self.resource_helper.create(bigip, payload)

    def _delete(self, bigip, payload, resource, service):
        self.resource_helper.delete(
            bigip, name=payload['name'], partition=payload['partition'])

    @log_helpers.log_method_call
    def create(self, resource, service, **kwargs):
        payload = kwargs.get("payload",
                             self._create_payload(resource, service))
        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            self._create(bigip, payload, resource, service)
        LOG.debug("Finish to create %s %s", self._resource, payload['name'])

    @log_helpers.log_method_call
    def update(self, old_resource, resource, service, **kwargs):
        payload = kwargs.get("payload",
                             self._update_payload(old_resource, resource,
                                                  service))

        if not payload or len(payload.keys()) == 0:
            LOG.debug("Do not need to update %s", self._resource)
            return

        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            self._update(bigip, payload, old_resource, resource, service)
        LOG.debug("Finish to update %s %s", self._resource, payload['name'])

    @log_helpers.log_method_call
    def delete(self, resource, service, **kwargs):
        payload = kwargs.get("payload",
                             self._create_payload(resource, service))
        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            self._delete(bigip, payload, resource, service)
        LOG.debug("Finish to delete %s %s", self._resource, payload['name'])


class ListenerManager(ResourceManager):

    def __init__(self, driver):
        super(ListenerManager, self).__init__(driver)
        self._resource = "virtual server"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.mutable_props = {
            "name": "description",
            "default_pool_id": "pool",
            "connection_limit": "connectionLimit"
        }

    def _search_listener(self, listener, service):
        for element in service['listeners']:
            if element['id'] == listener['id']:
                service['listener'] = element
                break
        if not service.get('listener'):
            raise Exception("Invalid input: listener %s "
                            "is not in service payload %s",
                            listener['id'], service)

    def _create_payload(self, listener, service):
        # Do not support TERMINATED_HTTPS
        if listener['protocol'] == "TERMINATED_HTTPS":
            raise Exception("Do not support TERMINATED_HTTPS protocol")

        self._search_listener(listener, service)
        return self.driver.service_adapter.get_virtual(service)

    def _update_payload(self, old_listener, listener, service, **kwargs):
        payload = {}
        create_payload = self._create_payload(listener, service)

        if old_listener['admin_state_up'] != listener['admin_state_up']:
            if listener['admin_state_up']:
                payload['enabled'] = True
            else:
                payload['disabled'] = True

        return super(ListenerManager, self)._update_payload(
            old_listener, listener, service,
            payload=payload, create_payload=create_payload
        )

    def _create(self, bigip, vs, listener, service):
        loadbalancer = service.get('loadbalancer', dict())
        network_id = loadbalancer.get('network_id', "")
        self.driver.service_adapter.get_vlan(vs, bigip, network_id)
        super(ListenerManager, self)._create(bigip, vs, listener, service)

    @log_helpers.log_method_call
    def delete(self, listener, service, **kwargs):
        self._search_listener(listener, service)
        payload = self.driver.service_adapter.get_virtual_name(service)
        super(ListenerManager, self).delete(listener, service, payload=payload)
