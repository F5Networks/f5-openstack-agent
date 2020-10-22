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

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as f5const
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import virtual_address
from f5_openstack_agent.lbaasv2.drivers.bigip import tenants

LOG = logging.getLogger(__name__)


class ResourceManager(object):

    _collection_key = 'baseResources'
    _key = 'baseResource'

    def __init__(self, driver):
        self.driver = driver
        self.mutable_props = {}

    def _shrink_payload(self, payload, **kwargs):
        keys_to_keep = kwargs.get('keys_to_keep', [])
        for key in payload.keys():
            if key not in keys_to_keep:
                del payload[key]

    def _search_element(self, resource, service):
        for element in service[self._collection_key]:
            if element['id'] == resource['id']:
                service[self._key] = element
                break

        if not service.get(self._key):
            raise Exception("Invalid input: %s %s "
                            "is not in service payload %s",
                            self._key, resource['id'], service)

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
        if not service.get(self._key):
            self._search_element(resource, service)
        payload = kwargs.get("payload",
                             self._create_payload(resource, service))

        if not payload or len(payload.keys()) == 0:
            LOG.info("Do not need to create %s", self._resource)
            return

        if not payload.get("name") or not payload.get("partition"):
            create_payload = self._create_payload(resource, service)
            payload['name'] = create_payload['name']
            payload['partition'] = create_payload['partition']

        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            self._create(bigip, payload, resource, service)
        LOG.debug("Finish to create %s %s", self._resource, payload['name'])

    @log_helpers.log_method_call
    def update(self, old_resource, resource, service, **kwargs):
        if not service.get(self._key):
            self._search_element(resource, service)
        payload = kwargs.get("payload",
                             self._update_payload(old_resource, resource,
                                                  service))

        if not payload or len(payload.keys()) == 0:
            LOG.debug("Do not need to update %s", self._resource)
            return

        if not payload.get("name") or not payload.get("partition"):
            create_payload = self._create_payload(resource, service)
            payload['name'] = create_payload['name']
            payload['partition'] = create_payload['partition']

        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            self._update(bigip, payload, old_resource, resource, service)
        LOG.debug("Finish to update %s %s", self._resource, payload['name'])

    @log_helpers.log_method_call
    def delete(self, resource, service, **kwargs):
        if not service.get(self._key):
            self._search_element(resource, service)
        payload = kwargs.get("payload",
                             self._create_payload(resource, service))
        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            self._delete(bigip, payload, resource, service)
        LOG.debug("Finish to delete %s %s", self._resource, payload['name'])


class LoadBalancerManager(ResourceManager):

    _collection_key = 'no_collection_key'
    _key = 'loadbalancer'

    def __init__(self, driver):
        super(LoadBalancerManager, self).__init__(driver)
        self._resource = "virtual address"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)
        self.tenant_manager = tenants.BigipTenantManager(self.driver.conf,
                                                         self.driver)
        self.mutable_props = {
            "name": "description",
            "description": "description",
            "admin_state_up": "enabled"
        }
        self.all_subnet_hints = {}

    def _create_vip(self, loadbalancer, service):
        vip = virtual_address.VirtualAddress(self.driver.service_adapter,
                                             loadbalancer)
        return vip

    @log_helpers.log_method_call
    def create(self, loadbalancer, service, **kwargs):
        self._pre_create(service)
        self._create_lb(service)
        self._post_create(service)

    def _post_create(self, service):
        # create fdb for vxlan tunnel
        if not self.driver.conf.f5_global_routed_mode:
            self.driver.network_builder.update_bigip_l2(service)

    def _create_lb(self, service):
        bigips = self.driver.get_config_bigips()
        loadbalancer = service["loadbalancer"]
        vip = self._create_vip(loadbalancer, service)

        for bigip in bigips:
            vip.assure(bigip)

        # allow address pair
        if self.driver.l3_binding:
            loadbalancer = service["loadbalancer"]
            self.driver.l3_binding.bind_address(
                subnet_id=loadbalancer["vip_subnet_id"],
                ip_address=loadbalancer["vip_address"])

    def _pre_create(self, service):
        loadbalancer = service["loadbalancer"]
        self.tenant_manager.assure_tenant_created(service)
        traffic_group = self.driver.service_to_traffic_group(service)
        loadbalancer['traffic_group'] = traffic_group

        if not self.driver.conf.f5_global_routed_mode:
            self.driver.network_builder.prep_service_networking(
                service, traffic_group)

    @log_helpers.log_method_call
    def delete(self, loadbalancer, service, **kwargs):
        self._pre_delete(service)
        self._delete_lb(service)
        self._post_delete(service)

    def _pre_delete(self, service):
        # assign neutron network object in service
        # with route domain first
        self.driver.network_builder._annotate_service_route_domains(
            service)

        bigips = self.driver.get_config_bigips()
        loadbalancer = service["loadbalancer"]

        for bigip in bigips:
            self.all_subnet_hints[bigip.device_name] = \
                {'check_for_delete_subnets': {},
                 'do_not_delete_subnets': []}
        self.driver.lbaas_builder._update_subnet_hints(
            loadbalancer["provisioning_status"],
            loadbalancer["vip_subnet_id"],
            loadbalancer["network_id"],
            self.all_subnet_hints,
            False
        )

    def _delete_lb(self, service):
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_config_bigips()
        vip = self._create_vip(loadbalancer, service)

        if self.driver.l3_binding:
            self.driver.l3_binding.unbind_address(
                subnet_id=loadbalancer["vip_subnet_id"],
                ip_address=loadbalancer["vip_address"])

        for bigip in bigips:
            vip.assure(bigip, delete=True)

    def _post_delete(self, service):
        if self.driver.network_builder:
            self.driver.network_builder.post_service_networking(
                service, self.all_subnet_hints)
        self.tenant_manager.assure_tenant_cleanup(
            service, self.all_subnet_hints)

