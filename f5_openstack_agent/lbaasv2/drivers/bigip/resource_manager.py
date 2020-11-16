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
import json
import urllib

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.ftp_profile \
    import FTPProfileHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_adapter \
    import L7PolicyServiceAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import tenants
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import serialized
from f5_openstack_agent.lbaasv2.drivers.bigip import virtual_address

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from pathlib import Path
from time import time

from requests import HTTPError

LOG = logging.getLogger(__name__)


class ResourceManager(object):

    _collection_key = 'baseResources'
    _key = 'baseResource'

    def __init__(self, driver):
        self.driver = driver
        self.service_queue = driver.service_queue
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
        return {
            "name": "faked",
            "partition": "faked"
        }

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

    def _create(self, bigip, payload, resource, service, **kwargs):
        resource_helper = kwargs.get("helper", self.resource_helper)
        resource_type = kwargs.get("type", self._resource)
        overwrite = kwargs.get("overwrite", True)
        if resource_helper.exists(bigip, name=payload['name'],
                                  partition=payload['partition']):
            if overwrite:
                LOG.debug("%s %s already exists ... updating",
                          resource_type, payload['name'])
                resource_helper.update(bigip, payload)
            else:
                LOG.debug("%s %s already exists, do not update.",
                          resource_type, payload['name'])
        else:
            LOG.debug("%s %s does not exist ... creating",
                      resource_type, payload['name'])
            resource_helper.create(bigip, payload)

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

    def _delete(self, bigip, payload, resource, service, **kwargs):
        resource_helper = kwargs.get("helper", self.resource_helper)
        resource_helper.delete(bigip, name=payload['name'],
                               partition=payload['partition'])

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

    def _create_payload(self, loadbalancer, service):
        vip = virtual_address.VirtualAddress(self.driver.service_adapter,
                                             loadbalancer)
        return vip.model()

    @serialized('LoadBalancerManager.create')
    @log_helpers.log_method_call
    def create(self, loadbalancer, service, **kwargs):
        self._pre_create(service)
        super(LoadBalancerManager, self).create(
            service["loadbalancer"], service)
        self._post_create(service)

    def _post_create(self, service):
        # create fdb for vxlan tunnel
        if not self.driver.conf.f5_global_routed_mode:
            self.driver.network_builder.update_bigip_l2(service)

    def _pre_create(self, service):
        loadbalancer = service["loadbalancer"]
        # allow address pair
        if self.driver.l3_binding:
            self.driver.l3_binding.bind_address(
                subnet_id=loadbalancer["vip_subnet_id"],
                ip_address=loadbalancer["vip_address"])

        self.tenant_manager.assure_tenant_created(service)
        traffic_group = self.driver.service_to_traffic_group(service)
        loadbalancer['traffic_group'] = traffic_group

        if not self.driver.conf.f5_global_routed_mode:
            self.driver.network_builder.prep_service_networking(
                service, traffic_group)

    @serialized('LoadBalancerManager.update')
    @log_helpers.log_method_call
    def update(self, old_loadbalancer, loadbalancer, service, **kwargs):
        super(LoadBalancerManager, self).update(
            old_loadbalancer, loadbalancer, service)

    @serialized('LoadBalancerManager.delete')
    @log_helpers.log_method_call
    def delete(self, loadbalancer, service, **kwargs):
        self._pre_delete(service)
        super(LoadBalancerManager, self).delete(loadbalancer, service)
        self._post_delete(service)

    def _pre_delete(self, service):
        # assign neutron network object in service
        # with route domain first
        # self.driver.network_builder is None in global routed mode
        if self.driver.network_builder:
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

        if self.driver.l3_binding:
            self.driver.l3_binding.unbind_address(
                subnet_id=loadbalancer["vip_subnet_id"],
                ip_address=loadbalancer["vip_address"])

    def _post_delete(self, service):
        # self.driver.network_builder is None in global routed mode
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
        self.http_cookie_persist_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.cookie_persistence)
        self.source_addr_persist_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.source_addr_persistence)
        self.http_profile_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.http_profile)
        self.ftp_helper = FTPProfileHelper()
        self.mutable_props = {
            "name": "description",
            "default_pool_id": "pool",
            "connection_limit": "connectionLimit"
        }

    def _create_payload(self, listener, service):
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
        persist_type = persist.get('type', "")
        if persist_type == "APP_COOKIE":
            return self._create_app_cookie_persist_profile(bigip, vs, persist)
        elif persist_type == "HTTP_COOKIE":
            return self._create_http_cookie_persist_profile(bigip, vs, persist)
        elif persist_type == "SOURCE_IP":
            return self._create_source_addr_persist_profile(bigip, vs, persist)

    def _create_app_cookie_persist_profile(self, bigip, vs, persist):
        listener_builder = self.driver.lbaas_builder.listener_builder
        listener_builder._add_cookie_persist_rule(vs, persist, bigip)
        return "app_cookie_" + vs['name']

    def _create_http_cookie_persist_profile(self, bigip, vs, persist):
        name = "http_cookie_" + vs['name']
        timeout = self.driver.conf.persistence_timeout
        rest = timeout
        day = str(rest / 86400)
        rest = rest % 86400
        hour = str(rest / 3600)
        rest = rest % 3600
        minute = str(rest / 60)
        rest = rest % 60
        second = str(rest)
        # expiration format is d:h:m:s
        expiration = day + ":" + hour + ":" + minute + ":" + second
        payload = {
            "name": name,
            "partition": vs['partition'],
            "expiration": expiration,
            "timeout": str(timeout)
        }
        super(ListenerManager, self)._create(
            bigip, payload, None, None, type="http-cookie",
            helper=self.http_cookie_persist_helper, overwrite=False)
        return name

    def _create_source_addr_persist_profile(self, bigip, vs, persist):
        name = "source_addr_" + vs['name']
        payload = {
            "name": name,
            "partition": vs['partition'],
            "timeout": str(self.driver.conf.persistence_timeout)
        }
        super(ListenerManager, self)._create(
            bigip, payload, None, None, type="source-addr",
            helper=self.source_addr_persist_helper, overwrite=False)
        return name

    def _create_ssl_profile(self, bigip, vs, tls):
        listener_builder = self.driver.lbaas_builder.listener_builder
        tls['name'] = vs['name']
        tls['partition'] = vs['partition']
        listener_builder.add_ssl_profile(tls, vs, bigip)

    def _delete_app_cookie_persist_profile(self, bigip, vs):
        listener_builder = self.driver.lbaas_builder.listener_builder
        listener_builder._remove_cookie_persist_rule(vs, bigip)

    def _delete_http_cookie_persist_profile(self, bigip, vs):
        payload = {
            "name": "http_cookie_" + vs['name'],
            "partition": vs['partition'],
        }
        super(ListenerManager, self)._delete(
            bigip, payload, None, None,
            helper=self.http_cookie_persist_helper)

    def _delete_source_addr_persist_profile(self, bigip, vs):
        payload = {
            "name": "source_addr_" + vs['name'],
            "partition": vs['partition'],
        }
        super(ListenerManager, self)._delete(
            bigip, payload, None, None,
            helper=self.source_addr_persist_helper)

    def _delete_persist_profile(self, bigip, vs):
        self._delete_app_cookie_persist_profile(bigip, vs)
        self._delete_http_cookie_persist_profile(bigip, vs)
        self._delete_source_addr_persist_profile(bigip, vs)

    def _delete_ssl_profiles(self, bigip, vs, service):
        listener_builder = self.driver.lbaas_builder.listener_builder
        tls = self.driver.service_adapter.get_tls(service)
        listener_builder.remove_ssl_profiles(tls, bigip)

    def _delete_http_profile(self, bigip, vs):
        payload = {
            "name": "http_profile_" + vs['name'],
            "partition": vs['partition'],
        }
        super(ListenerManager, self)._delete(
            bigip, payload, None, None,
            helper=self.http_profile_helper)

    def _create_http_profile(self, bigip, vs):
        # the logic is, if the http_profile_file is configured
        # in the ini file, then
        # 1) check if the configured file exists or not.
        # 2) parse the content in the file
        # 3) call the restful api to create the http_profile for the listener
        # 4) set the http_profile in the profiles.
        if self.driver.conf.f5_extended_profile:
            # check if the file exists or not.
            # check the content of the file content
            file_name = self.driver.conf.f5_extended_profile
            LOG.debug("extended profile file configured is %s",
                      file_name)
            profile_file = Path(file_name)
            if not profile_file.exists():
                LOG.warning("extended profile %s doesn't exist",
                            file_name)
                return
            try:
                with open(file_name) as fp:
                    payload = json.load(fp)
                if 'http_profile' not in payload:
                    LOG.debug("http profile is not defined in %s",
                              file_name)
                    return
                http_profile = payload['http_profile']
            except ValueError:
                LOG.warning("extended profile %s is not a valid json file",
                            file_name)
                return

            LOG.debug("http profile content is %s", http_profile)

            # The name and parition items in the file will be overwriten

            if 'name' in http_profile:
                del http_profile['name']
            http_profile['name'] = "http_profile_" + vs['name']

            if 'partition' in http_profile:
                del http_profile['partition']
            http_profile['partition'] = vs['partition']

            profile_name = '/' + http_profile['partition'] + '/' \
                           + http_profile['name']
            profiles = vs.get('profiles', [])
            # in agent_lite, we will not apply esd so that only
            # /common/http is possibly set in the profiles.
            if '/Common/http' in vs['profiles']:
                profiles.remove('/Common/http')
            profiles.append(profile_name)

            super(ListenerManager, self)._create(
                bigip, http_profile, None, None, type="http-profile",
                helper=self.http_profile_helper, overwrite=False)

    def _create(self, bigip, vs, listener, service):
        tls = self.driver.service_adapter.get_tls(service)
        if tls:
            self._create_ssl_profile(bigip, vs, tls)
        persist = service[self._key].get('session_persistence')
        if persist:
            profile = self._create_persist_profile(bigip, vs, persist)
            vs['persist'] = [{"name": profile}]
        ftp_enable = self.ftp_helper.enable_ftp(service)
        if ftp_enable:
            self.ftp_helper.add_profile(service, vs, bigip)

        loadbalancer = service.get('loadbalancer', dict())
        network_id = loadbalancer.get('network_id', "")
        self.driver.service_adapter.get_vlan(vs, bigip, network_id)
        if listener['protocol'] == "HTTP":
            self._create_http_profile(bigip, vs)
        super(ListenerManager, self)._create(bigip, vs, listener, service)

    def _update(self, bigip, vs, old_listener, listener, service):
        persist = None
        if vs.get('persist'):
            persist = service[self._key]['session_persistence']
        if persist:
            LOG.debug("Need to create or updte persist profile for %s %s",
                      self._resource, vs['name'])
            profile = self._create_persist_profile(bigip, vs, persist)
            vs['persist'] = [{"name": profile}]

        super(ListenerManager, self)._update(bigip, vs, old_listener, listener,
                                             service)

    def _delete(self, bigip, vs, listener, service):
        super(ListenerManager, self)._delete(bigip, vs, listener, service)
        self._delete_persist_profile(bigip, vs)
        self._delete_ssl_profiles(bigip, vs, service)
        self._delete_http_profile(bigip, vs)
        ftp_enable = self.ftp_helper.enable_ftp(service)
        if ftp_enable:
            self.ftp_helper.remove_profile(service, vs, bigip)

    @serialized('ListenerManager.create')
    @log_helpers.log_method_call
    def create(self, listener, service, **kwargs):
        super(ListenerManager, self).create(listener, service)

    @serialized('ListenerManager.update')
    @log_helpers.log_method_call
    def update(self, old_listener, listener, service, **kwargs):
        super(ListenerManager, self).update(
            old_listener, listener, service)

    @serialized('ListenerManager.delete')
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
        if 'members' in poolpayload:
            del poolpayload['members']
        if 'monitor' in poolpayload:
            del poolpayload['monitor']
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
        # Pool has other props to update
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

    @serialized('PoolManager.create')
    @log_helpers.log_method_call
    def create(self, pool, service, **kwargs):
        super(PoolManager, self).create(pool, service)

    @serialized('PoolManager.update')
    @log_helpers.log_method_call
    def update(self, old_pool, pool, service, **kwargs):
        super(PoolManager, self).update(old_pool, pool, service)

    @serialized('PoolManager.delete')
    @log_helpers.log_method_call
    def delete(self, pool, service, **kwargs):
        super(PoolManager, self).delete(pool, service)


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

    @serialized('MonitorManager.create')
    @log_helpers.log_method_call
    def create(self, monitor, service, **kwargs):
        super(MonitorManager, self).create(monitor, service)

    @serialized('MonitorManager.update')
    @log_helpers.log_method_call
    def update(self, old_monitor, monitor, service, **kwargs):
        super(MonitorManager, self).update(
            old_monitor, monitor, service)

    @serialized('MonitorManager.delete')
    @log_helpers.log_method_call
    def delete(self, monitor, service, **kwargs):
        super(MonitorManager, self).delete(monitor, service)


