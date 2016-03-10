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

import time

from oslo_log import log as logging

from neutron.plugins.common import constants as plugin_const

from f5_openstack_agent.lbaasv2.drivers.bigip import listener_service

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
            self.service_adapter
        )

    def assure_service(self, service, traffic_group, all_subnet_hints):
        """Assure that a service is configured on the BIGIP."""
        # Assure that the service is configured

        self._assure_loadbalancer_create(service)

        self._assure_listener_create(service)

        # start_time = time.time()
        # self._assure_pool_create(service['pool'])
        # LOG.debug("    _assure_pool_create took %.5f secs" %
        #           (time.time() - start_time))

        # start_time = time.time()
        # self._assure_pool_monitors(service)
        # LOG.debug("    _assure_pool_monitors took %.5f secs" %
        #           (time.time() - start_time))

        # start_time = time.time()
        # self._assure_members(service, all_subnet_hints)
        # LOG.debug("    _assure_members took %.5f secs" %
        #           (time.time() - start_time))

        start_time = time.time()
        self._assure_pool_delete(service)
        LOG.debug("    _assure_pool_delete took %.5f secs" %
                  (time.time() - start_time))

        start_time = time.time()
        self._assure_loadbalancer_delete(service)
        LOG.debug("    _assure_loadbalancer_delete took %.5f secs" %
                  (time.time() - start_time))

        self._assure_listener_delete(service)

        return all_subnet_hints

    def _assure_loadbalancer_create(self, service):
        if not service['loadbalancer']:
            return

    def _assure_listener_create(self, service):

        listeners = service["listeners"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for listener in listeners:
            # create a service object in form expected by builder
            svc = {"loadbalancer": loadbalancer,
                   "listener": listener}

            # create
            self.listener_builder.create_listener(svc, bigips)

    def _assure_listener_delete(self, service):

        listeners = service["listeners"]
        loadbalancer = service["loadbalancer"]
        bigips = self.driver.get_all_bigips()

        for listener in listeners:
            # Is the lister being deleted
            if listener['provisioning_status'] == plugin_const.PENDING_DELETE:
                # Create a service object in form expected by builder
                svc = {"loadbalancer": loadbalancer,
                       "listener": listener}
                self.listener_builder.delete_listener(svc, bigips)

    def _assure_pool_create(self, pool):
        # Provision Pool - Create/Update
        # Service Layer (Shared Config)
        # for bigip in self.driver.get_config_bigips():
        #    self.bigip_pool_manager.assure_bigip_pool_create(bigip, pool)
        pass

    def _assure_pool_monitors(self, service):
        # Provision Health Monitors - Create/Update
        # Service Layer (Shared Config)
        # for bigip in self.driver.get_config_bigips():
        #    self.bigip_pool_manager.assure_bigip_pool_monitors(bigip, service)
        pass

    def _assure_members(self, service, all_subnet_hints):
        # Service Layer (Shared Config)
        # for bigip in self.driver.get_config_bigips():
        #    subnet_hints = all_subnet_hints[bigip.device_name]
        #    self.bigip_pool_manager.assure_bigip_members(
        #        bigip, service, subnet_hints)

        # avoids race condition:
        # deletion of pool member objects must sync before we
        # remove the selfip from the peer bigips.
        self.driver.sync_if_clustered()

    def _assure_loadbalancer_delete(self, service):
        if (service['loadbalancer']['provisioning_status'] !=
                plugin_const.PENDING_DELETE):
            return

    def _assure_pool_delete(self, service):
        # Assure pool is deleted from big-ip
        if 'pool' not in service:
            return

        if service['pool']['status'] != plugin_const.PENDING_DELETE:
            return

        # Service Layer (Shared Config)
        # for bigip in self.driver.get_config_bigips():
        #    self.bigip_pool_manager.assure_bigip_pool_delete(bigip, service)

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
