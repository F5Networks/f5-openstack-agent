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

import itertools
import netaddr

from neutron.common.exceptions import NeutronException
from neutron.plugins.common import constants as plugin_const
from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    L2ServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.selfips import BigipSelfIpManager
from f5_openstack_agent.lbaasv2.drivers.bigip.snats import BigipSnatManager
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import strip_domain_address

LOG = logging.getLogger(__name__)


class NetworkServiceBuilder(object):

    def __init__(self, f5_global_routed_mode, conf, driver, l3_binding=None):
        self.f5_global_routed_mode = f5_global_routed_mode
        self.conf = conf
        self.driver = driver
        self.l3_binding = l3_binding
        self.l2_service = L2ServiceBuilder(driver, f5_global_routed_mode)

        self.bigip_selfip_manager = BigipSelfIpManager(
            self.driver, self.l2_service, self.driver.l3_binding)
        self.bigip_snat_manager = BigipSnatManager(
            self.driver, self.l2_service, self.driver.l3_binding)

        self.rds_cache = {}
        self.interface_mapping = self.l2_service.interface_mapping
        self.network_helper = NetworkHelper()
        self.service_adapter = self.driver.service_adapter

    def post_init(self):
        # Run and Post Initialization Tasks """
        # run any post initialized tasks, now that the agent
        # is fully connected
        self.l2_service.post_init()

    def tunnel_sync(self, tunnel_ips):
        self.l2_service.tunnel_sync(tunnel_ips)

    def set_tunnel_rpc(self, tunnel_rpc):
        # Provide FDB Connector with ML2 RPC access """
        self.l2_service.set_tunnel_rpc(tunnel_rpc)

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access """
        self.l2_service.set_l2pop_rpc(l2pop_rpc)

    def initialize_vcmp(self):
        self.l2_service.initialize_vcmp_manager()

    def initialize_tunneling(self):
        # setup tunneling
        vtep_folder = self.conf.f5_vtep_folder
        vtep_selfip_name = self.conf.f5_vtep_selfip_name
        local_ips = []

        for bigip in self.driver.get_all_bigips():

            if not vtep_folder or vtep_folder.lower() == 'none':
                vtep_folder = 'Common'

            if vtep_selfip_name and \
               not vtep_selfip_name.lower() == 'none':

                # profiles may already exist
                # create vxlan_multipoint_profile`
                self.network_helper.create_vxlan_multipoint_profile(
                    bigip,
                    'vxlan_ovs',
                    partition='Common')
                # create l2gre_multipoint_profile
                self.network_helper.create_l2gre_multipoint_profile(
                    bigip,
                    'gre_ovs',
                    partition='Common')

                # find the IP address for the selfip for each box
                local_ip = self.bigip_selfip_manager.get_selfip_addr(
                    bigip,
                    vtep_selfip_name,
                    partition=vtep_folder
                )

                if local_ip:
                    bigip.local_ip = local_ip
                    local_ips.append(local_ip)
                else:
                    raise f5_ex.MissingVTEPAddress(
                        'device %s missing vtep selfip %s'
                        % (bigip.device_name,
                           '/' + vtep_folder + '/' +
                           vtep_selfip_name))
        return local_ips

    def prep_service_networking(self, service, traffic_group):
        # Assure network connectivity is established on all bigips
        if self.conf.f5_global_routed_mode or not service['loadbalancer']:
            return

        if self.conf.use_namespaces:
            try:
                LOG.debug("Annotating the service definition networks "
                          "with route domain ID.")
                self._annotate_service_route_domains(service)
            except Exception as err:
                LOG.exception(err)
                raise f5_ex.RouteDomainCreationException(
                    "Route domain annotation error")

        # Per Device Network Connectivity (VLANs or Tunnels)
        subnetsinfo = self._get_subnets_to_assure(service)
        for (assure_bigip, subnetinfo) in (
                itertools.product(self.driver.get_all_bigips(), subnetsinfo)):
            LOG.debug("Assuring per device network connectivity "
                      "for %s on subnet %s." % (assure_bigip.hostname,
                                                subnetinfo['subnet']))

            # Make sure the L2 network is established
            self.l2_service.assure_bigip_network(
                assure_bigip, subnetinfo['network'])

            # Connect the BigIP device to network, by getting
            # a self-ip address on the subnet.
            self.bigip_selfip_manager.assure_bigip_selfip(
                assure_bigip, service, subnetinfo)

        # L3 Shared Config
        assure_bigips = self.driver.get_config_bigips()
        LOG.debug("Getting subnetinfo for ...")
        LOG.debug(assure_bigips)
        for subnetinfo in subnetsinfo:
            if self.conf.f5_snat_addresses_per_subnet > 0:
                self._assure_subnet_snats(assure_bigips, service, subnetinfo)

            if subnetinfo['is_for_member'] and not self.conf.f5_snat_mode:
                try:
                    self._allocate_gw_addr(subnetinfo)
                except KeyError as err:
                    raise f5_ex.VirtualServerCreationException(err.message)

                for assure_bigip in assure_bigips:
                    # If we are not using SNATS, attempt to become
                    # the subnet's default gateway.
                    self.bigip_selfip_manager.assure_gateway_on_subnet(
                        assure_bigip, subnetinfo, traffic_group)

    def _annotate_service_route_domains(self, service):
        # Add route domain notation to pool member and vip addresses.
        LOG.debug("Service before route domains: %s" % service)
        tenant_id = service['loadbalancer']['tenant_id']
        self.update_rds_cache(tenant_id)

        if 'members' in service:
            for member in service['members']:
                if 'address' in member:
                    LOG.debug("processing member %s" % member['address'])
                    if 'network_id' in member and member['network_id']:
                        member_network = (
                            self.service_adapter.get_network_from_service(
                                service,
                                member['network_id']
                            ))
                        member_subnet = (
                            self.service_adapter.get_subnet_from_service(
                                service,
                                member['subnet_id']
                            ))
                        if member_network:
                            self.assign_route_domain(
                                tenant_id, member_network, member_subnet)
                            rd_id = (
                                '%' + str(member_network['route_domain_id'])
                            )
                            member['address'] += rd_id
                    else:
                        member['address'] += '%0'

        if 'vip_address' in service['loadbalancer']:
            loadbalancer = service['loadbalancer']
            if 'network_id' in loadbalancer:
                lb_network = self.service_adapter.get_network_from_service(
                    service, loadbalancer['network_id'])
                vip_subnet = self.service_adapter.get_subnet_from_service(
                    service, loadbalancer['vip_subnet_id'])
                self.assign_route_domain(
                    tenant_id, lb_network, vip_subnet)
                rd_id = '%' + str(lb_network['route_domain_id'])
                service['loadbalancer']['vip_address'] += rd_id
            else:
                service['loadbalancer']['vip_address'] += '%0'
        LOG.debug("Service after route domains: %s" % service)

    def assign_route_domain(self, tenant_id, network, subnet):
        # Assign route domain for a network
        if self.l2_service.is_common_network(network):
            network['route_domain_id'] = 0
            return

        LOG.debug("assign route domain get from cache %s" % network)
        route_domain_id = self.get_route_domain_from_cache(network)
        if route_domain_id is not None:
            network['route_domain_id'] = route_domain_id
            return

        LOG.debug("max namespaces: %s" % self.conf.max_namespaces_per_tenant)
        LOG.debug("max namespaces == 1: %s" %
                  (self.conf.max_namespaces_per_tenant == 1))

        if self.conf.max_namespaces_per_tenant == 1:
            bigip = self.driver.get_bigip()
            LOG.debug("bigip before get_domain: %s" % bigip)
            partition_id = self.service_adapter.get_folder_name(
                tenant_id)
            tenant_rd = self.network_helper.get_route_domain(
                bigip, partition=partition_id)
            network['route_domain_id'] = tenant_rd.id
            return

        LOG.debug("assign route domain checking for available route domain")
        # need new route domain ?
        check_cidr = netaddr.IPNetwork(subnet['cidr'])
        placed_route_domain_id = None
        for route_domain_id in self.rds_cache[tenant_id]:
            LOG.debug("checking rd %s" % route_domain_id)
            rd_entry = self.rds_cache[tenant_id][route_domain_id]
            overlapping_subnet = None
            for net_shortname in rd_entry:
                LOG.debug("checking net %s" % net_shortname)
                net_entry = rd_entry[net_shortname]
                for exist_subnet_id in net_entry['subnets']:
                    if exist_subnet_id == subnet['id']:
                        continue
                    exist_subnet = net_entry['subnets'][exist_subnet_id]
                    exist_cidr = exist_subnet['cidr']
                    if check_cidr in exist_cidr or exist_cidr in check_cidr:
                        overlapping_subnet = exist_subnet
                        LOG.debug('rd %s: overlaps with subnet %s id: %s' % (
                            (route_domain_id, exist_subnet, exist_subnet_id)))
                        break
                if overlapping_subnet:
                    # no need to keep looking
                    break
            if not overlapping_subnet:
                placed_route_domain_id = route_domain_id
                break

        if placed_route_domain_id is None:
            if (len(self.rds_cache[tenant_id]) <
                    self.conf.max_namespaces_per_tenant):
                placed_route_domain_id = self._create_aux_rd(tenant_id)
                self.rds_cache[tenant_id][placed_route_domain_id] = {}
                LOG.debug("Tenant %s now has %d route domains" %
                          (tenant_id, len(self.rds_cache[tenant_id])))
            else:
                raise Exception("Cannot allocate route domain")

        LOG.debug("Placed in route domain %s" % placed_route_domain_id)
        rd_entry = self.rds_cache[tenant_id][placed_route_domain_id]

        net_short_name = self.get_neutron_net_short_name(network)
        if net_short_name not in rd_entry:
            rd_entry[net_short_name] = {'subnets': {}}
        net_subnets = rd_entry[net_short_name]['subnets']
        net_subnets[subnet['id']] = {'cidr': check_cidr}
        network['route_domain_id'] = placed_route_domain_id

    def _create_aux_rd(self, tenant_id):
        # Create a new route domain
        route_domain_id = None
        for bigip in self.driver.get_all_bigips():
            partition_id = self.service_adapter.get_folder_name(tenant_id)
            bigip_route_domain_id = self.network_helper.create_route_domain(
                bigip,
                partition=partition_id,
                strictness=self.conf.f5_route_domain_strictness,
                is_aux=True)
            if route_domain_id is None:
                route_domain_id = bigip_route_domain_id.id
            elif bigip_route_domain_id.id != route_domain_id:
                # FixME error
                LOG.debug(
                    "Bigips allocated two different route domains!: %s %s"
                    % (bigip_route_domain_id, route_domain_id))
        LOG.debug("Allocated route domain %s for tenant %s"
                  % (route_domain_id, tenant_id))
        return route_domain_id

    # The purpose of the route domain subnet cache is to
    # determine whether there is an existing bigip
    # subnet that conflicts with a new one being
    # assigned to the route domain.
    """
    # route domain subnet cache
    rds_cache =
        {'<tenant_id>': {
            {'0': {
                '<network type>-<segmentation id>': [
                    'subnets': [
                        '<subnet id>': {
                            'cidr': '<cidr>'
                        }
                ],
            '1': {}}}}
    """
    def update_rds_cache(self, tenant_id):
        # Update the route domain cache from bigips
        if tenant_id not in self.rds_cache:
            LOG.debug("rds_cache: adding tenant %s" % tenant_id)
            self.rds_cache[tenant_id] = {}
            for bigip in self.driver.get_all_bigips():
                self.update_rds_cache_bigip(tenant_id, bigip)
            LOG.debug("rds_cache updated: " + str(self.rds_cache))

    def update_rds_cache_bigip(self, tenant_id, bigip):
        # Update the route domain cache for this tenant
        # with information from bigip's vlan and tunnels
        LOG.debug("rds_cache: processing bigip %s" % bigip.device_name)

        route_domain_ids = self.network_helper.get_route_domain_ids(
            bigip,
            partition=self.service_adapter.get_folder_name(tenant_id))
        # LOG.debug("rds_cache: got bigip route domains: %s" % route_domains)
        for route_domain_id in route_domain_ids:
            self.update_rds_cache_bigip_rd_vlans(
                tenant_id, bigip, route_domain_id)

    def update_rds_cache_bigip_rd_vlans(
            self, tenant_id, bigip, route_domain_id):
        # Update the route domain cache with information
        # from the bigip vlans and tunnels from
        # this route domain
        LOG.debug("rds_cache: processing bigip %s rd %s"
                  % (bigip.device_name, route_domain_id))
        # this gets tunnels too
        partition_id = self.service_adapter.get_folder_name(tenant_id)
        rd_vlans = self.network_helper.get_vlans_in_route_domain_by_id(
            bigip,
            partition=partition_id,
            id=route_domain_id
        )
        LOG.debug("rds_cache: bigip %s rd %s vlans: %s"
                  % (bigip.device_name, route_domain_id, rd_vlans))
        if len(rd_vlans) == 0:
            LOG.debug("No vlans found for route domain: %d" %
                      (route_domain_id))
            return

        # make sure this rd has a cache entry
        tenant_entry = self.rds_cache[tenant_id]
        if route_domain_id not in tenant_entry:
            tenant_entry[route_domain_id] = {}

        # for every VLAN or TUNNEL on this bigip...
        for rd_vlan in rd_vlans:
            self.update_rds_cache_bigip_vlan(
                tenant_id, bigip, route_domain_id, rd_vlan)

    def update_rds_cache_bigip_vlan(
            self, tenant_id, bigip, route_domain_id, rd_vlan):
        # Update the route domain cache with information
        #    from the bigip vlan or tunnel
        LOG.debug("rds_cache: processing bigip %s rd %d vlan %s"
                  % (bigip.device_name, route_domain_id, rd_vlan))
        net_short_name = self.get_bigip_net_short_name(
            bigip, tenant_id, rd_vlan)

        # make sure this net has a cache entry
        tenant_entry = self.rds_cache[tenant_id]
        rd_entry = tenant_entry[route_domain_id]
        if net_short_name not in rd_entry:
            rd_entry[net_short_name] = {'subnets': {}}
        net_subnets = rd_entry[net_short_name]['subnets']

        partition_id = self.service_adapter.get_folder_name(tenant_id)
        LOG.debug("Calling get_selfips with: partition %s and vlan_name %s",
                  partition_id, rd_vlan)
        selfips = self.bigip_selfip_manager.get_selfips(
            bigip,
            partition=partition_id,
            vlan_name=rd_vlan
        )

        LOG.debug("rds_cache: got selfips")
        for selfip in selfips:
            LOG.debug("rds_cache: processing bigip %s rd %s vlan %s self %s" %
                      (bigip.device_name, route_domain_id, rd_vlan,
                       selfip.name))
            if bigip.device_name not in selfip.name:
                LOG.error("rds_cache: Found unexpected selfip %s for tenant %s"
                          % (selfip.name, tenant_id))
                continue
            subnet_id = selfip.name.split(bigip.device_name + '-')[1]

            # convert 10.1.1.1%1/24 to 10.1.1.1/24
            (addr, netbits) = selfip.address.split('/')
            addr = addr.split('%')[0]
            selfip.address = addr + '/' + netbits

            # selfip addresses will have slash notation: 10.1.1.1/24
            netip = netaddr.IPNetwork(selfip.address)
            LOG.debug("rds_cache: updating subnet %s with %s"
                      % (subnet_id, str(netip.cidr)))
            net_subnets[subnet_id] = {'cidr': netip.cidr}
            LOG.debug("rds_cache: now %s" % self.rds_cache)

    def get_route_domain_from_cache(self, network):
        # Get route domain from cache by network
        net_short_name = self.get_neutron_net_short_name(network)
        for tenant_id in self.rds_cache:
            tenant_cache = self.rds_cache[tenant_id]
            for route_domain_id in tenant_cache:
                if net_short_name in tenant_cache[route_domain_id]:
                    return route_domain_id

    def remove_from_rds_cache(self, network, subnet):
        # Get route domain from cache by network
        LOG.debug("remove_from_rds_cache")
        net_short_name = self.get_neutron_net_short_name(network)
        for tenant_id in self.rds_cache:
            LOG.debug("rds_cache: processing remove for %s" % tenant_id)
            deleted_rds = []
            tenant_cache = self.rds_cache[tenant_id]
            for route_domain_id in tenant_cache:
                if net_short_name in tenant_cache[route_domain_id]:
                    net_entry = tenant_cache[route_domain_id][net_short_name]
                    if subnet['id'] in net_entry['subnets']:
                        del net_entry['subnets'][subnet['id']]
                        if len(net_entry['subnets']) == 0:
                            del net_entry['subnets']
                    if len(tenant_cache[route_domain_id][net_short_name]) == 0:
                        del tenant_cache[route_domain_id][net_short_name]
                if len(self.rds_cache[tenant_id][route_domain_id]) == 0:
                    deleted_rds.append(route_domain_id)
            for rd in deleted_rds:
                LOG.debug("removing route domain %d from tenant %s" %
                          (rd, tenant_id))
                del self.rds_cache[tenant_id][rd]

    def get_bigip_net_short_name(self, bigip, tenant_id, network_name):
        # Return <network_type>-<seg_id> for bigip network
        LOG.debug("get_bigip_net_short_name: %s:%s" % (
            tenant_id, network_name))
        partition_id = self.service_adapter.get_folder_name(tenant_id)
        LOG.debug("network_name %s", network_name.split('/'))
        network_name = network_name.split("/")[-1]
        if 'tunnel-gre-' in network_name:
            tunnel_key = self.network_helper.get_tunnel_key(
                bigip,
                network_name,
                partition=partition_id
            )
            return 'gre-%s' % tunnel_key
        elif 'tunnel-vxlan-' in network_name:
            LOG.debug("Getting tunnel key for VXLAN: %s", network_name)
            tunnel_key = self.network_helper.get_tunnel_key(
                bigip,
                network_name,
                partition=partition_id
            )
            return 'vxlan-%s' % tunnel_key
        else:
            LOG.debug("Getting tunnel key for VLAN: %s", network_name)
            vlan_id = self.network_helper.get_vlan_id(bigip,
                                                      name=network_name,
                                                      partition=partition_id)
            return 'vlan-%s' % vlan_id

    @staticmethod
    def get_neutron_net_short_name(network):
        # Return <network_type>-<seg_id> for neutron network
        net_type = network['provider:network_type']
        net_seg_key = network['provider:segmentation_id']
        return net_type + '-' + str(net_seg_key)

    def _assure_subnet_snats(self, assure_bigips, service, subnetinfo):
        # Ensure snat for subnet exists on bigips
        tenant_id = service['loadbalancer']['tenant_id']
        subnet = subnetinfo['subnet']
        snats_per_subnet = self.conf.f5_snat_addresses_per_subnet

        assure_bigips = \
            [bigip for bigip in assure_bigips
                if tenant_id not in bigip.assured_tenant_snat_subnets or
                subnet['id'] not in
                bigip.assured_tenant_snat_subnets[tenant_id]]

        LOG.debug("_assure_subnet_snats: getting snat addrs for: %s" %
                  subnet['id'])
        if len(assure_bigips):
            snat_addrs = self.bigip_snat_manager.get_snat_addrs(
                subnetinfo, tenant_id, snats_per_subnet)

            if len(snat_addrs) != snats_per_subnet:
                raise f5_ex.SNAT_CreationException(
                    "Unable to satisfy request to allocate %d "
                    "snats.  Actual SNAT count: %d SNATs" %
                    (snats_per_subnet, len(snat_addrs)))
            for assure_bigip in assure_bigips:
                self.bigip_snat_manager.assure_bigip_snats(
                    assure_bigip, subnetinfo, snat_addrs, tenant_id)

    def _allocate_gw_addr(self, subnetinfo):
        # Create a name for the port and for the IP Forwarding
        # Virtual Server as well as the floating Self IP which
        # will answer ARP for the members
        need_port_for_gateway = False
        network = subnetinfo['network']
        subnet = subnetinfo['subnet']
        if not network or not subnet:
            LOG.error('Attempted to create default gateway'
                      ' for network with no id...skipping.')
            return

        if not subnet['gateway_ip']:
            raise KeyError("attempting to create gateway on subnet without "
                           "gateway ip address specified.")

        gw_name = "gw-" + subnet['id']
        ports = self.driver.plugin_rpc.get_port_by_name(port_name=gw_name)
        if len(ports) < 1:
            need_port_for_gateway = True

        # There was no port on this agent's host, so get one from Neutron
        if need_port_for_gateway:
            try:
                rpc = self.driver.plugin_rpc
                new_port = rpc.create_port_on_subnet_with_specific_ip(
                    subnet_id=subnet['id'], mac_address=None,
                    name=gw_name, ip_address=subnet['gateway_ip'])
                LOG.info('gateway IP for subnet %s will be port %s'
                         % (subnet['id'], new_port['id']))
            except Exception as exc:
                ermsg = 'Invalid default gateway for subnet %s:%s - %s.' \
                    % (subnet['id'],
                       subnet['gateway_ip'],
                       exc.message)
                ermsg += " SNAT will not function and load balancing"
                ermsg += " support will likely fail. Enable f5_snat_mode."
                LOG.exception(ermsg)
        return True

    def post_service_networking(self, service, all_subnet_hints):
        # Assure networks are deleted from big-ips
        if self.conf.f5_global_routed_mode:
            return

        # L2toL3 networking layer
        # Non Shared Config -  Local Per BIG-IP
        self.update_bigip_l2(service)

        # Delete shared config objects
        deleted_names = set()
        for bigip in self.driver.get_config_bigips():
            LOG.debug('post_service_networking: calling '
                      '_assure_delete_networks del nets sh for bigip %s %s'
                      % (bigip.device_name, all_subnet_hints))
            subnet_hints = all_subnet_hints[bigip.device_name]
            deleted_names = deleted_names.union(
                self._assure_delete_nets_shared(bigip, service,
                                                subnet_hints))

        # Delete non shared config objects
        for bigip in self.driver.get_all_bigips():
            LOG.debug('    post_service_networking: calling '
                      '    _assure_delete_networks del nets ns for bigip %s'
                      % bigip.device_name)

            subnet_hints = all_subnet_hints[bigip.device_name]

            deleted_names = deleted_names.union(
                self._assure_delete_nets_nonshared(
                    bigip, service, subnet_hints)
            )

        for port_name in deleted_names:
            LOG.debug('    post_service_networking: calling '
                      '    del port %s'
                      % port_name)
            self.driver.plugin_rpc.delete_port_by_name(
                port_name=port_name)

    def update_bigip_l2(self, service):
        # Update fdb entries on bigip
        loadbalancer = service['loadbalancer']
        service_adapter = self.service_adapter

        for bigip in self.driver.get_all_bigips():
            for member in service['members']:
                LOG.debug("update_bigip_l2 update service members")
                member['network'] = service_adapter.get_network_from_service(
                    service,
                    member['network_id']
                )
                member_status = member['provisioning_status']
                if member_status == plugin_const.PENDING_DELETE:
                    self.delete_bigip_member_l2(bigip, loadbalancer, member)
                else:
                    self.update_bigip_member_l2(bigip, loadbalancer, member)

            if "network_id" not in loadbalancer:
                LOG.error("update_bigip_l2, expected network ID")
                return

            LOG.debug("update_bigip_l2 get network for ID %s" %
                      loadbalancer["network_id"])
            loadbalancer['network'] = service_adapter.get_network_from_service(
                service,
                loadbalancer['network_id']
            )
            lb_status = loadbalancer['provisioning_status']
            if lb_status == plugin_const.PENDING_DELETE:
                self.delete_bigip_vip_l2(bigip, loadbalancer)
            else:
                LOG.debug("update_bigip_l2 calling update_bigip_vip_l2")
                self.update_bigip_vip_l2(bigip, loadbalancer)
            LOG.debug("update_bigip_l2 complete")

    def update_bigip_member_l2(self, bigip, loadbalancer, member):
        # update pool member l2 records
        network = member['network']
        if network:
            if self.l2_service.is_common_network(network):
                net_folder = 'Common'
            else:
                net_folder = self.service_adapter.get_folder_name(
                    loadbalancer['tenant_id']
                )
            fdb_info = {'network': network,
                        'ip_address': member['address'],
                        'mac_address': member['port']['mac_address']}
            self.l2_service.add_bigip_fdbs(
                bigip, net_folder, fdb_info, member)

    def delete_bigip_member_l2(self, bigip, loadbalancer, member):
        # Delete pool member l2 records
        network = member['network']
        if network:
            if 'port' in member:
                if self.l2_service.is_common_network(network):
                    net_folder = 'Common'
                else:
                    net_folder = self.service_adapter.get_folder_name(
                        loadbalancer['tenant_id']
                    )
                fdb_info = {'network': network,
                            'ip_address': member['address'],
                            'mac_address': member['port']['mac_address']}
                self.l2_service.delete_bigip_fdbs(
                    bigip, net_folder, fdb_info, member)
            else:
                LOG.error('Member on SDN has no port. Manual '
                          'removal on the BIG-IP will be '
                          'required. Was the vm instance '
                          'deleted before the pool member '
                          'was deleted?')

    def update_bigip_vip_l2(self, bigip, loadbalancer):
        # Update vip l2 records
        network = loadbalancer['network']
        if network:
            if self.l2_service.is_common_network(network):
                net_folder = 'Common'
            else:
                net_folder = self.service_adapter.get_folder_name(
                    loadbalancer['tenant_id']
                )
            fdb_info = {'network': network,
                        'ip_address': None,
                        'mac_address': None}
            self.l2_service.add_bigip_fdbs(
                bigip, net_folder, fdb_info, loadbalancer)

    def delete_bigip_vip_l2(self, bigip, loadbalancer):
        # Delete loadbalancer l2 records
        network = loadbalancer['network']
        if network:
            if self.l2_service.is_common_network(network):
                net_folder = 'Common'
            else:
                net_folder = self.service_adapter.get_folder_name(
                    loadbalancer['tenant_id']
                )
            fdb_info = {'network': network,
                        'ip_address': None,
                        'mac_address': None}
            self.l2_service.delete_bigip_fdbs(
                bigip, net_folder, fdb_info, loadbalancer)

    def _assure_delete_nets_shared(self, bigip, service, subnet_hints):
        # Assure shared configuration (which syncs) is deleted
        deleted_names = set()
        tenant_id = service['loadbalancer']['tenant_id']

        delete_gateway = self.bigip_selfip_manager.delete_gateway_on_subnet
        for subnetinfo in self._get_subnets_to_delete(bigip,
                                                      service,
                                                      subnet_hints):
            try:
                if not self.conf.f5_snat_mode:
                    gw_name = delete_gateway(bigip, subnetinfo)
                    deleted_names.add(gw_name)
                my_deleted_names, my_in_use_subnets = \
                    self.bigip_snat_manager.delete_bigip_snats(
                        bigip, subnetinfo, tenant_id)
                deleted_names = deleted_names.union(my_deleted_names)
                for in_use_subnetid in my_in_use_subnets:
                    subnet_hints['check_for_delete_subnets'].pop(
                        in_use_subnetid, None)
            except NeutronException as exc:
                LOG.error("assure_delete_nets_shared: exception: %s"
                          % str(exc.msg))
            except Exception as exc:
                LOG.error("assure_delete_nets_shared: exception: %s"
                          % str(exc.message))

        return deleted_names

    def _assure_delete_nets_nonshared(self, bigip, service, subnet_hints):
        # Delete non shared base objects for networks
        deleted_names = set()
        for subnetinfo in self._get_subnets_to_delete(bigip,
                                                      service,
                                                      subnet_hints):
            try:
                network = subnetinfo['network']
                if self.l2_service.is_common_network(network):
                    network_folder = 'Common'
                else:
                    network_folder = self.service_adapter.get_folder_name(
                        service['loadbalancer']['tenant_id'])

                subnet = subnetinfo['subnet']
                if self.conf.f5_populate_static_arp:
                    self.network_helper.arp_delete_by_subnet(
                        bigip,
                        subnet=subnet['cidr'],
                        mask=None,
                        partition=network_folder
                    )

                local_selfip_name = "local-" + bigip.device_name + \
                                    "-" + subnet['id']

                selfip_address = self.bigip_selfip_manager.get_selfip_addr(
                    bigip,
                    local_selfip_name,
                    partition=network_folder
                )

                if not selfip_address:
                    LOG.error("Failed to get self IP address %s in cleanup.",
                              local_selfip_name)

                self.bigip_selfip_manager.delete_selfip(
                    bigip,
                    local_selfip_name,
                    partition=network_folder
                )

                if self.l3_binding and selfip_address:
                    self.l3_binding.unbind_address(subnet_id=subnet['id'],
                                                   ip_address=selfip_address)

                deleted_names.add(local_selfip_name)

                self.l2_service.delete_bigip_network(bigip, network)

                if subnet['id'] not in subnet_hints['do_not_delete_subnets']:
                    subnet_hints['do_not_delete_subnets'].append(subnet['id'])

                self.remove_from_rds_cache(network, subnet)
                tenant_id = service['loadbalancer']['tenant_id']
                if tenant_id in bigip.assured_tenant_snat_subnets:
                    tenant_snat_subnets = \
                        bigip.assured_tenant_snat_subnets[tenant_id]
                    if subnet['id'] in tenant_snat_subnets:
                        tenant_snat_subnets.remove(subnet['id'])
            except NeutronException as exc:
                LOG.error("assure_delete_nets_nonshared: exception: %s"
                          % str(exc.msg))
            except Exception as exc:
                LOG.error("assure_delete_nets_nonshared: exception: %s"
                          % str(exc.message))

        return deleted_names

    def _get_subnets_to_delete(self, bigip, service, subnet_hints):
        # Clean up any Self IP, SNATs, networks, and folder for
        # services items that we deleted.
        subnets_to_delete = []
        for subnetinfo in subnet_hints['check_for_delete_subnets'].values():
            subnet = self.service_adapter.get_subnet_from_service(
                service, subnetinfo['subnet_id'])
            subnetinfo['subnet'] = subnet
            network = self.service_adapter.get_network_from_service(
                service, subnetinfo['network_id'])
            subnetinfo['network'] = network
            route_domain = network['route_domain_id']
            if not subnet:
                continue
            if not self._ips_exist_on_subnet(
                    bigip,
                    service,
                    subnet,
                    route_domain):
                subnets_to_delete.append(subnetinfo)

        return subnets_to_delete

    def _ips_exist_on_subnet(self, bigip, service, subnet, route_domain):
        # Does the big-ip have any IP addresses on this subnet?
        LOG.debug("_ips_exist_on_subnet entry %s rd %s"
                  % (str(subnet['cidr']), route_domain))
        route_domain = str(route_domain)
        ipsubnet = netaddr.IPNetwork(subnet['cidr'])

        # Are there any virtual addresses on this subnet?
        folder = self.service_adapter.get_folder_name(
            service['loadbalancer']['tenant_id']
        )
        virtual_services = self.network_helper.get_virtual_service_insertion(
            bigip,
            partition=folder
        )
        for virt_serv in virtual_services:
            (_, dest) = virt_serv.items()[0]
            LOG.debug("            _ips_exist_on_subnet: checking vip %s"
                      % str(dest['address']))
            if len(dest['address'].split('%')) > 1:
                vip_route_domain = dest['address'].split('%')[1]
            else:
                vip_route_domain = '0'
            if vip_route_domain != route_domain:
                continue
            vip_addr = strip_domain_address(dest['address'])
            if netaddr.IPAddress(vip_addr) in ipsubnet:
                LOG.debug("            _ips_exist_on_subnet: found")
                return True

        # If there aren't any virtual addresses, are there
        # node addresses on this subnet?
        nodes = self.network_helper.get_node_addresses(
            bigip,
            partition=folder
        )
        for node in nodes:
            LOG.debug("            _ips_exist_on_subnet: checking node %s"
                      % str(node))
            if len(node.split('%')) > 1:
                node_route_domain = node.split('%')[1]
            else:
                node_route_domain = '0'
            if node_route_domain != route_domain:
                continue
            node_addr = strip_domain_address(node)
            if netaddr.IPAddress(node_addr) in ipsubnet:
                LOG.debug("        _ips_exist_on_subnet: found")
                return True

        LOG.debug("            _ips_exist_on_subnet exit %s"
                  % str(subnet['cidr']))
        # nothing found
        return False

    def add_bigip_fdb(self, bigip, fdb):
        self.l2_service.add_bigip_fdb(bigip, fdb)

    def remove_bigip_fdb(self, bigip, fdb):
        self.l2_service.remove_bigip_fdb(bigip, fdb)

    def update_bigip_fdb(self, bigip, fdb):
        self.l2_service.update_bigip_fdb(bigip, fdb)

    def set_context(self, context):
        self.l2_service.set_context(context)

    def vlan_exists(self, network, folder='Common'):
        return False

    def _get_subnets_to_assure(self, service):
        # Examine service and return active networks
        networks = dict()
        loadbalancer = service['loadbalancer']
        service_adapter = self.service_adapter

        lb_status = loadbalancer['provisioning_status']
        if lb_status != plugin_const.PENDING_DELETE:
            if 'network_id' in loadbalancer:
                network = service_adapter.get_network_from_service(
                    service,
                    loadbalancer['network_id']
                )
                subnet = service_adapter.get_subnet_from_service(
                    service,
                    loadbalancer['vip_subnet_id']
                )
                networks[network['id']] = {'network': network,
                                           'subnet': subnet,
                                           'is_for_member': False}

        for member in service['members']:
            if member['provisioning_status'] != plugin_const.PENDING_DELETE:
                if 'network_id' in member:
                    network = service_adapter.get_network_from_service(
                        service,
                        member['network_id']
                    )
                    subnet = service_adapter.get_subnet_from_service(
                        service,
                        member['subnet_id']
                    )
                    networks[network['id']] = {'network': network,
                                               'subnet': subnet,
                                               'is_for_member': True}
        return networks.values()