class ListenerManager(ResourceManager):

    _collection_key = 'listeners'
    _key = 'listener'

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

    def _create_payload(self, listener, service):
        # Do not support TERMINATED_HTTPS
        if listener['protocol'] == "TERMINATED_HTTPS":
            raise Exception("Do not support TERMINATED_HTTPS protocol")

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
        self._search_element(listener, service)
        payload = self.driver.service_adapter.get_virtual_name(service)
        super(ListenerManager, self).delete(listener, service, payload=payload)


class PoolManager(ResourceManager):

    _collection_key = 'pools'
    _key = 'pool'

    def __init__(self, driver):
        super(PoolManager, self).__init__(driver)
        self._resource = "pool"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)
        self.mutable_props = {
            "name": "description",
            "description": "description",
            "lb_algorithm": "loadBalancingMode"
        }

    def _create_payload(self, pool, service):
        return self.driver.service_adapter.get_pool(service)

    def _create(self, bigip, poolpayload, pool, service):
        super(PoolManager, self)._create(bigip, poolpayload, pool, service)

        """ create the pool at first"""
        for listener in service['listeners']:
            if listener['default_pool_id'] == pool['id']:
                service['listener'] = listener
                break

        """Update the listener's default pool id if needed"""
        if service.get('listener'):
            LOG.debug("Find a listener %s for create pool", listener)
            mgr = ListenerManager(self.driver)
            listener_payload = mgr._create_payload(listener, service)
            self._shrink_payload(
                listener_payload,
                keys_to_keep=['partition', 'name', 'pool']
            )
            mgr._update(bigip, listener_payload, None, None, service)

    def _delete(self, bigip, payload, pool, service):

        mgr = ListenerManager(self.driver)
        for listener in service['listeners']:
            if listener['default_pool_id'] == pool['id']:
                service['listener'] = listener
                """ Unmap listener and pool"""
                listener_payload = mgr._create_payload(listener, service)
                self._shrink_payload(
                    listener_payload,
                    keys_to_keep=['partition', 'name', 'pool']
                )
                listener_payload['pool'] = ''
                mgr._update(bigip, listener_payload, None, None, service)
        super(PoolManager, self)._delete(bigip, payload, pool, service)


class MonitorManager(ResourceManager):

    _collection_key = 'healthmonitors'
    _key = 'healthmonitor'

    def __init__(self, driver, **kwargs):
        super(MonitorManager, self).__init__(driver)

        subtype = kwargs.get('type', '')

        if subtype == 'HTTP':
            monitor_type = resource_helper.ResourceType.http_monitor
            self._resource = 'http_monitor'
        elif subtype == 'HTTPS':
            monitor_type = resource_helper.ResourceType.https_monitor
            self._resource = 'https_monitor'
        elif subtype == 'PING':
            monitor_type = resource_helper.ResourceType.ping_monitor
            self._resource = 'ping_monitor'
        elif subtype == 'TCP':
            monitor_type = resource_helper.ResourceType.tcp_monitor
            self._resource = 'tcp_monitor'
        else:
            raise Exception("Invalid monitor type %s", subtype)

        self.resource_helper = resource_helper.BigIPResourceHelper(
            monitor_type
        )
        self.mutable_props = {
            "name": "description",
            "description": "description",
            "timeout": "timeout",
            "max_retries": "timeout",
            "url_path": "send",
            "http_method": "send",
            "url_path": "send",
            "delay": "interval",
            "expected_codes": "recv"
        }

    def _create_payload(self, healthmonitor, service):
        return self.driver.service_adapter.get_healthmonitor(service)

    def _create(self, bigip, payload, healthmonitor, service):

        super(MonitorManager, self)._create(
            bigip, payload, healthmonitor, service
        )

        """ update the pool  """
        healthmonitor = service['healthmonitor']
        mgr = PoolManager(self.driver)
        pool = {}
        pool['id'] = healthmonitor['pool_id']
        mgr._search_element(pool, service)
        pool_payload = mgr._create_payload(pool, service)

        self._shrink_payload(
            pool_payload,
            keys_to_keep=['partition', 'name', 'monitor']
        )
        mgr._update(bigip, pool_payload, None, None, service)

    def _delete(self, bigip, payload, healthmonitor, service):

        mgr = PoolManager(self.driver)
        monitor = service['healthmonitor']
        pool = {}
        pool['id'] = monitor['pool_id']
        mgr._search_element(pool, service)
        pool_payload = mgr._create_payload(pool, service)
        self._shrink_payload(
            pool_payload,
            keys_to_keep=['partition', 'name', 'monitor']
        )
        pool_payload['monitor'] = ''
        """ update the pool  """
        mgr._update(bigip, pool_payload, None, None, service)

        super(MonitorManager, self)._delete(
            bigip, payload, healthmonitor, service
        )
