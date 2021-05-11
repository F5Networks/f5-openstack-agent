"""Tenants Manager."""
# Copyright (c) 2014-2018, F5 Networks, Inc.
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
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType
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
        self.va_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)
        self.node_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.node)

    def assure_tenant_created(self, service, sync=False):
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
                    LOG.exception("Error creating folder %s: %s" %
                                  (folder, err.message))
                    raise f5ex.SystemCreationException(
                        "Folder creation error for tenant %s" %
                        (tenant_id))

        if self.conf.use_namespaces and sync \
                and not self.conf.f5_global_routed_mode:
            # pzhang sync all route domain on an active bigip to all
            # standby bigip
            bigips = self.driver.get_all_bigips()
            active_bigips = [
                bigip for bigip in bigips
                if bigip.failover_state == "active"
            ]

            standby_bigips = [
                bigip for bigip in bigips
                if bigip.failover_state == "standby"
            ]

            if active_bigips:
                # pzhang; default to use first
                # active bigip to sync route domain
                # of certain parition of the loadbalancer in service.
                active_bigip = active_bigips[0]
                rd_ids = self.network_helper.get_route_domain_ids(
                    active_bigip, partition=folder_name)
            else:
                LOG.warning(
                    "Not found active bigip to sync route domain in L2 mode"
                )

            if rd_ids:
                for rd_id in rd_ids:
                    for standby_bigip in standby_bigips:
                        rd_exists = self.network_helper.route_domain_exists(
                            standby_bigip,
                            folder_name
                        )
                        if not rd_exists:
                            self.network_helper.create_route_domain(
                                standby_bigip,
                                rd_id,
                                folder_name,
                                self.conf.f5_route_domain_strictness
                            )

            else:
                LOG.warning(
                    "Not found any route domain ids \
                    of partitiion %s in L2 mode",
                    folder_name
                )

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

        if not self._partition_empty(bigip, partition):
            LOG.debug("Partition: %s still exists VIPs and Nodes" % partition)
            return

        # There might be some snats, vlans and self ips in this folder, which
        # are shared by member subnets. Since we can not remove them when
        # deleting members, we just cleanup them all before removing folder
        types = [
            ResourceType.snat_translation,
            ResourceType.selfip,
        ]
        # Deallocate neutron port, ignore error.
        for rtype in types:
            helper = BigIPResourceHelper(rtype)
            for r in helper.get_resources(bigip, partition):
                try:
                    self.driver.plugin_rpc.delete_port_by_name(
                        port_name=r.name)
                except Exception as err:
                    LOG.debug("Failed to delete port: %s", err.message)
        types = [
            ResourceType.snat,
            ResourceType.snatpool,
            ResourceType.snat_translation,
            ResourceType.selfip,
            ResourceType.vlan
        ]
        # Delete resource from BIG-IP, igore error.
        for rtype in types:
            helper = BigIPResourceHelper(rtype)
            for r in helper.get_resources(bigip, partition):
                try:
                    r.delete()
                except Exception as err:
                    LOG.debug("Failed to delete resource: %s", err.message)

        LOG.info("Delete empty partition: %s" % partition)
        for domain_name in domain_names:
            try:
                self.network_helper.delete_route_domain(bigip,
                                                        partition,
                                                        domain_name)
            except Exception as err:
                LOG.debug("Failed to delete route domain %s. "
                          "%s. Manual intervention might be required."
                          % (domain_name, err.message))

        try:
            self.system_helper.delete_folder(bigip, partition)
        except Exception as err:
            LOG.debug(
                "Folder deletion exception for tenant partition %s occurred. "
                "Manual cleanup might be required." % (tenant_id))

    def _partition_empty(self, bigip, partition):
        virtual_addresses = self.va_helper.get_resources(
            bigip, partition=partition)
        nodes = self.node_helper.get_resources(
            bigip, partition=partition)

        if not nodes and not virtual_addresses:
            return True
        return False
