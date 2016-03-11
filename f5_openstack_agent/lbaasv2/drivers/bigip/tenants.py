""" Tenants Manager """
# Copyright 2014 F5 Networks Inc.
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

from eventlet import greenthread
from neutron.plugins.common import constants as plugin_const
from oslo_log import log as logging

import logging as std_logging

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5ex
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper

LOG = logging.getLogger(__name__)


class BigipTenantManager(object):
    # Create network connectivity for a bigip
    def __init__(self, conf, driver):
        self.conf = conf
        self.driver = driver
        self.system_helper = SystemHelper()
        self.network_helper = NetworkHelper()
        self.service_adapter = self.driver.service_adapter

    def assure_tenant_created(self, service):
        # Create tenant partition.
        tenant_id = service['loadbalancer']['tenant_id']
        traffic_group = self.driver.service_to_traffic_group(service)
        traffic_group = '/Common/' + traffic_group
        service["traffic_gorup"] = traffic_group

        # create tenant folder
        for bigip in self.driver.get_config_bigips():
            folder_name = self.service_adapter.get_folder_name(tenant_id)
            if not self.system_helper.folder_exists(bigip, folder_name):
                folder = self.service_adapter.get_folder(service)
                self.system_helper.create_folder(bigip, folder)

        # folder must sync before route domains are created.
        self.driver.sync_if_clustered()

        # create tenant route domain
        if self.conf.use_namespaces:
            for bigip in self.driver.get_all_bigips():
                folder_name = self.conf.environment_prefix + tenant_id
                if not self.network_helper.route_domain_exists(bigip,
                                                               folder_name):
                    self.network_helper.create_route_domain(
                        bigip,
                        folder_name,
                        self.conf.f5_route_domain_strictness)

    def assure_tenant_cleanup(self, service, all_subnet_hints):
        # Delete tenant partition.
        # Called for every bigip only in replication mode,
        # otherwise called once.
        for bigip in self.driver.get_config_bigips():
            # subnet_hints = all_subnet_hints[bigip.device_name]
            # self._assure_bigip_tenant_cleanup(bigip, service, subnet_hints)
            pass

    # called for every bigip only in replication mode.
    # otherwise called once
    def _assure_bigip_tenant_cleanup(self, bigip, service, subnet_hints):
        # if something was deleted check whether to do
        #    domain+folder teardown
        tenant_id = service['loadbalancer']['tenant_id']
        if service['loadbalancer']['provisioing_status'] == plugin_const.PENDING_DELETE or \
                len(subnet_hints['check_for_delete_subnets']) > 0:
            existing_monitors = bigip.monitor.get_monitors(folder=tenant_id)
            existing_pools = bigip.pool.get_pools(folder=tenant_id)
            existing_vips = bigip.virtual_server.get_virtual_service_insertion(
                folder=tenant_id)

            if not (existing_monitors or existing_pools or existing_vips):
                if self.conf.f5_sync_mode == 'replication':
                    self._remove_tenant_replication_mode(bigip, tenant_id)
                else:
                    self._remove_tenant_autosync_mode(bigip, tenant_id)

    def _remove_tenant_replication_mode(self, bigip, tenant_id):
        # Remove tenant in replication sync-mode
        domain_names = self.network_helper.get_route_domain_names(bigip,
                                                                  tenant_id)
        for domain_name in domain_names:
            self.network_helper.delete_route_domain(bigip,
                                                    tenant_id,
                                                    domain_name)
        sudslog = std_logging.getLogger('suds.client')
        sudslog.setLevel(std_logging.FATAL)
        self.system_helper.force_root_folder(bigip)
        sudslog.setLevel(std_logging.ERROR)

        folder_name = self.service_adapter.get_folder_name(tenant_id)
        try:
            self.system_helper.delete_folder(bigip, folder_name)
        except f5ex.SystemDeleteException:
            self.system_helper.purge_folder_contents(bigip, folder_name)
            self.system_helper.delete_folder(bigip, folder_name)

    def _remove_tenant_autosync_mode(self, bigip, tenant_id):
        # Remove tenant in autosync sync-mode
        # all domains must be gone before we attempt to delete
        # the folder or it won't delete due to not being empty
        for set_bigip in self.driver.get_all_bigips():
            self.network_helper.delete_route_domain(set_bigip, tenant_id, None)
            sudslog = std_logging.getLogger('suds.client')
            sudslog.setLevel(std_logging.FATAL)
            self.system_helper.force_root_folder(set_bigip)
            sudslog.setLevel(std_logging.ERROR)

        # we need to ensure that the following folder deletion
        # is clearly the last change that needs to be synced.
        self.driver.sync_if_clustered()
        greenthread.sleep(5)
        folder_name = self.service_adapter.get_folder_name(tenant_id)
        try:
            self.system_helper.delete_folder(bigip, folder_name)
        except f5ex.SystemDeleteException:
            self.system_helper.purge_folder_contents(bigip, folder_name)
            self.system_helper.delete_folder(bigip, folder_name)

        # Need to make sure this folder delete syncs before
        # something else runs and changes the current folder to
        # the folder being deleted which will cause big problems.
        self.driver.sync_if_clustered()
