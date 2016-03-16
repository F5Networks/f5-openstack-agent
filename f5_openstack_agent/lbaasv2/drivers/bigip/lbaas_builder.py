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

from time import time

from oslo_log import log as logging

from neutron.plugins.common import constants as plugin_const

from f5_openstack_agent.lbaasv2.drivers.bigip import listener_service
from f5_openstack_agent.lbaasv2.drivers.bigip import pool_service

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
            self.service_adapter)
        self.pool_builder = pool_service.PoolServiceBuilder(
            self.service_adapter
        )

    def assure_service(self, service, traffic_group, all_subnet_hints):
        """Assure that a service is configured on the BIGIP."""

        start_time = time()
        LOG.debug("Starting assure_service")

        self._assure_loadbalancer_created(service)

        self._assure_listeners_created(service)

        self._assure_pools_created(service)

        self._assure_monitors(service)

        self._assure_members(service, all_subnet_hints)

        self._assure_pools_deleted(service)

        self._assure_listeners_deleted(service)

        self._assure_loadbalancer_deleted(service)

        LOG.debug("    _assure_service took %.5f secs" %
                  (time() - start_time))
        return all_subnet_hints

    def _assure_loadbalancer_created(self, service):
        if 'loadbalancer' not in service:
            return

    def _assure_listeners_created(self, service):
        if 'listeners' not in service:
            return

        listeners = service["listeners"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for listener in listeners:
            svc = {"loadbalancer": loadbalancer,
                   "listener": listener}
            if listener['provisioning_status'] != plugin_const.PENDING_DELETE:
                try:

                    if "default_pool_id" in listener:
                        pool = self._get_pool_by_id(
                            service, listener["default_pool_id"])
                        if pool is not None:
                            svc["pool"] = pool

                    self.listener_builder.create_listener(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_listeners_created."
                              "Message: %s" % err.message)
                    continue

    def _assure_pools_created(self, service):
        if "pools" not in service:
            return

        pools = service["pools"]
        loadbalancer = service["loadbalancer"]

        bigips = self.driver.get_all_bigips()

        for pool in pools:
            svc = {"loadbalancer": loadbalancer,
                   "pool": pool}

            if pool['provisioning_status'] != plugin_const.PENDING_DELETE:
                try:
                    self.pool_builder.create_pool(svc, bigips)

                    if "listeners" in pool:
                        pool_name = self.service_adapter.init_pool_name(
                            loadbalancer, pool)["name"]
                        listeners = pool["listeners"]
                        for listener in listeners:
                            self._update_listener_pool(
                                service, listener["id"], pool_name, bigips)

                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_pools_created."
                              "Message: %s" % err.message)
                    continue

    def _update_listener_pool(self, service, listener_id, pool_name, bigips):
        listener = self._get_listener_by_id(service, listener_id)
        if listener is not None:
            listener["pool"] = pool_name
            svc = {"loadbalancer": service["loadbalancer"],
                   "listener": listener}
            self.listener_builder.update_listener(svc, bigips)

    def _assure_monitors(self, service):
        if not (("pools" in service) and ("healthmonitors" in service)):
            return

        monitors = service["healthmonitors"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for monitor in monitors:
            svc = {"loadbalancer": loadbalancer,
                   "healthmonitor": monitor,
                   "pool": self._get_pool_by_id(service, monitor["pool_id"])}
            if monitor['provisioning_status'] == plugin_const.PENDING_DELETE:
                try:
                    self.pool_builder.delete_healthmonitor(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_monitors (delete)."
                              "Message: %s" % err.message)
                    continue
            else:
                try:
                    self.pool_builder.create_healthmonitor(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_monitors (create)."
                              "Message: %s" % err.message)

    def _assure_members(self, service, all_subnet_hints):
        if not (("pools" in service) and ("members" in service)):
            return

        members = service["members"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for member in members:
            svc = {"loadbalancer": loadbalancer,
                   "member": member,
                   "pool": self._get_pool_by_id(service, member["pool_id"])}
            if member['provisioning_status'] == plugin_const.PENDING_DELETE:
                try:
                    self.pool_builder.delete_member(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_members (delete)."
                              "Message: %s" % err.message)
                    continue
            else:
                try:
                    self.pool_builder.create_member(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_members (create)."
                              "Message: %s" % err.message)

    def _assure_loadbalancer_deleted(self, service):
        if (service['loadbalancer']['provisioning_status'] !=
                plugin_const.PENDING_DELETE):
            return

    def _assure_pools_deleted(self, service):
        if 'pools' not in service:
            return

        pools = service["pools"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for pool in pools:
            # Is the pool being deleted?
            if pool['provisioning_status'] == plugin_const.PENDING_DELETE:
                svc = {"loadbalancer": loadbalancer,
                       "pool": pool}
                try:
                    # remove default pool from virtual
                    if "listeners" in pool:
                        pool_name = ""
                        listeners = pool["listeners"]
                        for listener in listeners:
                            self._update_listener_pool(
                                service, listener["id"], pool_name, bigips)

                    self.pool_builder.delete_pool(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_pools_deleted."
                              "Message: %s" % err.message)

    def _assure_listeners_deleted(self, service):
        if 'listeners' not in service:
            return

        listeners = service["listeners"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for listener in listeners:
            svc = {"loadbalancer": loadbalancer,
                   "listener": listener}
            if listener['provisioning_status'] == plugin_const.PENDING_DELETE:
                try:
                    self.listener_builder.delete_listener(svc, bigips)
                except Exception as err:
                    LOG.error("Error in "
                              "LBaaSBuilder._assure_listeners_deleted."
                              "Message: %s" % err.message)

    def _check_monitor_delete(self, service):
        # If the pool is being deleted, then delete related objects
        if service['pool']['status'] == plugin_const.PENDING_DELETE:
            # Everything needs to be go with the pool, so overwrite
            # service state to appropriately remove all elements
            service['vip']['status'] = plugin_const.PENDING_DELETE
            for member in service['members']:
                member['status'] = plugin_const.PENDING_DELETE
            for monitor in service['pool']['health_monitors_status']:
                monitor['status'] = plugin_const.PENDING_DELETE

    def _get_pool_by_id(self, service, id):
        if "pools" in service:
            pools = service["pools"]
            for pool in pools:
                if pool["id"] == id:
                    return pool
        return None

    def _get_listener_by_id(self, service, id):
        if "listeners" in service:
            listeners = service["listeners"]
            for listener in listeners:
                if listener["id"] == id:
                    return listener
        return None