class MemberManager(ResourceManager):

    _collection_key = 'members'
    _key = 'member'

    def __init__(self, driver):
        super(MemberManager, self).__init__(driver)
        self._resource = "member"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.member)
        self._pool_mgr = PoolManager(self.driver)
        self.mutable_props = {
            "weight": "ratio",
            "admin_state_up": "session",
        }

    def _create_member_payload(self, loadbalancer, member):
        return self.driver.service_adapter._map_member(loadbalancer, member)

    def _create_payload(self, member, service):
        return self.driver.service_adapter.get_member(service)

    def _merge_members(self, lbaas_members, bigip_members, service):
        members_payload = []
        name_list = []

        start_time = time()
        """ old members from bigip """
        for item in bigip_members:
            fqdn = item.fqdn
            del item._meta_data
            content = item.to_dict()
            del content['fqdn']
            """ after to_dict the content's fqdn becomes a list somehow"""
            content['fqdn'] = fqdn

            if content['session'] == 'user-disabled':
                """ disable case"""
                if content['state'] != 'user-down':
                    del content['state']
                """ else case for force offline. Need to keep both
                    session and state """
            else:
                """ otherwise than user-disabled delete both session
                    and state"""
                LOG.debug("Default case %s %s",
                          content['session'], content['state'])
                del content['session']
                del content['state']

            members_payload.append(content)
            name_list.append(content['name'])

        """ new members from bigip """
        lb = service['loadbalancer']
        for item in lbaas_members:
            if item['name'] not in name_list:
                content = self._create_member_payload(lb, item)
                members_payload.append(content)

        if time() - start_time > .001:
            LOG.debug("For merge_members took %.5f secs" %
                      (time() - start_time))

        return members_payload

    @serialized('MemberManager.create')
    @log_helpers.log_method_call
    def create(self, resource, service, **kwargs):
        create_in_bulk = False
        if 'multiple' in service:
            create_in_bulk = service.get('multiple')

        if create_in_bulk is True:
            self._create_multiple(resource, service, **kwargs)
        else:
            self._create_single(resource, service, **kwargs)
        return

    def _create_multiple(self, resource, service, **kwargs):

        self.driver.prepare_network_for_member(service)
        LOG.debug("Begin to create in batch %s %s",
                  self._resource, resource['name'])
        if not service.get(self._key):
            self._search_element(resource, service)
        member = service.get('member')
        pool = {}
        pool['id'] = member['pool_id']
        self._pool_mgr._search_element(pool, service)
        pool_payload = self._pool_mgr._create_payload(pool, service)

        if 'members' not in pool_payload:
            LOG.error("None members in pool")
            return
        lbaas_members = service['members']
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            pool_resource = self._pool_mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )
            bigip_members = pool_resource.members_s.get_collection()

            del pool_payload['members']
            new_payload = self._merge_members(
                lbaas_members, bigip_members, service)
            pool_payload['members'] = new_payload
            self._shrink_payload(pool_payload,
                                 keys_to_keep=['partition',
                                               'name', 'members',
                                               'loadBalancingMode'])
            self._pool_mgr._update(bigip, pool_payload, None, None, service)
        LOG.debug("Finish to create in batch %s %s",
                  self._resource, resource['name'])

    def _create_single(self, resource, service, **kwargs):

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
        pool = {}
        pool['id'] = member['pool_id']
        self._pool_mgr._search_element(pool, service)
        pool_payload = self._pool_mgr._create_payload(pool, service)

        payload = self._create_payload(member, service)
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            pool_resource = self._pool_mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )
            pool_resource.members_s.members.create(**payload)
            self._shrink_payload(pool_payload,
                                 keys_to_keep=['partition',
                                               'name', 'loadBalancingMode'])
            self._pool_mgr._update(bigip, pool_payload, None, None, service)
        LOG.debug("Finish to create %s %s", self._resource, resource['id'])

    @serialized('MemberManager.delete')
    @log_helpers.log_method_call
    def delete(self, resource, service, **kwargs):

        self.driver.annotate_service_members(service)
        if not service.get(self._key):
            self._search_element(resource, service)

        LOG.debug("Begin to delete %s %s", self._resource, resource['id'])
        member = service['member']
        payload = self._create_payload(member, service)

        pool = {}
        pool['id'] = member['pool_id']
        self._pool_mgr._search_element(pool, service)
        pool_payload = self._pool_mgr._create_payload(pool, service)

        bigips = self.driver.get_config_bigips()
        loadbalancer = service.get('loadbalancer')
        for bigip in bigips:
            pool_resource = self._pool_mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )
            member_resource = pool_resource.members_s.members.load(
                name=urllib.quote(payload['name']),
                partition=payload['partition']
            )
            member_resource.delete()
            self._pool_mgr._delete_member_node(loadbalancer, member, bigip)
            self._shrink_payload(pool_payload,
                                 keys_to_keep=['partition',
                                               'name', 'loadBalancingMode'])
            self._pool_mgr._update(bigip, pool_payload, None, None, service)

        LOG.debug("Finish to delete %s %s", self._resource, resource['id'])

    @serialized('MemberManager.update')
    @log_helpers.log_method_call
    def update(self, old_resource, resource, service, **kwargs):
        self.driver.annotate_service_members(service)
        if not service.get(self._key):
            self._search_element(resource, service)

        LOG.debug("Begin to update %s %s", self._resource, resource['name'])
        member = service['member']
        old_member = old_resource

        pool = {}
        pool['id'] = member['pool_id']
        self._pool_mgr._search_element(pool, service)
        pool_payload = self._pool_mgr._create_payload(pool, service)

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
            pool_resource = self._pool_mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )

            member_resource = pool_resource.members_s.members.load(
                name=urllib.quote(payload['name']),
                partition=payload['partition']
            )

            member_resource.update(**payload)
            self._shrink_payload(pool_payload,
                                 keys_to_keep=['partition',
                                               'name', 'loadBalancingMode'])
            self._pool_mgr._update(bigip, pool_payload, None, None, service)
        LOG.debug("Finish to update %s %s", self._resource, payload['name'])


