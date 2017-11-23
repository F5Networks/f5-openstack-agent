# coding=utf-8
# Copyright 2014-2017 F5 Networks Inc.
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

from time import time

from oslo_log import log as logging

from neutron.plugins.common import constants as plugin_const
from neutron_lbaas.services.loadbalancer import constants as lb_const

from f5_openstack_agent.lbaasv2.drivers.bigip import l7policy_service
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_service import \
    LbaasServiceObject
from f5_openstack_agent.lbaasv2.drivers.bigip import listener_service
from f5_openstack_agent.lbaasv2.drivers.bigip import pool_service
from f5_openstack_agent.lbaasv2.drivers.bigip import virtual_address

from requests import HTTPError

LOG = logging.getLogger(__name__)


class LBaaSBuilder(object):
    # F5 LBaaS Driver using iControl for BIG-IP to
    # create objects (vips, pools) - not using an iApp."""

    def __init__(self, conf, driver, l2_service=None):
        self.conf = conf
        self.driver = driver
        self.l2_service = l2_service
        self.service_adapter = driver.service_adapter
        self.listener_builder = listener_service.ListenerServiceBuilder(
            self.service_adapter,
            driver.cert_manager,
            conf.f5_parent_ssl_profile)
        self.pool_builder = pool_service.PoolServiceBuilder(
            self.service_adapter
        )
        self.l7service = l7policy_service.L7PolicyService(conf)
        self.esd = None

    def assure_service(self, service, traffic_group, all_subnet_hints):
        """Assure that a service is configured on the BIGIP."""
        start_time = time()

        LOG.debug("assuring loadbalancers")

        self._assure_loadbalancer_created(service, all_subnet_hints)

        LOG.debug("assuring monitors")

        self._assure_monitors_created(service)

        LOG.debug("assuring pools")

        self._assure_pools_created(service)

        LOG.debug("assuring pool members")

        self._assure_members(service, all_subnet_hints)

        LOG.debug("assuring l7 policies")

        self._assure_l7policies_created(service)

        LOG.debug("assuring listeners")

        self._assure_listeners_created(service)

        LOG.debug("deleting listeners")

        self._assure_listeners_deleted(service)

        LOG.debug("deleting l7 policies")

        self._assure_l7policies_deleted(service)

        LOG.debug("deleting pools")

        self._assure_pools_deleted(service)

        LOG.debug("deleting monitors")

        self._assure_monitors_deleted(service)

        LOG.debug("deleting loadbalancers")

        self._assure_loadbalancer_deleted(service)

        LOG.debug("    _assure_service took %.5f secs" %
                  (time() - start_time))
        return all_subnet_hints

    @staticmethod
    def _set_status_as_active(svc_obj, force=False):
        # If forced, then set to ACTIVE else hold ERROR
        preserve_statuses = \
            tuple([plugin_const.ERROR, plugin_const.PENDING_DELETE])
        ps = svc_obj['provisioning_status']
        svc_obj['provisioning_status'] = plugin_const.ACTIVE \
            if ps not in preserve_statuses or force else ps

    @staticmethod
    def _set_status_as_error(svc_obj):
        svc_obj['provisioning_status'] = plugin_const.ERROR

    @staticmethod
    def _is_not_pending_delete(svc_obj):
        return svc_obj['provisioning_status'] != plugin_const.PENDING_DELETE

    @staticmethod
    def _is_not_error(svc_obj):
        return svc_obj['provisioning_status'] != plugin_const.ERROR

    def _assure_loadbalancer_created(self, service, all_subnet_hints):
        if 'loadbalancer' not in service:
            return
        bigips = self.driver.get_config_bigips()
        loadbalancer = service["loadbalancer"]
        set_active = True

        if self._is_not_pending_delete(loadbalancer):

            vip_address = virtual_address.VirtualAddress(
                self.service_adapter,
                loadbalancer)
            for bigip in bigips:
                try:
                    vip_address.assure(bigip)
                except Exception as error:
                    LOG.error(str(error))
                    self._set_status_as_error(loadbalancer)
                    set_active = False

            self._set_status_as_active(loadbalancer, force=set_active)

        if self.driver.l3_binding:
            loadbalancer = service["loadbalancer"]
            self.driver.l3_binding.bind_address(
                subnet_id=loadbalancer["vip_subnet_id"],
                ip_address=loadbalancer["vip_address"])

        self._update_subnet_hints(loadbalancer["provisioning_status"],
                                  loadbalancer["vip_subnet_id"],
                                  loadbalancer["network_id"],
                                  all_subnet_hints,
                                  False)

    def _assure_listeners_created(self, service):
        if 'listeners' not in service:
            return

        listeners = service["listeners"]
        loadbalancer = service["loadbalancer"]
        networks = service.get("networks", list())
        pools = service.get("pools", list())
        l7policies = service.get("l7policies", list())
        l7rules = service.get("l7policy_rules", list())
        bigips = self.driver.get_config_bigips()

        for listener in listeners:
            error = False
            if self._is_not_pending_delete(listener):

                svc = {"loadbalancer": loadbalancer,
                       "listener": listener,
                       "pools": pools,
                       "l7policies": l7policies,
                       "l7policy_rules": l7rules,
                       "networks": networks}

                # create_listener() will do an update if VS exists
                error = self.listener_builder.create_listener(
                    svc, bigips)

                if error:
                    loadbalancer['provisioning_status'] = \
                        plugin_const.ERROR
                    listener['provisioning_status'] = plugin_const.ERROR
                else:
                    listener['provisioning_status'] = plugin_const.ACTIVE
                    listener['operating_status'] = lb_const.ONLINE

    def _assure_pools_created(self, service):
        if "pools" not in service:
            return

        pools = service.get("pools", list())
        loadbalancer = service.get("loadbalancer", dict())
        monitors = \
            [monitor for monitor in service.get("healthmonitors", list())
             if monitor['provisioning_status'] != plugin_const.PENDING_DELETE]

        bigips = self.driver.get_config_bigips()
        error = None
        for pool in pools:
            if pool['provisioning_status'] != plugin_const.PENDING_DELETE:
                svc = {"loadbalancer": loadbalancer,
                       "pool": pool}
                svc['members'] = self._get_pool_members(service, pool['id'])
                svc['healthmonitors'] = monitors

                error = self.pool_builder.create_pool(svc, bigips)
                if error:
                    pool['provisioning_status'] = plugin_const.ERROR
                    loadbalancer['provisioning_status'] = plugin_const.ERROR
                else:
                    pool['provisioning_status'] = plugin_const.ACTIVE
                    pool['operating_status'] = lb_const.ONLINE

    def _get_pool_members(self, service, pool_id):
        """Return a list of members associated with given pool."""
        members = []
        for member in service['members']:
            if member['pool_id'] == pool_id:
                members.append(member)
        return members

    def _assure_monitors_created(self, service):
        monitors = service.get("healthmonitors", list())
        loadbalancer = service.get("loadbalancer", dict())
        bigips = self.driver.get_config_bigips()
        force_active_status = True

        for monitor in monitors:
            svc = {"loadbalancer": loadbalancer,
                   "healthmonitor": monitor}
            if monitor['provisioning_status'] != plugin_const.PENDING_DELETE:
                if self.pool_builder.create_healthmonitor(svc, bigips):
                    monitor['provisioning_status'] = plugin_const.ERROR
                    force_active_status = False

                self._set_status_as_active(monitor, force=force_active_status)

    def _assure_monitors_deleted(self, service):
        monitors = service["healthmonitors"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_config_bigips()

        for monitor in monitors:
            svc = {"loadbalancer": loadbalancer,
                   "healthmonitor": monitor}
            if monitor['provisioning_status'] == plugin_const.PENDING_DELETE:
                if self.pool_builder.delete_healthmonitor(svc, bigips):
                    monitor['provisioning_status'] = plugin_const.ERROR

    def _assure_members(self, service, all_subnet_hints):
        if not (("pools" in service) and ("members" in service)):
            return

        members = service["members"]
        pools = service["pools"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_config_bigips()
        force_active = False

        for pool in pools:
            pool = self.get_pool_by_id(service, pool['id'])
            svc = {"loadbalancer": loadbalancer,
                   "pool": pool,
                   "members": []}
            for member in members:
                if member['pool_id'] == pool['id']:
                    svc['members'].append(member)
            try:
                self.pool_builder.delete_orphaned_members(svc, bigips)
            except HTTPError as error:
                LOG.error(str(error))

        for member in members:
            pool = self.get_pool_by_id(service, member["pool_id"])
            svc = {"loadbalancer": loadbalancer,
                   "member": member,
                   "pool": pool}
            # Create a pool service dict since the pool may need to be updated
            # based upon changes in the members.
            pool_svc = {
                "loadbalancer": loadbalancer,
                "pool": pool,
                "members": self._get_pool_members(service, pool['id'])}

            if 'port' not in member and \
               member['provisioning_status'] != plugin_const.PENDING_DELETE:
                LOG.warning("Member definition does not include Neutron port")

            # delete member if pool is being deleted
            member_status = member['provisioning_status']
            if member_status == plugin_const.PENDING_DELETE or \
               pool['provisioning_status'] == plugin_const.PENDING_DELETE:
                try:
                    self.pool_builder.delete_member(svc, bigips)
                    self.pool_builder.update_pool(pool_svc, bigips)
                except Exception as err:
                    member['provisioning_status'] = plugin_const.ERROR
                    LOG.error(
                        "Caught unexpected error deleting member, "
                        "continuing...%s", err.message)
            else:
                try:
                    self.pool_builder.create_member(svc, bigips)
                except Exception:
                    member['provisioning_status'] = plugin_const.ERROR
                    LOG.error(
                        "Caught unexpected error assuring member, "
                        "continuing...%s",
                        err.message)
                else:
                    member['provisioning_status'] = plugin_const.ACTIVE

            self._update_subnet_hints(member["provisioning_status"],
                                      member["subnet_id"],
                                      member["network_id"],
                                      all_subnet_hints,
                                      True)
            self._set_status_as_active(member, force=force_active)

    def _assure_loadbalancer_deleted(self, service):
        if (service['loadbalancer']['provisioning_status'] !=
                plugin_const.PENDING_DELETE):
            return

        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_config_bigips()

        if self.driver.l3_binding:
            self.driver.l3_binding.unbind_address(
                subnet_id=loadbalancer["vip_subnet_id"],
                ip_address=loadbalancer["vip_address"])

        vip_address = virtual_address.VirtualAddress(
            self.service_adapter,
            loadbalancer)

        for bigip in bigips:
            vip_address.assure(bigip, delete=True)

    def _assure_pools_deleted(self, service):
        if 'pools' not in service:
            return

        pools = service["pools"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_config_bigips()

        for pool in pools:
            # Is the pool being deleted?
            if pool['provisioning_status'] == plugin_const.PENDING_DELETE:
                svc = {"loadbalancer": loadbalancer,
                       "pool": pool}
                # Delete pool
                error = self.pool_builder.delete_pool(svc, bigips)
                if error:
                    pool['provisioning_status'] = plugin_const.ERROR

    def _assure_listeners_deleted(self, service):
        bigips = self.driver.get_config_bigips()
        if 'listeners' in service:
            listeners = service["listeners"]
            loadbalancer = service["loadbalancer"]
            for listener in listeners:
                error = False
                if listener['provisioning_status'] == \
                        plugin_const.PENDING_DELETE:
                    svc = {"loadbalancer": loadbalancer,
                           "listener": listener}
                    error = \
                        self.listener_builder.delete_listener(svc, bigips)

                    if error:
                        listener['provisioning_status'] = plugin_const.ERROR

        self.listener_builder.delete_orphaned_listeners(service, bigips)

    @staticmethod
    def _check_monitor_delete(service):
        # If the pool is being deleted, then delete related objects
        if service['pool']['status'] == plugin_const.PENDING_DELETE:
            # Everything needs to be go with the pool, so overwrite
            # service state to appropriately remove all elements
            service['vip']['status'] = plugin_const.PENDING_DELETE
            for member in service['members']:
                member['status'] = plugin_const.PENDING_DELETE
            for monitor in service['pool']['health_monitors_status']:
                monitor['status'] = plugin_const.PENDING_DELETE

    @staticmethod
    def get_pool_by_id(service, pool_id):
        if pool_id and "pools" in service:
            pools = service["pools"]
            for pool in pools:
                if pool["id"] == pool_id:
                    return pool
        return None

    @staticmethod
    def get_listener_by_id(service, listener_id):
        if "listeners" in service:
            listeners = service["listeners"]
            for listener in listeners:
                if listener["id"] == listener_id:
                    return listener
        return None

    def _update_subnet_hints(self, status, subnet_id,
                             network_id, all_subnet_hints, is_member):
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            subnet_hints = all_subnet_hints[bigip.device_name]

            if status != plugin_const.PENDING_DELETE:
                if subnet_id in subnet_hints['check_for_delete_subnets']:
                    del subnet_hints['check_for_delete_subnets'][subnet_id]
                if subnet_id not in subnet_hints['do_not_delete_subnets']:
                    subnet_hints['do_not_delete_subnets'].append(subnet_id)

            else:
                if subnet_id not in subnet_hints['do_not_delete_subnets']:
                    subnet_hints['check_for_delete_subnets'][subnet_id] = \
                        {'network_id': network_id,
                         'subnet_id': subnet_id,
                         'is_for_member': is_member}

    def listener_exists(self, bigip, service):
        """Test the existence of the listener defined by service."""
        try:
            # Throw an exception if the listener does not exist.
            self.listener_builder.get_listener(service, bigip)
        except HTTPError as err:
            LOG.debug("Virtual service service discovery error, %s." %
                      err.message)
            return False

        return True

    def _assure_l7policies_created(self, service):
        if 'l7policies' not in service:
            return

        listener_policy_map = dict()
        bigips = self.driver.get_config_bigips()
        lbaas_service = LbaasServiceObject(service)

        l7policies = service['l7policies']
        LOG.debug("L7 debug: processing policies: %s", l7policies)
        for l7policy in l7policies:
            LOG.debug("L7 debug: assuring policy: %s", l7policy)
            name = l7policy.get('name', None)
            if not self.is_esd(name):
                listener_id = l7policy.get('listener_id', None)
                if not listener_id or listener_id in listener_policy_map:
                    LOG.debug(
                        "L7 debug: listener policies already added: %s",
                        listener_id)
                    continue
                listener_policy_map[listener_id] = \
                    self.l7service.build_policy(l7policy, lbaas_service)

        for listener_id, policy in listener_policy_map.items():
            error = False
            if policy['f5_policy'].get('rules', list()):
                error = self.l7service.create_l7policy(
                    policy['f5_policy'], bigips)

            for p in policy['l7policies']:
                if self._is_not_pending_delete(p):
                    if not error:
                        self._set_status_as_active(p, force=True)
                    else:
                        self._set_status_as_error(p)

            loadbalancer = service.get('loadbalancer', {})
            if not error:
                listener = lbaas_service.get_listener(listener_id)
                if listener:
                    listener['f5_policy'] = policy['f5_policy']
                loadbalancer['provisioning_status'] = \
                    plugin_const.ACTIVE
            else:
                loadbalancer['provisioning_status'] = \
                    plugin_const.ERROR

    def _assure_l7policies_deleted(self, service):
        if 'l7policies' not in service:
            return
        listener_policy_map = dict()
        bigips = self.driver.get_config_bigips()
        lbaas_service = LbaasServiceObject(service)

        l7policies = service['l7policies']
        for l7policy in l7policies:
            name = l7policy.get('name', None)
            if not self.is_esd(name):
                listener_id = l7policy.get('listener_id', None)
                if not listener_id or listener_id in listener_policy_map:
                    continue
                listener_policy_map[listener_id] = \
                    self.l7service.build_policy(l7policy, lbaas_service)

        # Clean wrapper policy this is the legacy name of a policy
        loadbalancer = service.get('loadbalancer', dict())
        tenant_id = loadbalancer.get('tenant_id', "")
        try:
            wrapper_policy = {
                'name': 'wrapper_policy',
                'partition': self.service_adapter.get_folder_name(
                    tenant_id)}

            self.l7service.delete_l7policy(wrapper_policy, bigips)
        except HTTPError as err:
            if err.response.status_code != 404:
                LOG.error("Failed to remove wrapper policy: %s",
                          err.message)
        except Exception as err:
            LOG.error("Failed to remove wrapper policy: %s",
                      err.message)

        for _, policy in listener_policy_map.items():
            error = False
            if not policy['f5_policy'].get('rules', list()):
                error = self.l7service.delete_l7policy(
                    policy['f5_policy'], bigips)

            for p in policy['l7policies']:
                if self._is_not_pending_delete(p):
                    if not error:
                        self._set_status_as_active(p, force=True)
                    else:
                        self._set_status_as_error(p)
                else:
                    if error:
                        self._set_status_as_error(p)

    def get_listener_stats(self, service, stats):
        """Get statistics for a loadbalancer service.

        Sums values for stats defined in stats dictionary for all listeners
        defined in service object. For example, if loadbalancer has two
        listeners and stats defines a stat 'clientside.bitsIn' as a key, the
        sum of all pools' clientside.bitsIn will be returned in stats.

        Provisioning status is ignored -- PENDING_DELETE objects are
        included.

        :param service: defines loadbalancer and set of pools.
        :param stats: a dictionary that defines which stats to get.
        Should be initialized by caller with 0 values.
        :return: stats are appended to input stats dict (i.e., contains
        the sum of given stats for all BIG-IPs).
        """
        listeners = service["listeners"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_config_bigips()

        collected_stats = {}
        for stat in stats:
            collected_stats[stat] = 0

        for listener in listeners:
            svc = {"loadbalancer": loadbalancer, "listener": listener}
            vs_stats = self.listener_builder.get_stats(svc, bigips, stats)
            for stat in stats:
                collected_stats[stat] += vs_stats[stat]

        return collected_stats

    def update_operating_status(self, service):
        bigip = self.driver.get_active_bigip()
        loadbalancer = service["loadbalancer"]
        status_keys = ['status.availabilityState',
                       'status.enabledState']

        members = service["members"]
        for member in members:
            if member['provisioning_status'] == plugin_const.ACTIVE:
                pool = self.get_pool_by_id(service, member["pool_id"])
                svc = {"loadbalancer": loadbalancer,
                       "member": member,
                       "pool": pool}
                status = self.pool_builder.get_member_status(
                    svc, bigip, status_keys)
                member['operating_status'] = self.convert_operating_status(
                    status)

    @staticmethod
    def convert_operating_status(status):
        """Convert object status to LBaaS operating status.

        status.availabilityState and  status.enabledState = Operating Status

        available                     enabled                 ONLINE
        available                     disabled                DISABLED
        offline                       -                       OFFLINE
        unknown                       -                       NO_MONITOR
        """
        op_status = None
        available = status.get('status.availabilityState', '')
        if available == 'available':
            enabled = status.get('status.enabledState', '')
            if enabled == 'enabled':
                op_status = lb_const.ONLINE
            elif enabled == 'disabled':
                op_status = lb_const.DISABLED
            else:
                LOG.warning('Unexpected value %s for status.enabledState',
                            enabled)
        elif available == 'offline':
            op_status = lb_const.OFFLINE
        elif available == 'unknown':
            op_status = lb_const.NO_MONITOR

        return op_status

    def get_l7policy_for_rule(self, l7policies, l7rule):
        policy_id = l7rule['policy_id']
        for policy in l7policies:
            if policy_id == policy['id']:
                return policy

        return None

    def init_esd(self, esd):
        self.esd = esd

    def get_esd(self, name):
        if self.esd:
            return self.esd.get_esd(name)

        return None

    def is_esd(self, name):
        return self.esd.get_esd(name) is not None
