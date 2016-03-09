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

from neutron.plugins.common import constants as plugin_const
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class LBaaSBuilder(object):
    # F5 LBaaS Driver using iControl for BIG-IP to
    # create objects (vips, pools) - not using an iApp."""

    def __init__(self, conf, driver, l2_service=None):
        self.conf = conf
        self.driver = driver
        self.l2_service = l2_service

    def assure_service(self, service, traffic_group, all_subnet_hints):
        # Assure that the service is configured
        if not service['loadbalancer']:
            return

        self._check_monitor_delete(service)

        start_time = time()
        self._assure_pool_create(service['pool'])
        LOG.debug("    _assure_pool_create took %.5f secs" %
                  (time() - start_time))

        start_time = time()
        self._assure_pool_monitors(service)
        LOG.debug("    _assure_pool_monitors took %.5f secs" %
                  (time() - start_time))

        start_time = time()
        self._assure_members(service, all_subnet_hints)
        LOG.debug("    _assure_members took %.5f secs" %
                  (time() - start_time))

        start_time = time()
        self._assure_vip(service, traffic_group, all_subnet_hints)
        LOG.debug("    _assure_vip took %.5f secs" %
                  (time() - start_time))

        start_time = time()
        self._assure_pool_delete(service)
        LOG.debug("    _assure_pool_delete took %.5f secs" %
                  (time() - start_time))

        return all_subnet_hints

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

    def _assure_vip(self, service, traffic_group, all_subnet_hints):
        # Ensure the vip is on all bigips.
        vip = service['vip']
        if 'id' not in vip:
            return
        """
        bigips = self.driver.get_config_bigips()
        for bigip in bigips:
            subnet_hints = all_subnet_hints[bigip.device_name]
            subnet = vip['subnet']

            if vip['status'] == plugin_const.PENDING_CREATE or \
               vip['status'] == plugin_const.PENDING_UPDATE:
                self.bigip_vip_manager.assure_bigip_create_vip(
                    bigip, service, traffic_group)
                if subnet and subnet['id'] in \
                        subnet_hints['check_for_delete_subnets']:
                    del subnet_hints['check_for_delete_subnets'][subnet['id']]
                if subnet and subnet['id'] not in \
                        subnet_hints['do_not_delete_subnets']:
                    subnet_hints['do_not_delete_subnets'].append(subnet['id'])

            elif vip['status'] == plugin_const.PENDING_DELETE:
                self.bigip_vip_manager.assure_bigip_delete_vip(bigip, service)
                if subnet and subnet['id'] not in \
                        subnet_hints['do_not_delete_subnets']:
                    subnet_hints['check_for_delete_subnets'][subnet['id']] = \
                        {'network': vip['network'],
                         'subnet': subnet,
                         'is_for_member': False}
        """

        # avoids race condition:
        # deletion of vip address must sync before we
        # remove the selfip from the peer bigips.
        self.driver.sync_if_clustered()

    def _assure_pool_delete(self, service):
        # Assure pool is deleted from big-ip
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
