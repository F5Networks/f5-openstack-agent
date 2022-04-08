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
import netaddr
import os
import re
import urllib

from f5_openstack_agent.lbaasv2.drivers.bigip.acl import ACLHelper
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.ftp_profile \
    import FTPProfileHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.http_profile \
    import HTTPProfileHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.irule \
    import iRuleHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.l7policy_adapter \
    import L7PolicyServiceAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.ltm_policy \
    import LTMPolicyRedirect
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.tcp_profile \
    import TCPProfileHelper
from f5_openstack_agent.lbaasv2.drivers.bigip import tenants
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import serialized
from f5_openstack_agent.lbaasv2.drivers.bigip import virtual_address
from icontrol.exceptions import iControlUnexpectedHTTPError

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

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

    def _update(self, bigip, payload, old_resource, resource, service,
                **kwargs):
        resource_helper = kwargs.get("helper", self.resource_helper)
        resource_type = kwargs.get("type", self._resource)
        create_payload = kwargs.get("create_payload", {})
        if resource_helper.exists(bigip, name=payload['name'],
                                  partition=payload['partition']):
            LOG.debug("%s already exists ... updating", resource_type)
            resource_helper.update(bigip, payload)
        else:
            LOG.debug("%s does not exist ... creating", resource_type)
            if not create_payload:
                create_payload = self._create_payload(resource, service)
            LOG.debug("%s payload is %s", resource_type, create_payload)
            resource_helper.create(bigip, create_payload)

    def _delete(self, bigip, payload, resource, service, **kwargs):
        resource_helper = kwargs.get("helper", self.resource_helper)
        resource_helper.delete(bigip, name=payload['name'],
                               partition=payload['partition'])

    def _update_needed(self, payload, old_resource, resource):
        if not payload or len(payload.keys()) == 0:
            return False
        return True

    @log_helpers.log_method_call
    def create(self, resource, service=dict(), **kwargs):
        if service and not service.get(self._key):
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
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
        for bigip in bigips:
            self._create(bigip, payload, resource, service)
        LOG.debug("Finish to create %s %s", self._resource, payload['name'])

    @log_helpers.log_method_call
    def update(self, old_resource, resource, service=dict(), **kwargs):
        if service and not service.get(self._key):
            self._search_element(resource, service)
        payload = kwargs.get("payload",
                             self._update_payload(old_resource, resource,
                                                  service))

        if self._update_needed(payload, old_resource, resource) is False:
            LOG.debug("Do not need to update %s", self._resource)
            return

        if not payload.get("name") or not payload.get("partition"):
            create_payload = self._create_payload(resource, service)
            payload['name'] = create_payload['name']
            payload['partition'] = create_payload['partition']

        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
        for bigip in bigips:
            self._update(bigip, payload, old_resource, resource, service)
        LOG.debug("Finish to update %s %s", self._resource, payload['name'])

    @log_helpers.log_method_call
    def delete(self, resource, service=dict(), **kwargs):
        if service and not service.get(self._key):
            self._search_element(resource, service)
        payload = kwargs.get("payload",
                             self._create_payload(resource, service))
        LOG.debug("%s payload is %s", self._resource, payload)
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
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
        self.irule_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule)
        self.bwc_policy_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.bwc_policy)
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
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

    def _create(self, bigip, payload, loadbalancer, service, **kwargs):

        # create irule
        bandwidth = self.get_bandwidth_value(self.driver.conf, loadbalancer)
        if bandwidth > 0:
            self.__add_bwc(bigip, loadbalancer, bandwidth, service, False)

        super(LoadBalancerManager, self)._create(bigip, payload,
                                                 loadbalancer, service)

    def _delete(self, bigip, payload, loadbalancer, service, **kwargs):

        irule_payload = self._create_bwc_irule_payload(loadbalancer, True)
        super(LoadBalancerManager, self).\
            _delete(bigip, irule_payload, None, None,
                    type="irule",
                    helper=self.irule_helper)

        bwc_payload = self._create_bwc_payload(loadbalancer, 0)
        super(LoadBalancerManager, self).\
            _delete(bigip, bwc_payload, None, None, type="bwc_policy",
                    helper=self.bwc_policy_helper)

        super(LoadBalancerManager, self)._delete(bigip, payload,
                                                 loadbalancer, service)

    def _create_bwc_payload(self, loadbalancer, bandwidth):

        bwc_policy = {}
        bwc_policy['partition'] = self.driver.service_adapter.\
            get_folder_name(loadbalancer['tenant_id'])
        bwc_policy['name'] = 'bwc_policy_' + loadbalancer['id']
        if bandwidth > 0:
            bwc_policy['maxRate'] = bandwidth * 1000 * 1000
        return bwc_policy

    @staticmethod
    def get_bwc_policy_name(adapter, loadbalancer):

        policy_name = '/' + adapter.\
            get_folder_name(loadbalancer['tenant_id']) + \
            '/bwc_policy_' + loadbalancer['id']
        return policy_name

    @staticmethod
    def get_bwc_irule_name(adapter, loadbalancer):
        irule_name = '/' + adapter.\
            get_folder_name(loadbalancer['tenant_id']) + '/bwc_irule_'\
            + loadbalancer['id']
        return irule_name

    @staticmethod
    def get_bandwidth_value(conf, loadbalancer):

        if 'bandwidth' not in loadbalancer.keys():
            bandwidth = conf.f5_bandwidth_default
        else:
            bandwidth = loadbalancer.get('bandwidth', -1)

        bandwidth = int(bandwidth)
        if bandwidth < 0 or bandwidth > conf.f5_bandwidth_max:
            raise Exception("Invalid bandwidth value %d", bandwidth)

        return bandwidth

    def _create_bwc_irule_payload(self, loadbalancer, meta_only=False):
        # create irule profile
        irule = {}
        irule['partition'] = self.driver.service_adapter.\
            get_folder_name(loadbalancer['tenant_id'])
        irule['name'] = 'bwc_irule_' + loadbalancer['id']
        if not meta_only:
            bwc_policy_name = self.get_bwc_policy_name(
                self.driver.service_adapter,
                loadbalancer)
            irule['apiAnonymous'] = "when SERVER_CONNECTED {\n\
                    BWC::policy attach " + bwc_policy_name + "\n}"
        return irule

    def _post_create(self, service):
        # create fdb for vxlan tunnel
        if not self.driver.conf.f5_global_routed_mode:
            self.driver.network_builder.update_bigip_l2(service)

    def _pre_create(self, service):

        self._check_nonshared_network(service)
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
            self.driver.network_builder.config_snat(service)

    def __get_update_operation(self, old_loadbalancer, loadbalancer):

        old_value = self.get_bandwidth_value(self.driver.conf,
                                             old_loadbalancer)
        new_value = self.get_bandwidth_value(self.driver.conf,
                                             loadbalancer)
        if old_value == new_value:
            return 'None'
        else:
            if new_value > 0:
                return 'Add'
            else:
                return 'Delete'
        return 'None'

    def __update_listener_bwc(self, bigip, loadbalancer, service, add=True):

        if 'listeners' in service.keys():
            irule_name = self.get_bwc_irule_name(
                self.driver.service_adapter, loadbalancer)
            bwc_policy = self.get_bwc_policy_name(
                self.driver.service_adapter, loadbalancer)
            for listener in service['listeners']:
                vs_payload = self.driver.service_adapter.\
                    _init_virtual_name(loadbalancer, listener)
                # add is True then add irule to vs and otherwise delete irule
                # from vs
                vs = self.vs_helper.load(bigip, name=vs_payload['name'],
                                         partition=vs_payload['partition'])
                vs_payload['rules'] = vs.rules
                if add is True:
                    if irule_name not in vs_payload['rules']:
                        vs_payload['rules'].append(irule_name)
                    vs_payload['bwcPolicy'] = bwc_policy
                else:
                    if irule_name in vs_payload['rules']:
                        vs_payload['rules'].remove(irule_name)
                    vs_payload['bwcPolicy'] = 'None'
                self.vs_helper.update(bigip, vs_payload)
        return

    def __add_bwc(self, bigip, loadbalancer, bandwidth, service,
                  update_listener=True):
        # The logic is , add the irule bwc policies and go through listeners to
        # bind the bwc policy.
        payload = self._create_bwc_payload(loadbalancer, bandwidth)
        super(LoadBalancerManager, self)._create(
            bigip, payload, None, None, type="bwc_policy",
            helper=self.bwc_policy_helper, overwrite=True)

        payload = self._create_bwc_irule_payload(loadbalancer)
        super(LoadBalancerManager, self)._create(
            bigip, payload, None, None, type="irule",
            helper=self.irule_helper, overwrite=True)

        # go through the listeners and update them
        if update_listener is True:
            self.__update_listener_bwc(bigip, loadbalancer, service)
        return

    def __delete_bwc(self, bigip, loadbalancer, service):
        # The logic is , unbond the listenres' bwc policy and delete the irule
        # bwc policies and go through listeners to

        # go through the listeners and delete them
        self.__update_listener_bwc(bigip, loadbalancer, service, False)
        payload = self._create_bwc_irule_payload(loadbalancer, True)
        super(LoadBalancerManager, self)._delete(bigip, payload,
                                                 None, None,
                                                 type="irule",
                                                 helper=self.irule_helper)

        payload = self._create_bwc_payload(loadbalancer, 0)
        super(LoadBalancerManager, self).\
            _delete(bigip, payload, None, None,
                    type="bwc_policy", helper=self.bwc_policy_helper)
        return

    def _update_bwc(self, old_loadbalancer, loadbalancer, service):
        operate = self.__get_update_operation(old_loadbalancer, loadbalancer)
        LOG.debug("bwc operation is %s.", operate)
        bigips = self.driver.get_config_bigips()
        bandwidth = self.get_bandwidth_value(self.driver.conf, loadbalancer)
        for bigip in bigips:
            if operate == 'Add':
                self.__add_bwc(bigip, loadbalancer, bandwidth, service)
            elif operate == 'Delete':
                self.__delete_bwc(bigip, loadbalancer, service)
            else:
                LOG.debug("Don't need any update.")
        return

    def _check_nonshared_network(self, service):
        loadbalancer = service["loadbalancer"]
        tenant_id = loadbalancer['tenant_id']

        lb_net_id = loadbalancer['network_id']
        network = self.driver.service_adapter.get_network_from_service(
            service, lb_net_id)
        net_project_id = network["project_id"]

        if self.driver.conf.f5_global_routed_mode:
            shared = network["shared"]
            if not shared:
                if tenant_id != net_project_id:
                    raise f5_ex.ProjectIDException(
                        "The tenant project id is %s. "
                        "The nonshared netwok/subnet project id is %s. "
                        "They are not belong to the same tenant." %
                        (tenant_id, net_project_id))
            return

        if not self.driver.network_builder.l2_service.is_common_network(
                network):
            if tenant_id != net_project_id:
                raise f5_ex.ProjectIDException(
                    "The tenant project id is %s. "
                    "The nonshared netwok/subnet project id is %s. "
                    "They are not belong to the same tenant." %
                    (tenant_id, net_project_id))

    def _update_2_limits(self, old_loadbalancer, loadbalancer, service):
        # TODO(xie): delete following lines, 4 test
        # old_loadbalancer['flavor'] = 4
        # loadbalancer['flavor'] = 5

        LOG.info('inside _update_2_limits')
        old_flavor = old_loadbalancer.get('flavor')
        new_flavor = loadbalancer.get('flavor')
        LOG.debug(old_flavor)
        LOG.debug(new_flavor)

        if not new_flavor or int(new_flavor) < 0 or int(new_flavor) > 7:
            LOG.error('flavor id not expected. neglect only')
            return

        # refactor
        flavor_dict = {
            "1": {
                'connection_limit': 5000,
                'rate_limit': 3000
            },
            "2": {
                'connection_limit': 50000,
                'rate_limit': 5000
            },
            "3": {
                'connection_limit': 100000,
                'rate_limit': 10000
            },
            "4": {
                'connection_limit': 200000,
                'rate_limit': 20000
            },
            "5": {
                'connection_limit': 500000,
                'rate_limit': 50000
            },
            "6": {
                'connection_limit': 1000000,
                'rate_limit': 100000
            },
            "7": {
                'connection_limit': 8000000,
                'rate_limit': 100000
            }
        }

        # add some checks
        if not old_flavor or old_flavor != new_flavor:
            if new_flavor == 0:
                listener_connection_limit = 0
                listener_rate_limit = 0
            else:
                ratio1 = self.driver.conf.connection_limit_ratio
                LOG.debug(ratio1)
                ratio2 = self.driver.conf.connection_rate_limit_ratio
                LOG.debug(ratio2)

                listener_connection_limit = \
                    flavor_dict[str(new_flavor)]['connection_limit'] / ratio1

                listener_rate_limit = \
                    flavor_dict[str(new_flavor)]['rate_limit'] / ratio2

            LOG.info('listener_connection_limit to use:')
            LOG.info(listener_connection_limit)

            LOG.info('listener_rate_limit to use:')
            LOG.info(listener_rate_limit)

            if 'listeners' in service.keys():
                bigips = self.driver.get_config_bigips()
                for bigip in bigips:
                    LOG.info(bigip)
                    for listener in service['listeners']:
                        vs_payload = self.driver.service_adapter.\
                            _init_virtual_name(loadbalancer, listener)

                        vs_payload['connectionLimit'] = \
                            listener_connection_limit
                        vs_payload['rateLimit'] = listener_rate_limit
                        vs_payload['rateLimitMode'] = 'destination'
                        vs_payload['rateLimitDstMask'] = 32
                        LOG.info(vs_payload)
                        self.vs_helper.update(bigip, vs_payload)

    @serialized('LoadBalancerManager.update')
    @log_helpers.log_method_call
    def update(self, old_loadbalancer, loadbalancer, service, **kwargs):
        self._update_bwc(old_loadbalancer, loadbalancer, service)
        self._update_2_limits(old_loadbalancer, loadbalancer, service)
        self._update_flavor_snat(old_loadbalancer, loadbalancer, service)

        super(LoadBalancerManager, self).update(
            old_loadbalancer, loadbalancer, service)

    def _update_flavor_snat(
        self, old_loadbalancer, loadbalancer, service
    ):
        if self.driver.network_builder:
            if loadbalancer.get('flavor') != \
                    old_loadbalancer.get('flavor'):
                self.driver.network_builder.update_flavor_snat(
                    old_loadbalancer, loadbalancer, service
                )

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
        self._check_nonshared_network(service)
        if self.driver.network_builder:
            self.driver.network_builder._annotate_service_route_domains(
                service)

        loadbalancer = service["loadbalancer"]

        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
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
            self.driver.network_builder.remove_flavor_snat(service)
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
        self.ftp_helper = FTPProfileHelper()
        self.http_helper = HTTPProfileHelper()
        self.acl_helper = ACLHelper()
        self.irule_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule)
        self.tcp_helper = TCPProfileHelper()
        self.tcp_irule_helper = iRuleHelper()

        self.mutable_props = {
            "name": "description",
            "default_pool_id": "pool",
            "connection_limit": "connectionLimit"
        }
        self.profile_map = {
            "http_profile": {
                "condition": self._isHTTPorTLS,
                "customize": self._customize,
                "helper": resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.http_profile)
            },
            "http2_profile": {
                "condition": False,
                "helper": resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.http2_profile)
            },
            "http2tls_profile": {
                "condition": self._isHTTP2TLS,
                "helper": resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.http2_profile)
            },
            "websocket_profile": {
                "condition": False,
                "partition": "Common",
                "name": "websocket",
                "overwrite": False,
                "helper": resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.websocket_profile)
            }
        }
        self.extended_profiles = {}
        self._load_extended_profiles()
        self.cipher_policy = {}
        self._load_cipher_policy()

    def _isHTTP2TLS(self, listener):
        if listener['protocol'] != "TERMINATED_HTTPS":
            return False
        http2tls = listener.get('http2', False)
        return http2tls

    def _isHTTP2(self, listener):
        if listener['protocol'] != "HTTP":
            return False
        http2 = listener.get('http2', False)
        return http2

    def _isHTTPorTLS(self, listener):
        if listener['protocol'] == "HTTP" or \
           listener['protocol'] == "TERMINATED_HTTPS":
            return True
        else:
            return False

    def _isRedirect(self, listener):
        return listener.get("redirect_up", False)

    def _customize(self, profile_type, profile, listener):
        # NOTE(qzhao): The default behavior is to merge customized properties
        # into profile payload. That is for the profile like http_profile, who
        # supports to fetch addtional properties from customized json via API.
        # If any other profile requires different behavior, need to implement
        # that specific behavior by itself.
        customized = self._customized_profile(profile_type, listener)
        customized.update(
            self.http_helper.set_xff(listener)
        )
        profile.update(customized)

    def _create_payload(self, listener, service):
        payload = self.driver.service_adapter.get_virtual(service)
        profiles = payload.get('profiles', [])
        if '/Common/http' in profiles:
            profiles.remove('/Common/http')
        if self._isHTTPorTLS(listener):
            profiles.append(self.driver.conf.f5_request_logging_profile)
        return payload

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

    def _check_tls_changed(self, old_listener, listener):
        if not old_listener:
            return False
        if listener['protocol'] == "TERMINATED_HTTPS":
            LOG.debug("Finding tls setting  differences.")
            old_sni = [n['tls_container_id']
                       for n in old_listener['sni_containers']]
            sni = [n['tls_container_id']
                   for n in listener['sni_containers']]
            if old_listener['default_tls_container_id'] != \
               listener['default_tls_container_id'] or old_sni != sni:
                LOG.debug("tls changes happen")
                return True

            # If client authentication setting changes,
            # also need to update client ssl profile.
            old_mode = old_listener.get('mutual_authentication_up', False)
            new_mode = listener.get('mutual_authentication_up', False)
            old_ca = old_listener.get('ca_container_id', "")
            new_ca = listener.get('ca_container_id', "")

            if old_mode != new_mode or old_ca != new_ca:
                return True
            # if http2 property changes
            # also need to update client ssl profile
            old_http2 = old_listener.get('http2', False)
            new_http2 = listener.get('http2', False)
            if old_http2 != new_http2:
                return True

            # If cipher setting changes, need to update client ssl profile.
            old_tls_protocols = old_listener.get('tls_protocols', "")
            tls_protocols = listener.get('tls_protocols', "")
            old_cipher_suites = old_listener.get('cipher_suites', "")
            cipher_suites = listener.get('cipher_suites', "")
            if old_tls_protocols != tls_protocols:
                return True
            if tls_protocols != "" and old_cipher_suites != cipher_suites:
                return True

        return False

    def _check_customized_changed(self, old_listener, listener):
        if not old_listener:
            return False
        if listener['protocol'] == "HTTP" or \
           listener['protocol'] == "TERMINATED_HTTPS":
            old_customized = old_listener.get('customized', None)
            new_customized = listener.get('customized', None)
            if old_customized != new_customized:
                return True
        return False

    def _check_http2_changed(self, old_listener, listener):
        if old_listener.get("http2") != listener.get("http2"):
            return True
        return False

    def _check_redirect_changed(self, old_listener, listener):
        if old_listener.get("redirect_up") != listener.get("redirect_up"):
            return True

        if listener.get("redirect_up"):
            for key in ["redirect_port", "redirect_protocol"]:
                old_value = old_listener.get(key)
                new_value = listener.get(key)
                if old_value != new_value:
                    return True

        return False

    def _update_needed(self, payload, old_listener, listener):
        if self._check_tls_changed(old_listener, listener) or \
                self._check_customized_changed(old_listener, listener) or \
                self._check_redirect_changed(old_listener, listener) or \
                self._check_http2_changed(old_listener, listener) or \
                self.tcp_helper.need_update_tcp(old_listener, listener) or \
                self.http_helper.need_update_xff(old_listener, listener):
            return True
        return super(ListenerManager, self)._update_needed(
            payload, old_listener, listener)

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

        # persistence_timeout might be a string
        try:
            timeout = int(persist.get("persistence_timeout") or 0)
        except ValueError as ex:
            LOG.warning(ex.message)
            timeout = 0
        if timeout <= 0:
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
            helper=self.http_cookie_persist_helper)
        return name

    def _create_source_addr_persist_profile(self, bigip, vs, persist):
        name = "source_addr_" + vs['name']

        # persistence_timeout might be a string
        try:
            timeout = int(persist.get("persistence_timeout") or 0)
        except ValueError as ex:
            LOG.warning(ex.message)
            timeout = 0
        if timeout <= 0:
            timeout = self.driver.conf.persistence_timeout

        payload = {
            "name": name,
            "partition": vs['partition'],
            "timeout": str(timeout)
        }
        super(ListenerManager, self)._create(
            bigip, payload, None, None, type="source-addr",
            helper=self.source_addr_persist_helper)
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
        tls['name'] = vs['name']
        listener_builder.remove_ssl_profiles(tls, bigip)
        # Cleanup cipher group and rule, if they exist.
        try:
            for handle in [
                bigip.tm.ltm.cipher.groups.group,
                bigip.tm.ltm.cipher.rules.rule
            ]:
                if handle.exists(name=vs['name'], partition="Common"):
                    obj = handle.load(name=vs['name'], partition="Common")
                    obj.delete()
        except HTTPError as err:
            # Tolerate HTTP 400 error, because ssl profile and cipher
            # can not be deleted when updating a listener.
            if err.response.status_code != 400:
                raise err

    def _load_extended_profiles(self):
        if not self.driver.conf.f5_extended_profile:
            return

        file_name = self.driver.conf.f5_extended_profile
        if not os.path.exists(file_name):
            LOG.warning("Extended profile %s doesn't exist", file_name)
            return

        try:
            with open(file_name) as file:
                self.extended_profiles = json.load(file)
                self._filter_depercated(self.extended_profiles)
        except ValueError:
            LOG.error("Extended profile %s is an invalid json", file_name)
            return

        # Remove name and partition attributes
        for profile_type in self.extended_profiles.keys():
            profile = self.extended_profiles[profile_type]
            for key in ["name", "partition"]:
                if key in profile:
                    del profile[key]
        return

    def _load_cipher_policy(self):
        if not self.driver.conf.f5_cipher_policy:
            return

        file_name = self.driver.conf.f5_cipher_policy
        if not os.path.exists(file_name):
            LOG.warning("Cipher policy %s doesn't exist", file_name)
            return

        try:
            with open(file_name) as file:
                self.cipher_policy = json.load(file)
        except ValueError:
            LOG.error("Cipher policy %s is an invalid json", file_name)

        return

    def _filter_depercated(self, cust):
        depercated = {"http_profile": ["insertXforwardedFor"]}

        for profile, depercated_vals in depercated.items():
            cust_profile = cust.get(profile)
            if cust_profile:
                for val in depercated_vals:
                    if val in cust_profile:
                        del cust_profile[val]

    def _customized_profile(self, profile_type, listener):
        if 'customized' not in listener or not listener['customized']:
            return {}

        try:
            customized = json.loads(listener['customized'])
            self._filter_depercated(customized)
        except ValueError:
            LOG.error("Invalid json format: %s", listener['customized'])
            return {}

        if profile_type not in customized:
            return {}

        return customized.get(profile_type, {})

    def _profile_condition(self, profile_type, listener):
        condition = self.profile_map[profile_type]["condition"]
        if callable(condition):
            return condition(listener)
        elif isinstance(condition, bool):
            return condition
        else:
            return False

    def _create_extended_profiles(self, bigip, listener, vs):
        for profile_type in self.profile_map.keys():
            if self._profile_condition(profile_type, listener):
                profile = self.extended_profiles.get(profile_type, {})
                customize = self.profile_map[profile_type].get("customize")
                if callable(customize):
                    customize(profile_type, profile, listener)
                profile['partition'] = self.profile_map[profile_type].get(
                    "partition", vs['partition'])
                profile['name'] = self.profile_map[profile_type].get(
                    "name", profile_type + "_" + vs['name'])
                overwrite = self.profile_map[profile_type].get(
                    "overwrite", True)
                helper = self.profile_map[profile_type]['helper']
                super(ListenerManager, self)._create(
                    bigip, profile, None, None, type=profile_type,
                    helper=helper, overwrite=overwrite)
                loc = "/" + profile['partition'] + "/" + profile['name']
                if "profiles" not in vs:
                    vs['profiles'] = list()
                if loc not in vs['profiles']:
                    vs['profiles'].append(loc)

    def _update_extended_profiles(self, bigip, old_listener, listener, vs):
        for profile_type in self.profile_map.keys():
            old_cond = self._profile_condition(profile_type, old_listener)
            new_cond = self._profile_condition(profile_type, listener)

            if old_cond == new_cond and new_cond:
                # Profile should be already there. Perhaps we need to update
                # profile content, because some profiles (eg. http_profile)
                # support to fetch property via customized json from API.
                # In this case, needn't to consider the initial profile
                # properties defined in json file.
                old_profile = {}
                profile = {}
                whole_profile = self.extended_profiles.get(profile_type, {})
                customize = self.profile_map[profile_type].get("customize")
                if callable(customize):
                    customize(profile_type, old_profile, old_listener)
                    customize(profile_type, profile, listener)
                    customize(profile_type, whole_profile, listener)
                changed = profile != old_profile
                profile['partition'] = self.profile_map[profile_type].get(
                    "partition", vs['partition'])
                profile['name'] = self.profile_map[profile_type].get(
                    "name", profile_type + "_" + vs['name'])
                whole_profile['partition'] = profile['partition']
                whole_profile['name'] = profile['name']
                overwrite = self.profile_map[profile_type].get(
                    "overwrite", True)
                helper = self.profile_map[profile_type]['helper']
                if changed:
                    super(ListenerManager, self)._update(
                        bigip, profile, None, None, None,
                        type=profile_type, helper=helper,
                        create_payload=whole_profile)
                    self._attach_profile(bigip, vs, profile)
            elif old_cond != new_cond and new_cond:
                # Need to create and attach profile
                profile = self.extended_profiles.get(profile_type, {})
                customize = self.profile_map[profile_type].get("customize")
                if callable(customize):
                    customize(profile_type, profile, listener)
                profile['partition'] = self.profile_map[profile_type].get(
                    "partition", vs['partition'])
                profile['name'] = self.profile_map[profile_type].get(
                    "name", profile_type + "_" + vs['name'])
                overwrite = self.profile_map[profile_type].get(
                    "overwrite", True)
                helper = self.profile_map[profile_type]['helper']
                super(ListenerManager, self)._create(
                    bigip, profile, None, None, type=profile_type,
                    helper=helper, overwrite=overwrite)
                self._attach_profile(bigip, vs, profile)
            elif old_cond != new_cond and not new_cond:
                # Need to detach and delete profile
                profile = {}
                profile['partition'] = self.profile_map[profile_type].get(
                    "partition", vs['partition'])
                profile['name'] = self.profile_map[profile_type].get(
                    "name", profile_type + "_" + vs['name'])
                self._detach_profile(bigip, vs, profile)
                # Do not delete shared profile under /Common
                if profile['partition'] != "Common":
                    helper = self.profile_map[profile_type]['helper']
                    super(ListenerManager, self)._delete(
                        bigip, profile, None, None, type=profile_type,
                        helper=helper)

    def _delete_extended_profiles(self, bigip, listener, vs):
        for profile_type in self.profile_map.keys():
            profile = {}
            profile['partition'] = vs['partition']
            profile['name'] = profile_type + "_" + vs['name']
            helper = self.profile_map[profile_type]['helper']
            # Do not delete shared profile under /Common
            if profile['partition'] != "Common":
                super(ListenerManager, self)._delete(
                    bigip, profile, None, None, type=profile_type,
                    helper=helper)

    def _attach_profile(self, bigip, vs, profile):
        if profile['name'].startswith("http_profile_"):
            return self._attach_http_profile(bigip, vs, profile)

        v = self.resource_helper.load(bigip, name=vs['name'],
                                      partition=vs['partition'])
        if v.profiles_s.profiles.exists(name=profile['name'],
                                        partition=profile['partition']):
            LOG.debug("Profile %s has already been attached to vs %s",
                      profile['name'], vs['name'])
        else:
            full_name = "/" + profile['partition'] + "/" + profile['name']
            v.profiles_s.profiles.create(name=full_name,
                                         partition=profile['partition'])

    def _attach_http_profile(self, bigip, vs, profile):
        # If VS is created by legacy Agent instead of Agent Lite, we have to
        # patch VS profiles property, because /Common/http cannot be dettached.
        loc = "/" + profile["partition"] + "/" + profile["name"]
        attached = False
        payload = {
            "name": vs['name'],
            "partition": vs['partition'],
            "profiles": []
        }
        v = self.resource_helper.load(bigip, name=vs['name'],
                                      partition=vs['partition'],
                                      expand_subcollections=True)
        http_pattern = "https://localhost/mgmt/tm/ltm/profile/http/"
        for p in v.profilesReference['items']:
            profile_item = {}
            if p['fullPath'] == loc:
                attached = True
                break
            if re.search(http_pattern, p['nameReference']['link']):
                profile_item['name'] = loc
                payload['profiles'].append(profile_item)
            else:
                profile_item['name'] = p['fullPath']
                if p.get('context', None):
                    profile_item['context'] = p['context']
                payload['profiles'].append(profile_item)
        if not attached:
            self._update(bigip, payload, None, None, None)
        else:
            LOG.debug("Profile %s has already been attached to vs %s",
                      profile['name'], vs['name'])

    def _detach_profile(self, bigip, vs, profile):
        v = self.resource_helper.load(bigip, name=vs['name'],
                                      partition=vs['partition'])
        if v.profiles_s.profiles.exists(name=profile['name'],
                                        partition=profile['partition']):
            p = v.profiles_s.profiles.load(name=profile['name'],
                                           partition=profile['partition'])
            # Do not delete shared profile under /Common
            if profile['partition'] != "Common":
                p.delete()
        else:
            LOG.debug("Profile %s is not attached to vs %s",
                      profile['name'], vs['name'])

    def _create_websocket_irule(self, bigip, vs):
        # Websocket iRule is shared across all partitions. Needn't delete it.
        irule = {
            "name": "websocket_irule",
            "partition": "Common",
            "apiAnonymous": (
                'when HTTP_REQUEST {\n'
                '  if {([string tolower [HTTP::header value Upgrade]]\n'
                '                       equals "websocket") &&\n'
                '      ([string tolower [HTTP::header value Connection]]\n'
                '                       equals "upgrade")}\n'
                '  {\n'
                '    # TODO\n'
                '    HTTP::cookie insert name "hello" value "world"\n'
                '  }\n'
                '}\n'
            )
        }
        super(ListenerManager, self)._create(
            bigip, irule, None, None, type="irule", helper=self.irule_helper)
        vs['rules'].append("/Common/websocket_irule")

    def _create_redirect_policy(self, bigip, vs, listener):
        protocol = listener.get("redirect_protocol", "")
        if not protocol:
            protocol = "https"

        host = "[HTTP::host]"
        port = listener.get("redirect_port", 0)
        if port:
            # Only support IPv4
            # host = "[getfield [HTTP::host] : 1]:" + str(port)
            # Support IPv4 and IPv6 both
            host = r"[regsub -all {:\d*$} [HTTP::host] \"\"]:" + str(port)

        location = "tcl:" + protocol + "://" + host + "[HTTP::uri]"

        policy = LTMPolicyRedirect(
            bigip=bigip,
            partition=vs['partition'],
            vs_name=vs['name'],
            location=location,
        )
        policy.create()
        policy.attach_to_vs()

    def _update_redirect_policy(self, bigip, vs, old_listener, listener):
        if not self._isRedirect(old_listener) and self._isRedirect(listener):
            self._create_redirect_policy(bigip, vs, listener)
        elif self._isRedirect(old_listener) and not self._isRedirect(listener):
            self._delete_redirect_policy(bigip, vs)
        elif self._isRedirect(old_listener) and self._isRedirect(listener):
            old_proto = old_listener.get("redirect_protocol", "")
            new_proto = listener.get("redirect_protocol", "")
            old_port = old_listener.get("redirect_port", 0)
            new_port = listener.get("redirect_port", 0)

            if old_proto != new_proto or old_port != new_port:
                self._create_redirect_policy(bigip, vs, listener)

    def _delete_redirect_policy(self, bigip, vs):
        policy = LTMPolicyRedirect(
            bigip=bigip,
            partition=vs['partition'],
            vs_name=vs['name']
        )
        policy.detach_from_vs()
        policy.delete()

    def _create(self, bigip, vs, listener, service):
        tls = self.driver.service_adapter.get_tls(service)
        if tls:
            tls['cipher_policy'] = self.cipher_policy
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

        # Create the following profiles required by this VS:
        #   HTTP profile (if listener is HTTP or TERMINATED_HTTPS)
        #   Websocket profile (if listener is HTTP or TERMINATED_HTTPS)
        self._create_extended_profiles(bigip, listener, vs)

        # if self._isHTTPorTLS(listener):
        #     self._create_websocket_irule(bigip, vs)

        bandwidth = LoadBalancerManager.get_bandwidth_value(
            self.driver.conf, loadbalancer)
        if bandwidth > 0:
            LOG.debug("bandwidth exists")
            irule_name = LoadBalancerManager.get_bwc_irule_name(
                self.driver.service_adapter, loadbalancer)
            vs['rules'].append(irule_name)
            bwc_policy = LoadBalancerManager.get_bwc_policy_name(
                self.driver.service_adapter, loadbalancer)
            vs['bwcPolicy'] = bwc_policy

        # pzhang: we only consider to adding sctp profile so far.
        # notice the order of adding profiles, this will remove
        # fastL4 profile
        tcp_ip_enable = self.tcp_helper.enable_tcp(service)
        if tcp_ip_enable:
            ip_address = loadbalancer.get("vip_address", None)
            pure_ip_address = ip_address.split("%")[0]
            ip_version = netaddr.IPAddress(pure_ip_address).version

            self.tcp_helper.add_profile(
                service, vs, bigip,
                side="server",
                tcp_options=self.driver.conf.tcp_options
            )
            self.tcp_irule_helper.create_iRule(
                service, vs, bigip,
                tcp_options=self.driver.conf.tcp_options,
                ip_version=ip_version
            )

        super(ListenerManager, self)._create(bigip, vs, listener, service)

        if self._isRedirect(listener):
            self._create_redirect_policy(bigip, vs, listener)

    def __get_profiles_from_bigip(self, bigip, vs):
        # load profiles from bigip
        vs_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        l_objs = vs_manager.get_resources(
            bigip, partition=vs['partition'], expand_subcollections=True)
        v = filter(lambda x: x.name == vs['name'], l_objs)[0]
        profiles = v.profilesReference
        return profiles

    def _update(self, bigip, vs, old_listener, listener, service):
        # Add conditions here for more update requests via vs['profiles']
        extended_profile_updated = False
        orig_profiles = []
        if self._check_tls_changed(old_listener, listener) is True:
            tls = self.driver.service_adapter.get_tls(service)
            if tls:
                http2 = listener.get('http2', False)
                if self._check_http2_changed(old_listener, listener) is True \
                   and http2 is False:
                    # tls type listener,
                    # 1) http2 changed from true to false,
                    # update http2 profile at first then update tls profile.
                    # 2) http2 changed from false to true,
                    # update tls profile at first then update http2 profile.

                    self._update_extended_profiles(bigip, old_listener,
                                                   listener, vs)
                    extended_profile_updated = True
                tls['http2'] = http2
                tls['cipher_policy'] = self.cipher_policy
                self._create_ssl_profile(bigip, vs, tls)

            orig_profiles = self.__get_profiles_from_bigip(bigip, vs)
            if 'profiles' not in vs:
                vs['profiles'] = list()
            vs['profiles'] += filter(
                lambda x: x['context'] != 'clientside', orig_profiles['items'])

        if vs.get("persist") == []:
            LOG.debug("Need to remove persist profile from vs %s", vs['name'])

        persist = None
        if vs.get('persist'):
            persist = service[self._key]['session_persistence']
        if persist:
            LOG.debug("Need to create or update persist profile for %s %s",
                      self._resource, vs['name'])
            profile = self._create_persist_profile(bigip, vs, persist)
            vs['persist'] = [{"name": profile}]

        # pzhang: use need_update_tcp to check old_listener and
        # listener avoid tedious _update_payload function
        tcp_ip_update = self.tcp_helper.need_update_tcp(old_listener, listener)
        if tcp_ip_update:
            loadbalancer = service.get('loadbalancer', dict())
            ip_address = loadbalancer.get("vip_address", None)
            pure_ip_address = ip_address.split("%")[0]
            ip_version = netaddr.IPAddress(pure_ip_address).version

            self.tcp_helper.update_profile(
                service, vs, bigip,
                side="server",
                tcp_options=self.driver.conf.tcp_options
            )
            self.tcp_irule_helper.update_iRule(
                service, vs, bigip,
                tcp_options=self.driver.conf.tcp_options,
                ip_version=ip_version
            )

        # If no vs property to update, do not call icontrol patch api.
        # This happens, when vs payload only contains 'customized'.
        if set(sorted(vs.keys())) > set(['name', 'partition']):
            super(ListenerManager, self)._update(bigip, vs, old_listener,
                                                 listener, service)

        # Other code might call ListenerManager to post vs payload directly.
        # Only need to refresh profile when a real listener update occurs.
        if old_listener and listener and not extended_profile_updated:
            self._update_extended_profiles(bigip, old_listener, listener, vs)

        if old_listener and \
           self._check_tls_changed(old_listener, listener) is True:
            old_service = {"listener": old_listener}
            self._delete_ssl_profiles(bigip, vs, old_service)

        if old_listener and \
           self._check_redirect_changed(old_listener, listener):
            self._update_redirect_policy(bigip, vs, old_listener, listener)

        if tcp_ip_update:
            if self.tcp_helper.delete_profile is True:
                self.tcp_helper.remove_profile(
                    service, vs, bigip, side="server"
                )
            if self.tcp_irule_helper.delete_iRule is True:
                self.tcp_irule_helper.remove_iRule(
                    service, vs, bigip
                )

    def _delete(self, bigip, vs, listener, service):
        super(ListenerManager, self)._delete(bigip, vs, listener, service)
        self._delete_persist_profile(bigip, vs)
        self._delete_ssl_profiles(bigip, vs, service)
        self._delete_extended_profiles(bigip, listener, vs)
        self._delete_redirect_policy(bigip, vs)
        ftp_enable = self.ftp_helper.enable_ftp(service)
        if ftp_enable:
            self.ftp_helper.remove_profile(service, vs, bigip)
        tcp_ip_enable = self.tcp_helper.need_delete_tcp(service)
        if tcp_ip_enable:
            self.tcp_helper.remove_profile(
                service, vs, bigip,
                side="server"
            )
            self.tcp_irule_helper.remove_iRule(
                service, vs, bigip
            )

    @serialized('ListenerManager.create')
    @log_helpers.log_method_call
    def create(self, listener, service, **kwargs):
        loadbalancer = service.get("loadbalancer", None)
        traffic_group = self.driver.service_to_traffic_group(service)
        loadbalancer['traffic_group'] = traffic_group

        # pzhang: add a destination vip with route domain in service
        if not self.driver.conf.f5_global_routed_mode:
            self.driver.network_builder.prep_service_networking(
                service, traffic_group)
        super(ListenerManager, self).create(listener, service)

    @serialized('ListenerManager.update')
    @log_helpers.log_method_call
    def update(self, old_listener, listener, service, **kwargs):
        super(ListenerManager, self).update(
            old_listener, listener, service)

    # we may change this to bind_acl
    # and we add unbind_acl
    # bind_acl will consider enable and disableo
    # unbind_acl will clear everything whatever it enable or disable
    @serialized('ListenerManager.update_acl_bind')
    @log_helpers.log_method_call
    def update_acl_bind(self, listener, acl_bind, service, **kwargs):
        enable = self.acl_helper.enable_acl(acl_bind)
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)

        # force to used service although it is bad
        service["listener"] = listener
        vs_info = self.driver.service_adapter.get_virtual_name(service)
        irule_payload = self.acl_helper.get_acl_irule_payload(
            acl_bind, vs_info)
        irule_fullPath = irule_payload["fullPath"]

        for bigip in bigips:

            vs = self.resource_helper.load(
                bigip, name=vs_info['name'], partition=vs_info['partition'])
            irules = vs.rules

            if enable:
                self.acl_helper.create_acl_irule(
                    bigip, irule_payload)

                if irule_fullPath not in irules:
                    irules.append(irule_fullPath)

                vs_info['rules'] = irules
                # In order to rebuild listener, if it is missing.
                # we insure it only changes the changes, it will not
                # affect other configurations
                super(ListenerManager, self)._update(
                    bigip, vs_info, None, listener, service)
            else:
                if irule_fullPath in irules:
                    irules.remove(irule_fullPath)

                vs_info['rules'] = irules
                super(ListenerManager, self)._update(
                    bigip, vs_info, None, listener, service)

                self.acl_helper.remove_acl_irule(
                    bigip, irule_payload)

        LOG.debug("Finish to update ACL bind %s %s",
                  self._resource, str(acl_bind))

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
                LOG.debug("Failed to delete node 400: %s" % err.message)
            elif err.response.status_code == 404:
                LOG.debug("Failed to delete node 404: %s" % err.message)
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
        elif old_pool.get('session_persistence', None):
            # If persistence is removed from pool, and this
            # pool is the default pool of a listener, need
            # to remove persist property from VS.
            payload['session_persistence'] = "remove"
        elif old_pool['lb_algorithm'] == "SOURCE_IP":
            # If old pool uses SOURCE_IP algorithm, but new pool has no
            # persist profile, that means pool algorithm changes and no
            # session_persistence setting either. The source-ip persist
            # profile should be dettached from VS.
            payload['session_persistence'] = "remove"

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
        persist = None
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
                    if payload['session_persistence'] == "remove":
                        # Remove persist from VS
                        listener_payload['persist'] = []
                    mgr._update(bigip, listener_payload, None, None, service)
            # Exclude session_persistence from pool payload temporarily,
            # in order to update other properties of pool resource
            persist = payload['session_persistence']
            del payload['session_persistence']
        # Pool has other props to update
        for key in payload.keys():
            if key != "name" and key != "partition":
                super(PoolManager, self)._update(bigip, payload, old_pool,
                                                 pool, service)
                break
        # Restore session_persistence, if it used to be there. Other bigips
        # can continue to utilize this payload to run _update() routine
        if persist:
            payload['session_persistence'] = persist

    def _delete(self, bigip, payload, pool, service):
        mgr = ListenerManager(self.driver)
        for listener in service['listeners']:
            if listener['default_pool_id'] == pool['id']:
                service['listener'] = listener
                """ Unmap listener and pool"""
                vs = self.driver.service_adapter.get_virtual_name(service)
                vs['pool'] = ""
                # Need to remove persist profile from virtual server,
                # if its persist profile is configured by its default pool.
                # Do not modify persist profile which is manually attached.
                if "session_persistence" in service['pool']:
                    vs['persist'] = []
                    vs['fallbackPersistence'] = ""
                mgr._update(bigip, vs, None, None, service)
        super(PoolManager, self)._delete(bigip, payload, pool, service)

        """ try to delete the node which is only used by the pool """
        loadbalancer = service.get('loadbalancer')
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
        self.driver.network_builder.delete_mb_network(
            None, service, delete_pool=True
        )
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
        elif subtype == 'UDP':
            monitor_type = resource_helper.ResourceType.udp_monitor
            self._resource = 'udp_monitor'
        elif subtype == 'SIP':
            monitor_type = resource_helper.ResourceType.sip_monitor
            self._resource = 'sip_monitor'
        elif subtype == 'DIAMETER':
            monitor_type = resource_helper.ResourceType.diameter_monitor
            self._resource = 'diameter_monitor'
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

    def _update_payload(self, old_resource, resource, service, **kwargs):
        LOG.info('inside _update_payload MonitorManager')
        payload = kwargs.get('payload', {})
        create_payload = kwargs.get('create_payload',
                                    self._create_payload(resource, service))

        for key in self.mutable_props.keys():
            old = old_resource.get(key)
            new = resource.get(key)
            if old != new:
                prop = self.mutable_props[key]
                payload[prop] = create_payload[prop]

        LOG.info(payload)
        # changing only interval needs to update timeout as well
        if 'interval' in payload:
            payload['timeout'] = create_payload['timeout']

        if len(payload.keys()) > 0:
            payload['name'] = create_payload['name']
            payload['partition'] = create_payload['partition']

        LOG.debug('payload here:')
        LOG.debug(payload)
        return payload

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

    def _merge_members(self, lbaas_members, bigip_members, pool_id, service):
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
            if item['name'] not in name_list and \
               item['pool_id'] == pool_id:
                content = self._create_member_payload(lb, item)
                members_payload.append(content)

        if time() - start_time > .001:
            LOG.debug("For merge_members took %.5f secs" %
                      (time() - start_time))

        return members_payload

    @serialized('MemberManager.create')
    @log_helpers.log_method_call
    def create(self, resource, service, **kwargs):

        self._check_nonshared_network(service)

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
        pool_id = pool['id']
        lbaas_members = service['members']
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
        for bigip in bigips:
            pool_resource = self._pool_mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )
            bigip_members = pool_resource.members_s.get_collection()

            del pool_payload['members']
            new_payload = self._merge_members(
                lbaas_members, bigip_members, pool_id, service)
            pool_payload['members'] = new_payload
            self._shrink_payload(pool_payload,
                                 keys_to_keep=['partition',
                                               'name', 'members',
                                               'loadBalancingMode'])
            self._pool_mgr._update(bigip, pool_payload, None, None, service)
        LOG.debug("Finish to create in batch %s %s",
                  self._resource, resource['name'])

    def _create_single(self, resource, service, **kwargs):

        self.driver.network_builder.prep_mb_network(
            resource, service)

        if not service.get(self._key):
            self._search_element(resource, service)
        LOG.debug("Begin to create %s %s", self._resource, resource['id'])
        member = service.get('member')
        pool = {}
        pool['id'] = member['pool_id']
        self._pool_mgr._search_element(pool, service)
        pool_payload = self._pool_mgr._create_payload(pool, service)

        payload = self._create_payload(member, service)
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
        for bigip in bigips:
            pool_resource = self._pool_mgr.pool_helper.load(
                bigip,
                name=urllib.quote(pool_payload['name']),
                partition=pool_payload['partition']
            )

            try:
                pool_resource.members_s.members.create(**payload)
            except iControlUnexpectedHTTPError as ex:
                if ex.response.status_code == 409:
                    LOG.warning("The pool member %s exists", payload)
                    LOG.debug(
                        "Finish to create %s %s",
                        self._resource, resource['id'])
                    continue
                else:
                    raise ex

            self._shrink_payload(pool_payload,
                                 keys_to_keep=['partition',
                                               'name', 'loadBalancingMode'])
            self._pool_mgr._update(bigip, pool_payload, None, None, service)

        LOG.debug("Finish to create %s %s", self._resource, resource['id'])

    def _check_nonshared_network(self, service):
        loadbalancer = service["loadbalancer"]
        tenant_id = loadbalancer["tenant_id"]

        members = service["members"]
        for meb in members:
            meb_net_id = meb["network_id"]
            network = self.driver.service_adapter.get_network_from_service(
                service, meb_net_id)
            net_project_id = network["project_id"]

            if self.driver.conf.f5_global_routed_mode:
                shared = network["shared"]
                if not shared:
                    if tenant_id != net_project_id:
                        raise f5_ex.ProjectIDException(
                            "The tenant project id is %s. "
                            "The nonshared netwok/subnet project id is %s. "
                            "They are not belong to the same tenant." %
                            (tenant_id, net_project_id))
                return

            if not self.driver.network_builder.l2_service.is_common_network(
                    network):
                if tenant_id != net_project_id:
                    raise f5_ex.ProjectIDException(
                        "The tenant project id is %s. "
                        "The nonshared netwok/subnet project id of "
                        "member %s is %s. "
                        "They are not belong to the same tenant." %
                        (tenant_id, meb, net_project_id))

    @serialized('MemberManager.delete')
    @log_helpers.log_method_call
    def delete(self, resource, service, **kwargs):

        self._check_nonshared_network(service)

        self.driver.network_builder.delete_mb_network(
            resource, service)

        if not service.get(self._key):
            self._search_element(resource, service)

        LOG.debug("Begin to delete %s %s", self._resource, resource['id'])
        member = service['member']
        payload = self._create_payload(member, service)

        pool = {}
        pool['id'] = member['pool_id']
        self._pool_mgr._search_element(pool, service)
        pool_payload = self._pool_mgr._create_payload(pool, service)

        loadbalancer = service.get('loadbalancer')
        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
        for bigip in bigips:
            try:
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
            except HTTPError as err:
                if err.response.status_code == 404:
                    LOG.warning("the member not found, am ignoring")
                    LOG.warning(str(err))
                else:
                    LOG.error("unknow member deletion error")
                    LOG.error(str(err))
                    # maybe not raise at all?
                    # raise err

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

        bigips = self.driver.get_config_bigips(no_bigip_exception=True)
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


class ACLGroupManager(ResourceManager):

    def __init__(self, driver, **kwargs):
        super(ACLGroupManager, self).__init__(driver)
        self._resource = "ACLGroup"
        self.resource_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.internal_data_group)

    def _create_payload(self, resource, *args, **kwargs):
        """Convert neutron lbaas acl_group to bigip data_group"""

        partition = "Common"
        name = "acl_" + resource["id"]
        data_group_type = "ip"
        rules = resource.get("acl_rules_detail")
        data_group_rules = {}

        if rules:
            # do we need to put data as rule['id'] here?
            data_group_rules = [
                {"name": rule["ip_address"], "data": ""}
                for rule in rules]

        payload = {
            "name": name,
            "partition": partition,
            "type": data_group_type,
            "records": data_group_rules
        }

        return payload

    def _update_payload(self, old_resource, resource, service, **kwargs):
        payload = self._create_payload(resource, **kwargs)
        return payload
