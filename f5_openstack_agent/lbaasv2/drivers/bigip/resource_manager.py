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

import urllib

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import virtual_address

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from requests import HTTPError

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
        self.mutable_props = {
            "name": "description",
            "description": "description",
            "admin_state_up": "enabled"
        }

    def _create_payload(self, loadbalancer, service):
        vip = virtual_address.VirtualAddress(self.driver.service_adapter,
                                             loadbalancer)
        return vip.model()

    @log_helpers.log_method_call
    def create(self, loadbalancer, service, **kwargs):
        # TODO(qzhao): Future work
        pass

    @log_helpers.log_method_call
    def delete(self, loadbalancer, service, **kwargs):
        # TODO(qzhao): Future work
        pass


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

        if old_listener['default_pool_id'] != listener['default_pool_id']:
            payload['persist'] = create_payload['persist']

        return super(ListenerManager, self)._update_payload(
            old_listener, listener, service,
            payload=payload, create_payload=create_payload
        )

    def _create_persist_profile(self, bigip, vs, persist):
        listener_builder = self.driver.lbaas_builder.listener_builder
        listener_builder._add_cookie_persist_rule(vs, persist, bigip)

    def _delete_persist_profile(self, bigip, vs):
        listener_builder = self.driver.lbaas_builder.listener_builder
        listener_builder._remove_cookie_persist_rule(vs, bigip)

    def _create(self, bigip, vs, listener, service):
        persist = service[self._key].get('session_persistence')
        if persist and persist.get('type', "") == "APP_COOKIE":
            self._create_persist_profile(bigip, vs, persist)
        loadbalancer = service.get('loadbalancer', dict())
        network_id = loadbalancer.get('network_id', "")
        self.driver.service_adapter.get_vlan(vs, bigip, network_id)
        super(ListenerManager, self)._create(bigip, vs, listener, service)

    def _update(self, bigip, vs, old_listener, listener, service):
        persist = None
        if vs.get('persist'):
            persist = service[self._key]['session_persistence']
        if persist and persist.get('type', "") == "APP_COOKIE":
            LOG.debug("Need to create or updte persist profile for %s %s",
                      self._resource, vs['name'])
            self._create_persist_profile(bigip, vs, persist)
        super(ListenerManager, self)._update(bigip, vs, old_listener, listener,
                                             service)
        if persist and persist.get('type', "") != "APP_COOKIE":
            LOG.debug("Need to remove obsolete persist profile for %s %s",
                      self._resource, vs['name'])
            self._delete_persist_profile(bigip, vs)

    def _delete(self, bigip, vs, listener, service):
        super(ListenerManager, self)._delete(bigip, vs, listener, service)
        self._delete_persist_profile(bigip, vs)

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
        self.node_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.node)
        self.pool_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)
        self.mutable_props = {
            "name": "description",
            "description": "description",
            "lb_algorithm": "loadBalancingMode"
        }

    """ commonly used by pool and member """
    def _delete_member_node(self, loadbalancer, member, bigip):
        error = None
        svc = {'loadbalancer': loadbalancer,
               'member': member}
        node = self.driver.service_adapter.get_member_node(svc)
        try:
            self.node_helper.delete(bigip,
                                    name=urllib.quote(node['name']),
                                    partition=node['partition'])
        except HTTPError as err:
            # Possilbe error if node is shared with another member.
            # If so, ignore the error.
            if err.response.status_code == 400:
                LOG.debug(str(err))
            elif err.response.status_code == 404:
                LOG.debug(str(err))
            else:
                LOG.error("Unexpected node deletion error: %s",
                          urllib.quote(node['name']))
                error = f5_ex.NodeDeleteException(
                    "Unable to delete node {}".format(
                        urllib.quote(node['name'])))
        return error

    def _create_payload(self, pool, service):
        return self.driver.service_adapter.get_pool(service)

    def _update_payload(self, old_pool, pool, service, **kwargs):
        payload = {}
        create_payload = self._create_payload(pool, service)

        persist = service[self._key].get('session_persistence')
        if persist:
            payload['session_persistence'] = persist

        return super(PoolManager, self)._update_payload(
            old_pool, pool, service,
            payload=payload, create_payload=create_payload
        )

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
                keys_to_keep=['partition', 'name', 'pool', 'persist']
            )
            mgr._update(bigip, listener_payload, None, listener, service)

    def _update(self, bigip, payload, old_pool, pool, service):
        # Update listener session persistency if necessary
        if payload.get("session_persistence"):
            mgr = ListenerManager(self.driver)
            for listener in service['listeners']:
                if listener['default_pool_id'] == pool['id']:
                    service['listener'] = listener
                    listener_payload = mgr._create_payload(listener, service)
                    self._shrink_payload(
                        listener_payload,
                        keys_to_keep=['partition', 'name', 'persist']
                    )
                    mgr._update(bigip, listener_payload, None, None, service)
            del payload['session_persistence']
        # Pool has other props to upate
        for key in payload.keys():
            if key != "name" and key != "partition":
                super(PoolManager, self)._update(bigip, payload, old_pool,
                                                 pool, service)
                break

    def _delete(self, bigip, payload, pool, service):

        mgr = ListenerManager(self.driver)
        for listener in service['listeners']:
            if listener['default_pool_id'] == pool['id']:
                service['listener'] = listener
                """ Unmap listener and pool"""
                listener_payload = mgr._create_payload(listener, service)
                self._shrink_payload(
                    listener_payload,
                    keys_to_keep=['partition', 'name', 'pool', 'persist']
                )
                listener_payload['pool'] = ''
                mgr._update(bigip, listener_payload, None, None, service)
        super(PoolManager, self)._delete(bigip, payload, pool, service)

        """ try to delete the node which is only used by the pool """
        loadbalancer = service.get('loadbalancer')
        self.driver.annotate_service_members(service)
        members = service.get('members', list())
        for member in members:
            self._delete_member_node(loadbalancer, member, bigip)


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


