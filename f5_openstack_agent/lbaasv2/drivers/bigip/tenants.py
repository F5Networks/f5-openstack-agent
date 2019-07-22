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

import constants_v2 as const
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
        network_id = service['loadbalancer']['network_id']
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

        # create tenant route domain

        # ccloud: change of rd creartion to avoid different id's on the bigip pair members
        if self.conf.use_namespaces:
            # Determine which bigip needs a rd and if the rd is already created somewhere else so that id should be used
            route_domain_id = None
            bigiprds = []
            for bigip in self.driver.get_all_bigips():
                bigip_route_domain = self.network_helper.route_domain_exists(bigip, const.DEFAULT_PARTITION, network_id)
                bigip_route_domain_id = bigip_route_domain.id if bigip_route_domain else None
                # rd already created but not different between bigips (maybe not created on all of them)
                if bigip_route_domain_id and route_domain_id is None:
                    route_domain_id = bigip_route_domain_id
                # rd already created on different bigips with DIFFERENT id --> ERROR
                elif bigip_route_domain_id and route_domain_id and bigip_route_domain_id != bigip_route_domain_id:
                    LOG.error("Route Domain Failure: RD for network %s is defined with ID %s on one and with %s on another Bigip"
                              % (network_id, bigip_route_domain_id, route_domain_id))
                    raise f5ex.RouteDomainCreationException("Route Domain Failure: RD for network %s is defined with ID %s on one and with %s on another Bigip"
                                                            % (network_id, bigip_route_domain_id, route_domain_id))
                # rd not created anywhere until now
                elif bigip_route_domain_id is None:
                    bigiprds.append(bigip)
            # now we have the bigip's with the missing rd and an rd id in case it's created on one of the bigip's
            # create rd in bigips where it's missing either with the given id or a new one to be determined
            for bigip in bigiprds:
                try:
                    bigip_route_domain = self.network_helper.create_route_domain(
                        bigip,
                        partition=const.DEFAULT_PARTITION,
                        name=network_id,
                        strictness=self.conf.f5_route_domain_strictness,
                        is_aux=False,
                        rd_id=route_domain_id)
                    # use newly created id for next bigip
                    if route_domain_id is None:
                        route_domain_id = bigip_route_domain.id
                    # something went wrong
                    elif bigip_route_domain.id != route_domain_id:
                        LOG.error("Route Domain Failure: Attempt to create RD for network %s with ID %s on one and with %s on another Bigip"
                                  % (network_id, bigip_route_domain_id, route_domain_id))
                        raise f5ex.RouteDomainCreationException("Route Domain Failure: RD for network %s is defined with ID %s on one and with %s on another Bigip"
                                                                % (network_id, bigip_route_domain_id, route_domain_id))
                # error within rd creation procedure
                except Exception as err:
                    LOG.exception(err.message)
                    raise f5ex.RouteDomainCreationException("Failed to create route domain for network %s in tenant %s" % (network_id, const.DEFAULT_PARTITION))

        LOG.debug("Allocated route domain for network %s for tenant %s"
                  % (network_id, tenant_id))

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
        network_id = service['loadbalancer']['network_id']

        self._remove_tenant_replication_mode(bigip, tenant_id, network_id)

    def _remove_tenant_replication_mode(self, bigip, tenant_id, network_id):
        # Remove tenant in replication sync-mode
        partition = self.service_adapter.get_folder_name(tenant_id)


        try:
            self.network_helper.delete_route_domain(bigip,
                                                    "Common",
                                                    network_id)
        except Exception as err:
            LOG.info("Failed to delete route domain %s. "
                      "Manual intervention might be required." % (network_id))

        try:
            self.system_helper.delete_folder(bigip, partition)
        except Exception as err:
            LOG.info(
                "Folder deletion failed for tenant partition %s. "
                "Manual cleanup might be required." % (tenant_id))