class L7PolicyManager(ResourceManager):

    _collection_key = 'l7policies'
    _key = 'l7policy'

    def __init__(self, driver):
        super(L7PolicyManager, self).__init__(driver)
        self._resource = "l7policy"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.l7policy)
        self.irule_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule)
        self.listener_mgr = ListenerManager(driver)
        self.l7rule_mgr = L7RuleManager(driver, l7policy_manager=self)

    def _get_policy_dict(self, l7policy, service):
        l7policy_adapter = L7PolicyServiceAdapter(self.driver.conf)
        policy_dict = {
            "l7rules": [],
            "l7policies": [],
            "f5_policy": {},
            "iRules": []
        }
        # Gather all l7policies and l7rules of this listener
        listener_id = l7policy['listener_id']
        for policy in service['l7policies']:
            if policy['listener_id'] == listener_id:
                policy_dict['l7policies'].append(policy)
                for rule in service['l7policy_rules']:
                    if rule['policy_id'] == policy['id']:
                        policy_dict['l7rules'].append(rule)
        policy_dict['f5_policy'] = l7policy_adapter.translate(policy_dict)
        if getattr(l7policy_adapter, 'iRules', None):
            policy_dict['iRules'] = l7policy_adapter.iRules
        self.policy_dict = policy_dict
        return policy_dict

    def _create_payload(self, l7policy, service):
        policy_dict = self._get_policy_dict(l7policy, service)
        return policy_dict['f5_policy']

    def _create_ltm_policy(self, bigip, payload, l7policy, service):
        # Load the existing virtual server
        self.listener_mgr._search_element({"id": l7policy['listener_id']},
                                          service)
        vs_helper = self.listener_mgr.resource_helper
        vs_name = self.driver.service_adapter.get_virtual_name(service)
        vs = vs_helper.load(bigip, name=vs_name['name'],
                            partition=vs_name['partition'])

        name = payload['name']
        partition = payload['partition']

        need_to_attach = True
        if not payload.get('rules', list()):
            # LTM policy has no rules. Cannot attach it to virtual server
            need_to_attach = False

        already_attached = vs.policies_s.policies.exists(name=name,
                                                         partition=partition)

        # Detach and empty policy first, if it has been attached perviously
        if not need_to_attach and already_attached:
            LOG.debug("Detach policy %s from virtula server %s", name, vs_name)
            policy = vs.policies_s.policies.load(name=name,
                                                 partition=partition)
            policy.delete()
            super(L7PolicyManager, self)._delete(bigip, payload, None, None)

        # Do not create an empty policy, which cannot be attached.
        # Purge job will cleanup all LTM policies, which are not attached
        if not need_to_attach:
            return

        # Create or Update LTM policy
        super(L7PolicyManager, self)._create(bigip, payload, None, None)

        if need_to_attach and not already_attached:
            # Attach LTM policy to virtual server
            LOG.debug("Attach policy %s to virtula server %s", name, vs_name)
            try:
                vs.policies_s.policies.create(name=name, partition=partition)
            except HTTPError as ex:
                if ex.response.status_code == 404:
                    # iControl API has bug. It may return 404 when attaching
                    # an LTM policy to virtual server. Need to try again and
                    # get 409 response to confirm the policy has been attached.
                    try:
                        vs.policies_s.policies.create(name=name,
                                                      partition=partition)
                    except HTTPError as ex:
                        if ex.response.status_code == 409:
                            LOG.debug("LTM policy %s has been attached", name)
                        else:
                            LOG.error("Fail to attach LTM policy %s", name)
                            raise ex
                    except Exception as ex:
                        raise ex
            except Exception as ex:
                raise ex

    def _create(self, bigip, payload, l7policy, service, **kwargs):
        # Create or update LTM policy
        self._create_ltm_policy(bigip, payload, l7policy, service)
        # Create or update all iRules
        for irule in self.policy_dict['iRules']:
            self.l7rule_mgr._create(bigip, irule, None, service)

    def _delete(self, bigip, payload, l7policy, service, **kwargs):
        # Create or update LTM policy
        self._create_ltm_policy(bigip, payload, l7policy, service)
        # Delete all iRules of this l7policy
        for l7rule in service[self.l7rule_mgr._collection_key]:
            if l7rule['policy_id'] == l7policy['id'] and \
               l7rule['compare_type'] == "REGEX":
                self.l7rule_mgr._delete(bigip, None, l7rule, service)

    @serialized('L7PolicyManager.create')
    @log_helpers.log_method_call
    def create(self, l7policy, service, **kwargs):
        super(L7PolicyManager, self).create(l7policy, service)

    @serialized('L7PolicyManager.update')
    @log_helpers.log_method_call
    def update(self, old_l7policy, l7policy, service, **kwargs):
        super(L7PolicyManager, self).create(l7policy, service)

    @serialized('L7PolicyManager.delete')
    @log_helpers.log_method_call
    def delete(self, l7policy, service, **kwargs):
        super(L7PolicyManager, self).delete(l7policy, service)


