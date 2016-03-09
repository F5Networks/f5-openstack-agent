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
from oslo_utils import importutils

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5ex
from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    L2ServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.selfips import BigipSelfIpManager
from f5_openstack_agent.lbaasv2.drivers.bigip.snats import BigipSnatManager
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import strip_domain_address

LOG = logging.getLogger(__name__)


class NetworkServiceBuilder(object):

    def __init__(self, f5_global_routed_mode, conf, driver):
        self.f5_global_routed_mode = f5_global_routed_mode
        self.conf = conf
        self.driver = driver
        self.l2_service = L2ServiceBuilder(conf, f5_global_routed_mode)

        if self.conf.l3_binding_driver:
            try:
                self.l3_binding = importutils.import_object(
                    self.conf.l3_binding_driver,
                    driver.conf,
                    driver.plugin_rpc)
            except ImportError:
                LOG.error('Failed to import L3 binding driver: %s'
                          % self.conf.l3_binding_driver)
        else:
            LOG.debug('No L3 binding driver configured. '
                      'No L3 binding will be done.')
            self.l3_binding = None

        self.bigip_selfip_manager = BigipSelfIpManager(
            self.conf, self.l2_service, self.l3_binding)
        self.bigip_snat_manager = BigipSnatManager(
            self.conf, self.l2_service, self.l3_binding)

        self.rds_cache = {}
        self.interface_mapping = self.l2_service.interface_mapping

    def post_init(self):
        # Run and Post Initialization Tasks """
        # run any post initialized tasks, now that the agent
        # is fully connected
        self.l2_service.post_init()

        if self.l3_binding:
            LOG.debug('Getting BIG-IP MAC Address for L3 Binding')
            self.l3_binding.register_bigip_mac_addresses()

    def tunnel_sync(self, tunnel_ips):
        self.l2_service.tunnel_sync(tunnel_ips)

    def set_tunnel_rpc(self, tunnel_rpc):
        # Provide FDB Connector with ML2 RPC access """
        self.l2_service.set_tunnel_rpc(tunnel_rpc)

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access """
        self.l2_service.set_l2pop_rpc(l2pop_rpc)

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
                bigip.vxlan.create_multipoint_profile(
                    name='vxlan_ovs', folder='Common')
                bigip.l2gre.create_multipoint_profile(
                    name='gre_ovs', folder='Common')
                # find the IP address for the selfip for each box
                local_ip = bigip.selfip.get_addr(vtep_selfip_name, vtep_folder)
                if local_ip:
                    bigip.local_ip = local_ip
                    local_ips.append(local_ip)
                else:
                    raise f5ex.MissingVTEPAddress(
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
            self._annotate_service_route_domains(service)

        # Per Device Network Connectivity (VLANs or Tunnels)
        subnetsinfo = _get_subnets_to_assure(service)
        for (assure_bigip, subnetinfo) in \
                itertools.product(self.driver.get_all_bigips(), subnetsinfo):
            self.l2_service.assure_bigip_network(
                assure_bigip, subnetinfo['network'])
            self.bigip_selfip_manager.assure_bigip_selfip(
                assure_bigip, service, subnetinfo)

        # L3 Shared Config
        assure_bigips = self.driver.get_config_bigips()
        for subnetinfo in subnetsinfo:
            if self.conf.f5_snat_addresses_per_subnet > 0:
                self._assure_subnet_snats(assure_bigips, service, subnetinfo)

            if subnetinfo['is_for_member'] and not self.conf.f5_snat_mode:
                self._allocate_gw_addr(subnetinfo)
                for assure_bigip in assure_bigips:
                    # if we are not using SNATS, attempt to become
                    # the subnet's default gateway.
                    self.bigip_selfip_manager.assure_gateway_on_subnet(
                        assure_bigip, subnetinfo, traffic_group)

    def _annotate_service_route_domains(self, service):
        # Add route domain notation to pool member and vip addresses.
        LOG.debug("Service before route domains: %s" % service)
        tenant_id = service['pool']['tenant_id']
        self.update_rds_cache(tenant_id)

        if 'members' in service:
            for member in service['members']:
                LOG.debug("processing member %s" % member['address'])
                if 'address' in member:
                    if 'network' in member and member['network']:
                        self.assign_route_domain(
                            tenant_id, member['network'], member['subnet'])
                        rd_id = '%' + str(member['network']['route_domain_id'])
                        member['address'] += rd_id
                    else:
                        member['address'] += '%0'
        if 'vip' in service and 'address' in service['vip']:
            vip = service['vip']
            if 'network' in vip and vip['network']:
                self.assign_route_domain(
                    tenant_id, vip['network'], vip['subnet'])
                rd_id = '%' + str(vip['network']['route_domain_id'])
                service['vip']['address'] += rd_id
            else:
                service['vip']['address'] += '%0'
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
        LOG.debug("max namespaces ==1: %s" %
                  (self.conf.max_namespaces_per_tenant == 1))

        if self.conf.max_namespaces_per_tenant == 1:
            bigip = self.driver.get_bigip()
            LOG.debug("bigip before get_domain: %s" % bigip)
            tenant_rd = bigip.route.get_domain(folder=tenant_id)
            network['route_domain_id'] = tenant_rd
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
            # folder = bigip.decorate_folder(tenant_id)
            bigip_id = bigip.route.create_domain(
                folder=tenant_id,
                strict_route_isolation=self.conf.f5_route_domain_strictness,
                is_aux=True)
            if route_domain_id is None:
                route_domain_id = bigip_id
            elif bigip_id != route_domain_id:
                LOG.debug(
                    "Bigips allocated two different route domains!: %s %s"
                    % (bigip_id, route_domain_id))
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

        route_domain_ids = bigip.route.get_domain_ids(folder=tenant_id)
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
        rd_vlans = bigip.route.get_vlans_in_domain_by_id(
            folder=tenant_id, route_domain_id=route_domain_id)
        LOG.debug("rds_cache: bigip %s rd %s vlans: %s"
                  % (bigip.device_name, route_domain_id, rd_vlans))
        if len(rd_vlans) == 0:
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

        selfips = bigip.selfip.get_selfips(folder=tenant_id, vlan=rd_vlan)
        LOG.debug("rds_cache: got selfips: %s" % selfips)
        for selfip in selfips:
            LOG.debug("rds_cache: processing bigip %s rd %s vlan %s self %s" %
                      (bigip.device_name, route_domain_id, rd_vlan,
                       selfip['name']))
            if bigip.device_name not in selfip['name']:
                LOG.error("rds_cache: Found unexpected selfip %s for tenant %s"
                          % (selfip['name'], tenant_id))
                continue
            subnet_id = selfip['name'].split(bigip.device_name + '-')[1]

            # convert 10.1.1.1%1/24 to 10.1.1.1/24
            addr = selfip['address'].split('/')[0]
            addr = addr.split('%')[0]
            netbits = selfip['address'].split('/')[1]
            selfip['address'] = addr + '/' + netbits

            # selfip addresses will have slash notation: 10.1.1.1/24
            netip = netaddr.IPNetwork(selfip['address'])
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
        net_short_name = self.get_neutron_net_short_name(network)
        for tenant_id in self.rds_cache:
            tenant_cache = self.rds_cache[tenant_id]
            for route_domain_id in tenant_cache:
                if net_short_name in tenant_cache[route_domain_id]:
                    net_entry = tenant_cache[route_domain_id][net_short_name]
                    if subnet['id'] in net_entry:
                        del net_entry[subnet['id']]

    @staticmethod
    def get_bigip_net_short_name(bigip, tenant_id, network_name):
        # Return <network_type>-<seg_id> for bigip network
        if '_tunnel-gre-' in network_name:
            tunnel_key = bigip.l2gre.get_tunnel_key(
                name=network_name, folder=tenant_id)
            return 'gre-%s' % tunnel_key
        elif '_tunnel-vxlan-' in network_name:
            tunnel_key = bigip.vxlan.get_tunnel_key(
                name=network_name, folder=tenant_id)
            return 'vxlan-%s' % tunnel_key
        else:
            vlan_id = bigip.vlan.get_id(name=network_name, folder=tenant_id)
            return 'vlan-%s' % vlan_id

    @staticmethod
    def get_neutron_net_short_name(network):
        # Return <network_type>-<seg_id> for neutron network
        net_type = network['provider:network_type']
        net_seg_key = network['provider:segmentation_id']
        return net_type + '-' + str(net_seg_key)

    def _assure_subnet_snats(self, assure_bigips, service, subnetinfo):
        # Ensure snat for subnet exists on bigips
        tenant_id = service['pool']['tenant_id']
        subnet = subnetinfo['subnet']
        assure_bigips = \
            [bigip for bigip in assure_bigips
                if tenant_id not in bigip.assured_tenant_snat_subnets or
                subnet['id'] not in
                bigip.assured_tenant_snat_subnets[tenant_id]]
        if len(assure_bigips):
            snat_addrs = self.bigip_snat_manager.get_snat_addrs(
                subnetinfo, tenant_id)
            for assure_bigip in assure_bigips:
                self.bigip_snat_manager.assure_bigip_snats(
                    assure_bigip, subnetinfo, snat_addrs, tenant_id)

    def _allocate_gw_addr(self, subnetinfo):
        # Create a name for the port and for the IP Forwarding
        # Virtual Server as well as the floating Self IP which
        # will answer ARP for the members
        need_port_for_gateway = False
        network = subnetinfo['network']
        if not network:
            LOG.error('Attempted to create default gateway'
                      ' for network with no id.. skipping.')
            return

        subnet = subnetinfo['subnet']
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
                LOG.error(ermsg)
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
            LOG.debug('    post_service_networking: calling '
                      '_assure_delete_networks del nets sh for bigip %s %s'
                      % (bigip.device_name, all_subnet_hints))
            subnet_hints = all_subnet_hints[bigip.device_name]
            deleted_names = deleted_names.union(
                self._assure_delete_nets_shared(bigip, service,
                                                subnet_hints))

        # avoids race condition:
        # deletion of shared ip objects must sync before we
        # remove the selfips or vlans from the peer bigips.
        self.driver.sync_if_clustered()

        # Delete non shared config objects
        for bigip in self.driver.get_all_bigips():
            LOG.debug('    post_service_networking: calling '
                      '    _assure_delete_networks del nets ns for bigip %s'
                      % bigip.device_name)
            if self.conf.f5_sync_mode == 'replication':
                subnet_hints = all_subnet_hints[bigip.device_name]
            else:
                # If in autosync mode, then the IP operations were performed
                # on just the primary big-ip, and so that is where the subnet
                # hints are stored. So, just use those hints for every bigip.
                device_name = self.driver.get_bigip().device_name
                subnet_hints = all_subnet_hints[device_name]
            deleted_names = deleted_names.union(
                self._assure_delete_nets_nonshared(
                    bigip, service, subnet_hints))

        for port_name in deleted_names:
            LOG.debug('    post_service_networking: calling '
                      '    del port %s'
                      % port_name)
            self.driver.plugin_rpc.delete_port_by_name(
                port_name=port_name)

    def update_bigip_l2(self, service):
        # Update fdb entries on bigip
        vip = service['vip']
        pool = service['pool']

        for bigip in self.driver.get_all_bigips():
            for member in service['members']:
                if member['status'] == plugin_const.PENDING_DELETE:
                    self.delete_bigip_member_l2(bigip, pool, member)
                else:
                    self.update_bigip_member_l2(bigip, pool, member)
            if 'id' in vip:
                if vip['status'] == plugin_const.PENDING_DELETE:
                    self.delete_bigip_vip_l2(bigip, vip)
                else:
                    self.update_bigip_vip_l2(bigip, vip)

    def update_bigip_member_l2(self, bigip, pool, member):
        # update pool member l2 records
        network = member['network']
        if network:
            if self.l2_service.is_common_network(network):
                net_folder = 'Common'
            else:
                net_folder = pool['tenant_id']
            fdb_info = {'network': network,
                        'ip_address': member['address'],
                        'mac_address': member['port']['mac_address']}
            self.l2_service.add_bigip_fdbs(
                bigip, net_folder, fdb_info, member)

    def delete_bigip_member_l2(self, bigip, pool, member):
        # Delete pool member l2 records
        network = member['network']
        if network:
            if member['port']:
                if self.l2_service.is_common_network(network):
                    net_folder = 'Common'
                else:
                    net_folder = pool['tenant_id']
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

    def update_bigip_vip_l2(self, bigip, vip):
        # Update vip l2 records
        network = vip['network']
        if network:
            if self.l2_service.is_common_network(network):
                net_folder = 'Common'
            else:
                net_folder = vip['tenant_id']
            fdb_info = {'network': network,
                        'ip_address': None,
                        'mac_address': None}
            self.l2_service.add_bigip_fdbs(
                bigip, net_folder, fdb_info, vip)

    def delete_bigip_vip_l2(self, bigip, vip):
        # Delete vip l2 records
        network = vip['network']
        if network:
            if self.l2_service.is_common_network(network):
                net_folder = 'Common'
            else:
                net_folder = vip['tenant_id']
            fdb_info = {'network': network,
                        'ip_address': None,
                        'mac_address': None}
            self.l2_service.delete_bigip_fdbs(
                bigip, net_folder, fdb_info, vip)

    def _assure_delete_nets_shared(self, bigip, service, subnet_hints):
        # Assure shared configuration (which syncs) is deleted
        deleted_names = set()
        tenant_id = service['pool']['tenant_id']
        delete_gateway = self.bigip_selfip_manager.delete_gateway_on_subnet
        for subnetinfo in _get_subnets_to_delete(bigip, service, subnet_hints):
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
        for subnetinfo in _get_subnets_to_delete(bigip, service, subnet_hints):
            try:
                network = subnetinfo['network']
                if self.l2_service.is_common_network(network):
                    network_folder = 'Common'
                else:
                    network_folder = service['pool']['tenant_id']

                subnet = subnetinfo['subnet']
                if self.conf.f5_populate_static_arp:
                    bigip.arp.delete_by_subnet(subnet=subnet['cidr'],
                                               mask=None,
                                               folder=network_folder)
                local_selfip_name = "local-" + bigip.device_name + \
                                    "-" + subnet['id']

                selfip_address = bigip.selfip.get_addr(name=local_selfip_name,
                                                       folder=network_folder)
                bigip.selfip.delete(name=local_selfip_name,
                                    folder=network_folder)
                if self.l3_binding:
                    self.l3_binding.unbind_address(subnet_id=subnet['id'],
                                                   ip_address=selfip_address)

                deleted_names.add(local_selfip_name)

                self.l2_service.delete_bigip_network(bigip, network)

                if subnet['id'] not in subnet_hints['do_not_delete_subnets']:
                    subnet_hints['do_not_delete_subnets'].append(subnet['id'])

                self.remove_from_rds_cache(network, subnet)
                tenant_id = service['pool']['tenant_id']
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


def _get_subnets_to_assure(service):
    # Examine service and return active networks
    networks = dict()
    vip = service['vip']
    if 'id' in vip and \
            not vip['status'] == plugin_const.PENDING_DELETE:
        if 'network' in vip and vip['network']:
            network = vip['network']
            subnet = vip['subnet']
            networks[network['id']] = {'network': network,
                                       'subnet': subnet,
                                       'is_for_member': False}

    for member in service['members']:
        if not member['status'] == plugin_const.PENDING_DELETE:
            if 'network' in member and member['network']:
                network = member['network']
                subnet = member['subnet']
                networks[network['id']] = {'network': network,
                                           'subnet': subnet,
                                           'is_for_member': True}
    return networks.values()


def _get_subnets_to_delete(bigip, service, subnet_hints):
    # Clean up any Self IP, SNATs, networks, and folder for
    # services items that we deleted.
    subnets_to_delete = []
    for subnetinfo in subnet_hints['check_for_delete_subnets'].values():
        subnet = subnetinfo['subnet']
        route_domain = subnetinfo['network']['route_domain_id']
        if not subnet:
            continue
        if not _ips_exist_on_subnet(bigip, service, subnet, route_domain):
            subnets_to_delete.append(subnetinfo)
    return subnets_to_delete


def _ips_exist_on_subnet(bigip, service, subnet, route_domain):
    # Does the big-ip have any IP addresses on this subnet?
    LOG.debug("_ips_exist_on_subnet entry %s rd %s"
              % (str(subnet['cidr']), route_domain))
    route_domain = str(route_domain)
    ipsubnet = netaddr.IPNetwork(subnet['cidr'])
    # Are there any virtual addresses on this subnet?
    get_vs = bigip.virtual_server.get_virtual_service_insertion
    virtual_services = get_vs(folder=service['pool']['tenant_id'])
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
    get_node_addr = bigip.pool.get_node_addresses
    nodes = get_node_addr(folder=service['pool']['tenant_id'])
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