class MemberManager(ResourceManager):

    _collection_key = 'members'
    _key = 'member'

    def __init__(self, driver):
        super(MemberManager, self).__init__(driver)
        self._resource = "member"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.member)
        self.mutable_props = {
            "weight": "ratio",
            "admin_state_up": "session",
        }

    def _create_payload(self, member, service):
        return self.driver.service_adapter.get_member(service)

    @log_helpers.log_method_call
    def create(self, resource, service, **kwargs):

        net_resource_create = True

        if 'loadbalancer' in service:
            loadbalancer = service['loadbalancer']
            if loadbalancer['vip_subnet_id'] == resource['subnet_id']:
                LOG.debug("Loadbalancer's subnet is the same as member's")
                net_resource_create = False

        if net_resource_create is True and 'members' in service:
            for item in service['members']:
                if item['id'] != resource['id'] and \
                   item['subnet_id'] == resource['subnet_id']:
                    LOG.debug("member %s has the same subnet", item['name'])
                    net_resource_create = False
                    break

        if net_resource_create is True:
            self.driver.prepare_network_for_member(service)
        else:
            self.driver.annotate_service_members(service)

        if not service.get(self._key):
            self._search_element(resource, service)
        LOG.debug("Begin to create %s %s", self._resource, resource['id'])
        member = service.get('member')
        mgr = PoolManager(self.driver)
        pool = {}
        pool['id'] = member['pool_id']
        mgr._search_element(pool, service)
        pool_payload = mgr._create_payload(pool, service)

        payload = self._create_payload(member, service)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            pool_resource = mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )
            pool_resource.members_s.members.create(**payload)
        LOG.debug("Finish to create %s %s", self._resource, resource['id'])

    @log_helpers.log_method_call
    def delete(self, resource, service, **kwargs):

        self.driver.annotate_service_members(service)
        if not service.get(self._key):
            self._search_element(resource, service)

        LOG.debug("Begin to delete %s %s", self._resource, resource['id'])
        member = service['member']
        payload = self._create_payload(member, service)

        mgr = PoolManager(self.driver)
        pool = {}
        pool['id'] = member['pool_id']
        mgr._search_element(pool, service)
        pool_payload = mgr._create_payload(pool, service)

        bigips = self.driver.get_config_bigips()
        loadbalancer = service.get('loadbalancer')
        for bigip in bigips:
            pool_resource = mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )
            member_resource = pool_resource.members_s.members.load(
                name=urllib.quote(payload['name']),
                partition=payload['partition']
            )
            member_resource.delete()
            mgr._delete_member_node(loadbalancer, member, bigip)

        LOG.debug("Finish to delete %s %s", self._resource, resource['id'])

    @log_helpers.log_method_call
    def update(self, old_resource, resource, service, **kwargs):
        self.driver.annotate_service_members(service)
        if not service.get(self._key):
            self._search_element(resource, service)

        LOG.debug("Begin to update %s %s", self._resource, resource['name'])
        member = service['member']
        old_member = old_resource

        mgr = PoolManager(self.driver)
        pool = {}
        pool['id'] = member['pool_id']
        mgr._search_element(pool, service)
        pool_payload = mgr._create_payload(pool, service)

        payload = self._update_payload(old_member, member, service)
        if member['weight'] == 0:
            payload['session'] = 'user-disabled'

        self._shrink_payload(
            payload,
            keys_to_keep=['partition', 'name', 'ratio', 'session']
        )

        if not payload or len(payload.keys()) == 0:
            LOG.debug("Do not need to update %s", self._resource)
            return

        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            pool_resource = mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )

            member_resource = pool_resource.members_s.members.load(
                name=urllib.quote(payload['name']),
                partition=payload['partition']
            )

            member_resource.update(**payload)
        LOG.debug("Finish to update %s %s", self._resource, payload['name'])