class L7RuleManager(ResourceManager):

    _collection_key = 'l7policy_rules'
    _key = 'l7rule'

    def __init__(self, driver, **kwargs):
        super(L7RuleManager, self).__init__(driver)
        self._resource = "l7rule"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule)
        self.l7policy_mgr = kwargs.get("l7policy_manager")
        if not self.l7policy_mgr:
            self.l7policy_mgr = L7PolicyManager(driver)
        self.mutable_props = {
            "type": "apiAnonymous",
            "invert": "apiAnonymous",
            "key": "apiAnonymous",
            "value": "apiAnonymous",
            "admin_state_up": "apiAnonymous"
        }

    def _search_l7policy_and_listener(self, l7rule, service):
        self.l7policy_mgr._search_element({"id": l7rule['l7policy_id']},
                                          service)
        self._l7policy = service[self.l7policy_mgr._key]

        listener_mgr = self.l7policy_mgr.listener_mgr
        listener_mgr._search_element({"id": self._l7policy['listener_id']},
                                     service)
        self._listener = service[listener_mgr._key]

    def _create_payload(self, l7rule, service):
        policy = self.l7policy_mgr._get_policy_dict(self._l7policy, service)
        for irule in policy['iRules']:
            if irule['name'] == "irule_" + l7rule['id']:
                return irule
        return super(L7RuleManager, self)._create_payload(l7rule, service)

    def _attach_irule_to_vs(self, bigip, payload, l7rule, service):
        # Attach iRule to virtual server
        vs_payload = self.driver.service_adapter.get_virtual_name(service)
        vs_helper = self.l7policy_mgr.listener_mgr.resource_helper
        vs = vs_helper.load(bigip, name=vs_payload['name'],
                            partition=vs_payload['partition'])
        vs_payload['rules'] = vs.rules
        # Append iRule to virtual server
        # iControl API can tolerate duplicated items
        vs_payload['rules'].append("/" + payload['partition'] +
                                   "/" + payload['name'])
        self.l7policy_mgr.listener_mgr._update(bigip, vs_payload,
                                               None, None, None)

    def _create(self, bigip, payload, l7rule, service, **kwargs):
        super(L7RuleManager, self)._create(bigip, payload, None, None)
        self._attach_irule_to_vs(bigip, payload, l7rule, service)

    def _update(self, bigip, payload, old_l7rule, l7rule, service, **kwargs):
        super(L7RuleManager, self)._update(bigip, payload, None, None)
        self._attach_irule_to_vs(bigip, payload, l7rule, service)

    def _delete(self, bigip, payload, l7rule, service, **kwargs):
        # Detach iRule from virtual server and delete it
        vs_payload = self.driver.service_adapter.get_virtual_name(service)
        vs_helper = self.l7policy_mgr.listener_mgr.resource_helper
        vs = vs_helper.load(bigip, name=vs_payload['name'],
                            partition=vs_payload['partition'])
        irule = {
            "name": "irule_" + l7rule['id'],
            "partition": vs_payload['partition']
        }
        irule_path = "/" + irule['partition'] + "/" + irule['name']
        vs_payload['rules'] = vs.rules
        # Exclude this REGEX l7rule from virtual server
        if irule_path in vs_payload['rules']:
            LOG.debug("Detach iRule %s from virtual server %s",
                      irule_path, vs_payload['name'])
            vs_payload['rules'].remove(irule_path)
            self.l7policy_mgr.listener_mgr._update(bigip, vs_payload,
                                                   None, None, None)
        super(L7RuleManager, self)._delete(bigip, irule, None, None)

    @serialized('L7RuleManager._create_irule')
    @log_helpers.log_method_call
    def _create_irule(self, l7rule, service, **kwargs):
        # Just a wrapper to utilize serialized decorator appropriately
        super(L7RuleManager, self).create(l7rule, service)

    @serialized('L7RuleManager._update_irule')
    @log_helpers.log_method_call
    def _update_irule(self, old_l7rule, l7rule, service, **kwargs):
        # Just a wrapper to utilize serialized decorator appropriately
        super(L7RuleManager, self).update(old_l7rule, l7rule, service)

    @serialized('L7RuleManager._delete_irule')
    @log_helpers.log_method_call
    def _delete_irule(self, l7rule, service, **kwargs):
        # Just a wrapper to utilize serialized decorator appropriately
        super(L7RuleManager, self).delete(l7rule, service)

    @log_helpers.log_method_call
    def _update_ltm_policy(self, l7policy, service):
        self.l7policy_mgr.create(l7policy, service)

    @log_helpers.log_method_call
    def create(self, l7rule, service, **kwargs):
        self._search_l7policy_and_listener(l7rule, service)
        if l7rule['compare_type'] == "REGEX":
            # Create iRule
            self._create_irule(l7rule, service, **kwargs)
        else:
            # Update LTM policy
            self._update_ltm_policy(self._l7policy, service)

    @log_helpers.log_method_call
    def update(self, old_l7rule, l7rule, service, **kwargs):
        self._search_l7policy_and_listener(l7rule, service)
        # Neutron LBaaS may have bugs. The old_l7rule and l7rule are always
        # identical, so that we are not able to identify the detail infomation.
        # Have to always update LTM policy and refresh iRule in any cases.
        self._update_ltm_policy(self._l7policy, service)
        if l7rule['compare_type'] == "REGEX":
            # Create iRule
            self._create_irule(l7rule, service, **kwargs)
        else:
            # Delete iRule
            self._delete_irule(l7rule, service, **kwargs)

    @log_helpers.log_method_call
    def delete(self, l7rule, service, **kwargs):
        self._search_l7policy_and_listener(l7rule, service)
        if l7rule['compare_type'] == "REGEX":
            # Delete iRule
            self._delete_irule(l7rule, service, **kwargs)
        else:
            # Update LTM policy
            self._update_ltm_policy(self._l7policy, service)
