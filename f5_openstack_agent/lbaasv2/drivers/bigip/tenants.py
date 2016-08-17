"""Tenants Manager."""
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

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5ex
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper

LOG = logging.getLogger(__name__)


class BigipTenantManager(object):
    """Create network connectivity for a bigip."""

    def __init__(self, conf, driver):  # XXX maybe we need a better name: conf
        """Create a BigipTenantManager."""
        self.conf = conf
        self.driver = driver
        self.system_helper = SystemHelper()
        self.network_helper = NetworkHelper()
        self.service_adapter = self.driver.service_adapter

    def assure_tenant_created(self, service):
        """Create tenant partition.

        This method modifies its argument 'service' in place.
        This method adds a 'traffic_group" key to the service
        dict with a value of traffic_group_string_id.  But aren't
        traffic_groups a bigIP device concept?  And wasn't (until
        this method was called) the service object a configuration
        entirely defined by neutron?  Also for neutron->device
        adaptations shouldn't we be using ServiceModelAdapter...  though I
        suppose this is the other way.
        """
        tenant_id = service['loadbalancer']['tenant_id']
        traffic_group = self.driver.service_to_traffic_group(service)
        traffic_group = '/Common/' + traffic_group
        service["traffic_group"] = traffic_group  # modify the passed dict

        # create tenant folder
        folder_name = self.service_adapter.get_folder_name(tenant_id)
        LOG.debug("Creating tenant folder %s" % folder_name)
        for bigip in self.driver.get_config_bigips():
            if not self.system_helper.folder_exists(bigip, folder_name):
                folder = self.service_adapter.get_folder(service)
                # This folder is a dict config obj, that can be passed to
                # folder.create in the SDK
                try:
                    self.system_helper.create_folder(bigip, folder)
                except Exception as err:
                    # XXX Maybe we can make this more specific?
                    LOG.exception("Error creating folder %s" %
                                  (folder))
                    raise f5ex.SystemCreationException(
                        "Folder creation error for tenant %s" %
                        (tenant_id))

            if not self.driver.disconnected_service.network_exists(
                    bigip, folder_name):
                try:
                    self.driver.disconnected_service.create_network(
                        bigip, folder_name)
                except Exception as err:
                    LOG.exception("Error creating disconnected network %s." %
                                  (folder_name))
                    raise f5ex.SystemCreationException(
                        "Disconnected network create error for tenant %s" %
                        (tenant_id))

        # create tenant route domain
        if self.conf.use_namespaces:
            for bigip in self.driver.get_all_bigips():
                if not self.network_helper.route_domain_exists(bigip,
                                                               folder_name):
                    try:
                        self.network_helper.create_route_domain(
                            bigip,
                            folder_name,
                            self.conf.f5_route_domain_strictness)
                    except Exception as err:
                        LOG.exception(err.message)
                        raise f5ex.RouteDomainCreationException(
                            "Failed to create route domain for "
                            "tenant in %s" % (folder_name))

    def assure_tenant_cleanup(self, service, all_subnet_hints):
        """Delete tenant partition."""
        # Called for every bigip only in replication mode,
        # otherwise called once.
        for bigip in self.driver.get_config_bigips():
            subnet_hints = all_subnet_hints[bigip.device_name]
            self._assure_bigip_tenant_cleanup(bigip, service, subnet_hints)

    # called for every bigip only in replication mode.
    # otherwise called once
    def _assure_bigip_tenant_cleanup(self, bigip, service, subnet_hints):
        tenant_id = service['loadbalancer']['tenant_id']

        self._remove_tenant_replication_mode(bigip, tenant_id)

    def _remove_tenant_replication_mode(self, bigip, tenant_id):
        # Remove tenant in replication sync-mode
        partition = self.service_adapter.get_folder_name(tenant_id)
        domain_names = self.network_helper.get_route_domain_names(bigip,
                                                                  partition)
        for domain_name in domain_names:
            try:
                self.network_helper.delete_route_domain(bigip,
                                                        partition,
                                                        domain_name)
            except Exception as err:
                LOG.error("Failed to delete route domain %s. "
                          "%s. Manual intervention might be required."
                          % (domain_name, err.message))
            if self.driver.disconnected_service.network_exists(
                    bigip, partition):
                try:
                    self.driver.disconnected_service.delete_network(bigip,
                                                                    partition)
                except Exception as err:
                    LOG.error("Failed to delete disconnected network %s. "
                              "%s. Manual intervention might be required."
                              % (partition, err.message))

        try:
            self.system_helper.delete_folder(bigip, partition)
        except Exception:
            LOG.error(
                "Folder deletion exception for tenant partition %s occurred."
                % tenant_id)
            LOG.exception("%s" % err.message)
            raise f5ex.SystemDeleteException(
                "Failed to destroy folder %s manual cleanup might be "
                "required." % partition)
