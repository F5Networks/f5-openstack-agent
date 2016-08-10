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

from requests.exceptions import HTTPError

import os

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BigipSnatManager(object):
    def __init__(self, driver, l2_service, l3_binding):
        self.driver = driver
        self.l2_service = l2_service
        self.l3_binding = l3_binding
        self.snatpool_manager = BigIPResourceHelper(ResourceType.snatpool)
        self.snat_translation_manager = BigIPResourceHelper(
            ResourceType.snat_translation)
        self.network_helper = NetworkHelper()

    def _get_snat_name(self, subnet, tenant_id):
        # Get the snat name based on HA type
        if self.driver.conf.f5_ha_type == 'standalone':
            return 'snat-traffic-group-local-only-' + subnet['id']
        elif self.driver.conf.f5_ha_type == 'pair':
            return 'snat-traffic-group-1-' + subnet['id']
        elif self.driver.conf.f5_ha_type == 'scalen':
            traffic_group = self.driver.tenant_to_traffic_group(tenant_id)
            base_traffic_group = os.path.basename(traffic_group)
            return 'snat-' + base_traffic_group + '-' + subnet['id']
        LOG.error('Invalid f5_ha_type:%s' % self.driver.conf.f5_ha_type)
        return ''

    def _get_snat_traffic_group(self, tenant_id):
        # Get the snat name based on HA type """
        if self.driver.conf.f5_ha_type == 'standalone':
            return 'traffic-group-local-only'
        elif self.driver.conf.f5_ha_type == 'pair':
            return 'traffic-group-1'
        elif self.driver.conf.f5_ha_type == 'scalen':
            traffic_group = self.driver.tenant_to_traffic_group(tenant_id)
            return os.path.basename(traffic_group)
        # If this is an error shouldn't we raise?
        LOG.error('Invalid f5_ha_type:%s' % self.driver.conf.f5_ha_type)
        return ''

    def get_snat_addrs(self, subnetinfo, tenant_id, snat_count):
        # Get the ip addresses for snat """
        subnet = subnetinfo['subnet']
        snat_addrs = []

        snat_name = self._get_snat_name(subnet, tenant_id)
        for i in range(snat_count):
            ip_address = ""
            index_snat_name = snat_name + "_" + str(i)
            ports = self.driver.plugin_rpc.get_port_by_name(
                port_name=index_snat_name)
            if len(ports) > 0:
                first_port = ports[0]
                first_fixed_ip = first_port['fixed_ips'][0]
                ip_address = first_fixed_ip['ip_address']
            else:
                new_port = self.driver.plugin_rpc.create_port_on_subnet(
                    subnet_id=subnet['id'],
                    mac_address=None,
                    name=index_snat_name,
                    fixed_address_count=1)
                if new_port is not None:
                    ip_address = new_port['fixed_ips'][0]['ip_address']

            # Push the IP address on the list if the port was acquired.
            if len(ip_address) > 0:
                snat_addrs.append(ip_address)
            else:
                LOG.error("get_snat_addrs: failed to allocate port for "
                          "SNAT address.")

        return snat_addrs

    def assure_bigip_snats(self, bigip, subnetinfo, snat_addrs, tenant_id):
        # Ensure Snat Addresses are configured on a bigip.
        # Called for every bigip only in replication mode.
        # otherwise called once and synced.
        network = subnetinfo['network']

        snat_info = {}
        if self.l2_service.is_common_network(network):
            snat_info['network_folder'] = 'Common'
        else:
            snat_info['network_folder'] = (
                self.driver.service_adapter.get_folder_name(tenant_id)
            )

        snat_info['pool_name'] = self.driver.service_adapter.get_folder_name(
            tenant_id
        )
        snat_info['pool_folder'] = self.driver.service_adapter.get_folder_name(
            tenant_id
        )
        snat_info['addrs'] = snat_addrs

        self._assure_bigip_snats(bigip, subnetinfo, snat_info, tenant_id)

    def _assure_bigip_snats(self, bigip, subnetinfo, snat_info, tenant_id):
        # Configure the ip addresses for snat
        network = subnetinfo['network']
        subnet = subnetinfo['subnet']

        if tenant_id not in bigip.assured_tenant_snat_subnets:
            bigip.assured_tenant_snat_subnets[tenant_id] = []
        if subnet['id'] in bigip.assured_tenant_snat_subnets[tenant_id]:
            return

        snat_name = self._get_snat_name(subnet, tenant_id)
        for i, snat_address in enumerate(snat_info['addrs']):
            ip_address = snat_address + \
                '%' + str(network['route_domain_id'])
            index_snat_name = snat_name + "_" + str(i)

            snat_traffic_group = self._get_snat_traffic_group(tenant_id)
            # snat.create() did  the following in LBaaSv1
            # Creates the SNAT
            #   * if the traffic_group is empty it uses a const
            #     but this seems like it should be an error see message
            #     in this file about this
            # Create a SNAT Pool if a name was passed in
            #   * Add the snat to the list of members
            model = {
                "name": index_snat_name,
                "partition": snat_info['network_folder'],
                "address": ip_address,
                "trafficGroup": snat_traffic_group
            }
            try:
                if not self.snat_translation_manager.exists(
                        bigip,
                        name=index_snat_name,
                        partition=snat_info['network_folder']):
                    self.snat_translation_manager.create(bigip, model)
            except Exception as err:
                LOG.exception(err)
                raise f5_ex.SNATCreationException(
                    "Error creating snat translation manager %s" %
                    index_snat_name)

            model = {
                "name": snat_info['pool_name'],
                "partition": snat_info['network_folder'],
            }
            snatpool_member = ('/' + model["partition"] + '/' +
                               index_snat_name)
            model["members"] = [snatpool_member]
            try:
                if not self.snatpool_manager.exists(
                        bigip,
                        name=model['name'],
                        partition=model['partition']):
                    LOG.debug("Creating SNAT pool: %s" % model)
                    self.snatpool_manager.create(bigip, model)
                else:
                    LOG.debug("Updating SNAT pool")
                    snatpool = self.snatpool_manager.load(
                        bigip,
                        name=model["name"],
                        partition=model["partition"]
                    )
                    snatpool.members.append(snatpool_member)
                    snatpool.modify(members=snatpool.members)

            except Exception as err:
                LOG.error("Create SNAT pool failed %s" % err.message)
                raise f5_ex.SNATCreationException(
                    "Failed to create SNAT pool")

            if self.l3_binding:
                self.l3_binding.bind_address(subnet_id=subnet['id'],
                                             ip_address=ip_address)

        bigip.assured_tenant_snat_subnets[tenant_id].append(subnet['id'])

    def delete_bigip_snats(self, bigip, subnetinfo, tenant_id):
        # Assure shared snat configuration (which syncs) is deleted.
        #
        if not subnetinfo['network']:
            LOG.error('Attempted to delete selfip and snats '
                      'for missing network ... skipping.')
            return set()

        return self._delete_bigip_snats(bigip, subnetinfo, tenant_id)

    def _remove_assured_tenant_snat_subnet(self, bigip, tenant_id, subnet):
        # Remove ref for the subnet for this tenant"""
        if tenant_id in bigip.assured_tenant_snat_subnets:
            tenant_snat_subnets = \
                bigip.assured_tenant_snat_subnets[tenant_id]
            if tenant_snat_subnets and subnet['id'] in tenant_snat_subnets:
                LOG.debug(
                    'Remove subnet id %s from '
                    'bigip.assured_tenant_snat_subnets for tenant %s' %
                    (subnet['id'], tenant_id))
                tenant_snat_subnets.remove(subnet['id'])
            else:
                LOG.debug(
                    'Subnet id %s does not exist in '
                    'bigip.assured_tenant_snat_subnets for tenant %s' %
                    (subnet['id'], tenant_id))
        else:
            LOG.debug(
                'Tenant id %s does not exist in '
                'bigip.assured_tenant_snat_subnets' % tenant_id)

    def _delete_bigip_snats(self, bigip, subnetinfo, tenant_id):
        # Assure snats deleted in standalone mode """
        subnet = subnetinfo['subnet']
        network = subnetinfo['network']
        if self.l2_service.is_common_network(network):
            partition = 'Common'
        else:
            partition = self.driver.service_adapter.get_folder_name(tenant_id)

        snat_pool_name = self.driver.service_adapter.get_folder_name(tenant_id)
        deleted_names = set()
        in_use_subnets = set()

        # Delete SNATs on traffic-group-local-only
        snat_name = self._get_snat_name(subnet, tenant_id)
        for i in range(self.driver.conf.f5_snat_addresses_per_subnet):
            index_snat_name = snat_name + "_" + str(i)
            tmos_snat_name = index_snat_name

            if self.l3_binding:
                try:
                    snat_xlate = self.snat_translation_manager.load(
                        bigip, name=index_snat_name, partition=partition)
                except HTTPError as err:
                    LOG.error("Load SNAT xlate failed %s" % err.message)
                except Exception:
                    LOG.error("Unknown error occurred loading SNAT for unbind")
                else:
                    self.l3_binding.unbind_address(
                        subnet_id=subnet['id'], ip_address=snat_xlate.address)

            # Remove translation address from tenant snat pool
            # This seems strange that name and partition are tenant_id
            # but that is what the v1 code was doing.
            # The v1 code was also comparing basename in some cases
            # which seems dangerous because the folder may be in play?
            #
            # Revised (jl): It appears that v2 SNATs are created with a
            # name, not tenant_id, so we need to load SNAT by name.
            LOG.debug('Remove translation address from tenant SNAT pool')
            try:
                snatpool = self.snatpool_manager.load(bigip,
                                                      snat_pool_name,
                                                      partition)

                snatpool.members = [
                    member for member in snatpool.members
                    if os.path.basename(member) != tmos_snat_name
                ]

                # Delete snat pool if empty (no members)
                # In LBaaSv1 the snat.remove_from_pool() method did this if
                # there was only one member and it matched the one we were
                # deleting making this call basically useless, but the
                # code above makes this still necessary and probably what the
                # original authors intended anyway since there is logging here
                # but not in the snat.py module from LBaaSv1
                LOG.debug('Check if snat pool is empty')
                if not snatpool.members:
                    LOG.debug('Snat pool is empty - delete snatpool')
                    try:
                        snatpool.delete()
                    except HTTPError as err:
                        LOG.error("Delete SNAT pool failed %s" % err.message)
                else:
                    LOG.debug('Snat pool is not empty - update snatpool')
                    try:
                        snatpool.modify(members=snatpool.members)
                    except HTTPError as err:
                        LOG.error("Update SNAT pool failed %s" % err.message)
            except HTTPError as err:
                LOG.error("Failed to load SNAT pool %s" % err.message)

            # Check if subnet in use by any tenants/snatpools. If in use,
            # add subnet to hints list of subnets in use.
            self._remove_assured_tenant_snat_subnet(bigip, tenant_id, subnet)
            LOG.debug(
                'Check cache for subnet %s in use by other tenant' %
                subnet['id'])
            in_use_count = 0
            for loop_tenant_id in bigip.assured_tenant_snat_subnets:
                tenant_snat_subnets = \
                    bigip.assured_tenant_snat_subnets[loop_tenant_id]
                if subnet['id'] in tenant_snat_subnets:
                    LOG.debug(
                        'Subnet %s in use (tenant %s)' %
                        (subnet['id'], loop_tenant_id))
                    in_use_count += 1

            if in_use_count:
                in_use_subnets.add(subnet['id'])
            else:
                LOG.debug('Check subnet in use by any tenant')
                member_use_count = \
                    self.get_snatpool_member_use_count(
                        bigip, subnet['id'])
                if member_use_count:
                    LOG.debug('Subnet in use - do not delete')
                    in_use_subnets.add(subnet['id'])
                else:
                    LOG.debug('Subnet not in use - delete')

            # Check if trans addr in use by any snatpool.  If not in use,
            # okay to delete associated neutron port.
            LOG.debug('Check trans addr %s in use.' % tmos_snat_name)
            in_use_count = \
                self.get_snatpool_member_use_count(
                    bigip, tmos_snat_name)
            if not in_use_count:
                LOG.debug('Trans addr not in use - delete')
                deleted_names.add(index_snat_name)
            else:
                LOG.debug('Trans addr in use - do not delete')

        return deleted_names, in_use_subnets

    def get_snatpool_member_use_count(self, bigip, member_name):
        snat_count = 0
        snatpools = bigip.tm.ltm.snatpools.get_collection()
        for snatpool in snatpools:
            for member in snatpool.members:
                if member_name == os.path.basename(member):
                    snat_count += 1
        return snat_count
