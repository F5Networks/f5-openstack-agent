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

import itertools
import netaddr
from requests import HTTPError

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    L2ServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.selfips import BigipSelfIpManager
from f5_openstack_agent.lbaasv2.drivers.bigip.snats import BigipSnatManager
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import strip_domain_address

LOG = logging.getLogger(__name__)


def get_route_domain(network):
    net_type = network['provider:network_type']
    net_segement = network['provider:segmentation_id']
    shared = network['shared']

    if shared:
        LOG.info("route domain: 0 for shared network: %s"
                 % network)
        return 0

    if not net_type:
        raise f5_ex.InvalidNetworkType(
            'Provider network attributes not complete:'
            'Provider:network_type - {0} '
            'Provider:segmentation_id - {1}'
            'Provider network - {2}'
            .format(net_type, net_segement,
                    network))

    LOG.info("route domain: %s for network: %s"
             % (net_segement, network))

    return net_segement


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

        self.vlan_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.vlan)
        self.rds_cache = {}
        self.interface_mapping = self.l2_service.interface_mapping
        self.network_helper = NetworkHelper(conf=self.conf)
        self.service_adapter = self.driver.service_adapter

    def post_init(self):
        # Run and Post Initialization Tasks
        # run any post initialized tasks, now that the agent
        # is fully connected
        self.l2_service.post_init()

    def tunnel_sync(self, tunnel_ips):
        self.l2_service.tunnel_sync(tunnel_ips)

    def set_tunnel_rpc(self, tunnel_rpc):
        # Provide FDB Connector with ML2 RPC access
        self.l2_service.set_tunnel_rpc(tunnel_rpc)

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access
        self.l2_service.set_l2pop_rpc(l2pop_rpc)

    def initialize_vcmp(self):
        self.l2_service.initialize_vcmp_manager()

    def initialize_tunneling(self, bigip):
        # setup tunneling
        vtep_folder = self.conf.f5_vtep_folder
        vtep_selfip_name = self.conf.f5_vtep_selfip_name

        bigip.local_ip = None

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
            else:
                raise f5_ex.MissingVTEPAddress(
                    'device %s missing vtep selfip %s'
                    % (bigip.device_name,
                       '/' + vtep_folder + '/' +
                       vtep_selfip_name))

    def assure_opflex_network_port(self, network_id, network):
        port = None

        port_name = "bigip-opflex-{}".format(network_id)

        port = self.driver.plugin_rpc.create_port_on_network(
            network_id=network_id,
            name=port_name)

        return port

    def is_service_connected(self, service):
        networks = service.get('networks', {})
        supported_net_types = ['vlan', 'vxlan', 'gre', 'opflex']

        for (network_id, network) in networks.iteritems():
            if network_id in self.conf.common_network_ids:
                continue

            network_type = \
                network.get('provider:network_type', "")
            if network_type == "flat":
                continue

            segmentation_id = \
                network.get('provider:segmentation_id', None)
            if not segmentation_id:
                if network_type in supported_net_types and \
                   self.conf.f5_network_segment_physical_network:

                    if network_type == "opflex":
                        # This is called only when the HPB config item
                        # f5_network_segment_physical_network is set.
                        self.assure_opflex_network_port(network_id, network)

                    return False

                LOG.error("Misconfiguration: Segmentation ID is "
                          "missing from the service definition. "
                          "Please check the setting for "
                          "f5_network_segment_physical_network in "
                          "f5-openstack-agent.ini in case neutron "
                          "is operating in Hierarchical Port Binding "
                          "mode.")
                raise f5_ex.InvalidNetworkDefinition(
                    "Network segment ID %s not defined" % network_id)

        return True

    def prep_service_networking(self, service, traffic_group,
                                member_caller=False):
        """Assure network connectivity is established on all bigips."""
        if self.conf.f5_global_routed_mode:
            return

        if not self.is_service_connected(service):
            raise f5_ex.NetworkNotReady(
                "Network segment(s) definition incomplete")

        if self.conf.use_namespaces:
            try:
                LOG.debug("Annotating the service definition networks "
                          "with route domain ID.")

                self._annotate_service_route_domains(service)
            except f5_ex.InvalidNetworkType as exc:
                LOG.warning(exc.message)
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

    def config_snat(self, service):
        subnetsinfo = self._get_subnets_to_assure(service)
        snat_helper = SNATHelper(
            self.driver, service, subnetsinfo, self.bigip_snat_manager
        )
        snat_helper.snat_create()

    def remove_flavor_snat(self, service):
        subnetsinfo = self._get_subnets_to_assure(service)
        snat_helper = SNATHelper(
            self.driver, service, subnetsinfo, self.bigip_snat_manager
        )
        snat_helper.snat_remove()

    def update_flavor_snat(
            self, old_loadbalancer, loadbalancer, service
    ):
        subnetsinfo = self._get_subnets_to_assure(service)
        snat_helper = SNATHelper(
            self.driver, service, subnetsinfo, self.bigip_snat_manager
        )
        snat_helper.snat_update(old_loadbalancer, loadbalancer)

    def _annotate_service_route_domains(self, service):
        # Add route domain notation to pool member and vip addresses.
        tenant_id = service['loadbalancer']['tenant_id']
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
                        if member_network:
                            if member["provisioning_status"] in [
                                    constants_v2.PENDING_DELETE,
                                    constants_v2.ERROR]:
                                self.assign_delete_route_domain(
                                    tenant_id, member_network)
                            else:
                                self.assign_route_domain(
                                    tenant_id, member_network)
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
                if loadbalancer["provisioning_status"] in [
                        constants_v2.PENDING_DELETE, constants_v2.ERROR]:
                    self.assign_delete_route_domain(tenant_id, lb_network)
                else:
                    self.assign_route_domain(tenant_id, lb_network)
                rd_id = '%' + str(lb_network['route_domain_id'])
                service['loadbalancer']['vip_address'] += rd_id
            else:
                service['loadbalancer']['vip_address'] += '%0'

    def is_common_network(self, network):
        return self.l2_service.is_common_network(network)

    # NOTE(pzhang) we can delete this?
    def find_subnet_route_domain(self, tenant_id, subnet_id):
        rd_id = 0
        bigip = self.driver.get_bigip()
        partition_id = self.service_adapter.get_folder_name(
            tenant_id)
        try:
            tenant_rd = self.network_helper.get_route_domain(
                bigip, partition=partition_id)
            rd_id = tenant_rd.id
        except HTTPError as error:
            LOG.error(error)

        return rd_id

    def assign_delete_route_domain(self, tenant_id, network):
        LOG.info("Assgin route domain for deleting")
        if self.l2_service.is_common_network(network):
            network['route_domain_id'] = 0
            return

        route_domain = get_route_domain(network)
        self.set_network_route_domain(network, route_domain)
        LOG.info("Finish route domain %s for deleting" %
                 route_domain)

    def assign_route_domain(self, tenant_id, network):
        LOG.info(
            "Start creating Route Domain of network %s "
            "for tenant: %s" % (network, tenant_id)
        )
        if self.l2_service.is_common_network(network):
            network['route_domain_id'] = 0
            return

        bigips = self.driver.get_all_bigips()
        for bigip in bigips:
            self.create_rd_by_net(bigip, tenant_id, network)

        LOG.info(
            "Finished creating Route Domain of network %s "
            "for tenant: %s" % (network, tenant_id)
        )

    def create_rd_by_net(self, bigip, tenant_id, network):
        LOG.info("Create Route Domain by network %s", network)

        partition = self.service_adapter.get_folder_name(
            tenant_id
        )
        name = self.get_rd_name(network)
        route_domain = get_route_domain(network)
        self.set_network_route_domain(network, route_domain)

        try:
            exists = self.network_helper.route_domain_exists(
                bigip, partition=partition, name=name
            )

            if exists:
                LOG.info("route domain: %s, %s exists on bigip: %s"
                         % (name, route_domain, bigip.hostname))
            else:
                self.network_helper.create_route_domain(
                    bigip,
                    route_domain,
                    name,
                    partition=partition,
                    strictness=self.conf.f5_route_domain_strictness
                )

                LOG.info("create route domain: %s, %s on bigip: %s"
                         % (name, route_domain, bigip.hostname))
        except Exception as ex:
            if ex.response.status_code == 409:
                LOG.info("route domain %s already exists: %s, ignored.." % (
                    route_domain, ex.message))
            else:
                # FIXME(pzhang): what to do with multiple agent race?
                LOG.error(ex.message)
                raise f5_ex.RouteDomainCreationException(
                    "Failed to create route domain: %s, %s on bigip %s"
                    % (name, route_domain, bigip.hostname)
                )

    def get_rd_name(self, network):
        name = self.conf.environment_prefix + '_' + network["id"]
        return name

    def set_network_route_domain(self, network, route_domain):
        if not route_domain:
            raise Exception("Route domain is not found, for network "
                            "%s." % network)

        network["route_domain_id"] = route_domain

    @staticmethod
    def get_neutron_net_short_name(network):
        # Return <network_type>-<seg_id> for neutron network
        net_type = network.get('provider:network_type', None)
        net_seg_key = network.get('provider:segmentation_id', None)
        if not net_type or not net_seg_key:
            raise f5_ex.InvalidNetworkType(
                'Provider network attributes not complete:'
                'provider: network_type - {0} '
                'and provider:segmentation_id - {1}'
                .format(net_type, net_seg_key))

        return net_type + '-' + str(net_seg_key)

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

        bigips = self.driver.get_all_bigips()

        update_members = list()
        delete_members = list()
        update_loadbalancer = None
        delete_loadbalancer = None

        if "network_id" not in loadbalancer:
            LOG.error("update_bigip_l2, expected network ID")
            return

        if loadbalancer.get('provisioning_status', None) == \
                constants_v2.F5_PENDING_DELETE:
            delete_loadbalancer = loadbalancer
        else:
            update_loadbalancer = loadbalancer

        members = service['members']
        for member in members:
            member['network'] = service_adapter.get_network_from_service(
                service, member['network_id'])
            if member.get('provisioning_status', None) == \
                    constants_v2.F5_PENDING_DELETE:
                delete_members.append(member)
            else:
                update_members.append(member)

        loadbalancer['network'] = service_adapter.get_network_from_service(
            service,
            loadbalancer['network_id']
            )

        if delete_loadbalancer or delete_members:
            self.l2_service.delete_fdb_entries(
                bigips, delete_loadbalancer, delete_members)

        if update_loadbalancer or update_members:
            self.l2_service.add_fdb_entries(
                bigips, update_loadbalancer, update_members)

        LOG.debug("update_bigip_l2 complete")

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
                        bigip, subnetinfo, tenant_id, self.conf.provider_name)
                deleted_names = deleted_names.union(my_deleted_names)
                for in_use_subnetid in my_in_use_subnets:
                    subnet_hints['check_for_delete_subnets'].pop(
                        in_use_subnetid, None)
            except f5_ex.F5NeutronException as exc:
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

                if self.conf.f5_network_segment_physical_network:
                    opflex_net_id = network.get('id')
                    if opflex_net_id:
                        opflex_net_port = "bigip-opflex-{}".format(
                            opflex_net_id)
                        deleted_names.add(opflex_net_port)

                if not subnetinfo['network_vlan_inuse']:
                    self.delete_route_domain(
                        bigip, network_folder, network
                    )
                    self.l2_service.delete_bigip_network(bigip, network)

                if subnet['id'] not in subnet_hints['do_not_delete_subnets']:
                    subnet_hints['do_not_delete_subnets'].append(subnet['id'])

                tenant_id = service['loadbalancer']['tenant_id']
                if tenant_id in bigip.assured_tenant_snat_subnets:
                    tenant_snat_subnets = \
                        bigip.assured_tenant_snat_subnets[tenant_id]
                    if subnet['id'] in tenant_snat_subnets:
                        tenant_snat_subnets.remove(subnet['id'])
            except f5_ex.F5NeutronException as exc:
                LOG.debug("assure_delete_nets_nonshared: exception: %s"
                          % str(exc.msg))
            except Exception as exc:
                LOG.debug("assure_delete_nets_nonshared: exception: %s"
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
            route_domain = network.get('route_domain_id', None)
            if not subnet:
                continue

            tenant_id = service['loadbalancer']['tenant_id']

            inuse = self.selfip_routedomain_inuse(
                bigip,
                tenant_id,
                subnet,
                route_domain
            )

            if not inuse['selfip']:
                # XXX(pzhang): a vlan map a route domain,
                # if route domain is not inuse, then mark its vlan
                # can be deleted.
                subnetinfo['network_vlan_inuse'] = inuse['route_domain']
                subnets_to_delete.append(subnetinfo)

        return subnets_to_delete

    def selfip_routedomain_inuse(self, bigip, tenant_id,
                                 subnet, route_domain):
        # check vip and nodes on bigips
        # does the big-ip have any IP addresses on this subnet.
        # check the selfip is in use.
        # check the selfip related route domain is in use.
        # FIXME(pzhang): it may have race problem

        inuse = {"route_domain": False, "selfip": False}

        route_domain = str(route_domain)
        ipsubnet = netaddr.IPNetwork(subnet['cidr'])

        # Are there any virtual addresses on this subnet?
        folder = self.service_adapter.get_folder_name(
            tenant_id
        )
        va_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)
        virtual_addresses = va_helper.get_resources(bigip, partition=folder)

        for vip in virtual_addresses:
            dest = vip.address
            if len(dest.split('%')) > 1:
                vip_route_domain = dest.split('%')[1]
            else:
                vip_route_domain = '0'

            if vip_route_domain == route_domain:
                inuse["route_domain"] = True
                vip_addr = strip_domain_address(dest)
                if netaddr.IPAddress(vip_addr) in ipsubnet:
                    inuse["selfip"] = True

        # If there aren't any virtual addresses, are there
        # node addresses on this subnet?
        nodes = self.network_helper.get_node_addresses(
            bigip,
            partition=folder
        )
        for node in nodes:
            if len(node.split('%')) > 1:
                node_route_domain = node.split('%')[1]
            else:
                node_route_domain = '0'

            if node_route_domain == route_domain:
                inuse["route_domain"] = True
                node_addr = strip_domain_address(node)
                if netaddr.IPAddress(node_addr) in ipsubnet:
                    inuse["selfip"] = True

        LOG.debug("_ips_exist_on_subnet exit %s"
                  % str(subnet['cidr']))

        return inuse

    def delete_route_domain(self, bigip, partition, network):
        LOG.info("Deleting route domain of network %s",
                 network)

        name = self.get_rd_name(network)
        try:
            self.network_helper.delete_route_domain(
                bigip,
                partition=partition,
                name=name
            )
        except HTTPError as err:
            if err.response.status_code == 404:
                LOG.warning(
                    "The deleting route domain"
                    "is not found: %s", err.message
                )
            else:
                raise err

    def add_bigip_fdb(self, bigip, fdb):
        self.l2_service.add_bigip_fdb(bigip, fdb)

    def remove_bigip_fdb(self, bigip, fdb):
        self.l2_service.remove_bigip_fdb(bigip, fdb)

    def update_bigip_fdb(self, bigip, fdb):
        self.l2_service.update_bigip_fdb(bigip, fdb)

    def set_context(self, context):
        self.l2_service.set_context(context)

    def vlan_exists(self, bigip, network, folder='Common'):
        return self.vlan_manager.exists(bigip, name=network, partition=folder)

    def _get_subnets_to_assure(self, service):
        # Examine service and return active networks
        networks = dict()
        loadbalancer = service['loadbalancer']
        service_adapter = self.service_adapter
        lb_status = loadbalancer['provisioning_status']
        if lb_status != constants_v2.F5_PENDING_DELETE:
            if 'network_id' in loadbalancer:
                network = service_adapter.get_network_from_service(
                    service,
                    loadbalancer['network_id']
                )
                subnet = service_adapter.get_subnet_from_service(
                    service,
                    loadbalancer['vip_subnet_id']
                )
                networks[subnet['id']] = {'network': network,
                                          'subnet': subnet,
                                          'is_for_member': False}

        for member in service['members']:
            if member['provisioning_status'] != constants_v2.F5_PENDING_DELETE:
                if 'network_id' in member:
                    network = service_adapter.get_network_from_service(
                        service,
                        member['network_id']
                    )
                    subnet = service_adapter.get_subnet_from_service(
                        service,
                        member['subnet_id']
                    )
                    networks[subnet['id']] = {'network': network,
                                              'subnet': subnet,
                                              'is_for_member': True}

        return networks.values()


class SNATHelper(object):

    FLAVOR_MAP = constants_v2.FLAVOR_SNAT_MAP

    def __init__(self, driver, service, subnetsinfo, snat_manager):
        self.driver = driver
        self.service = service
        self.subnetsinfo = subnetsinfo
        self.snat_manager = snat_manager

        self.flavor = service['loadbalancer'].get('flavor')
        self.traffic_group = self.driver.service_to_traffic_group(service)
        self.partition = self.driver.service_adapter.get_folder_name(
            service['loadbalancer'].get('tenant_id')
        )

    @property
    def ip_addr(self):
        vip = self.service['loadbalancer'].get('vip_address')
        if '%' in vip:
            return vip.split('%')[0]
        return vip

    @property
    def net_info(self):
        lb_subnet_id = self.service['loadbalancer'].get('vip_subnet_id')
        lb_subnet_info = self.service['subnets'].get(lb_subnet_id)
        lb_network_info = self.service['networks'].get(
            lb_subnet_info['network_id'])

        return {'network': lb_network_info, 'subnet': lb_subnet_info}

    def legacy_maintain(self):

        snatpool_name = \
            self.driver.service_adapter.get_folder_name(
                self.service['loadbalancer'].get('id')
            )
        partition = self.driver.service_adapter.get_folder_name(
            self.service['loadbalancer'].get('tenant_id')
        )
        bigips = self.driver.get_config_bigips()

        result = False
        for bigip in bigips:
            result = result or self.snat_manager.snatpool_exist(
                bigip, snatpool_name, partition
            )
            if result:
                break
        return not result

    def new_lb_create(self):
        return len(self.subnetsinfo) == 1

    def snat_create(self):
        bigips = self.driver.get_config_bigips()

        if self.new_lb_create():
            self.lb_snat_create(bigips)
        # else:
        # if self.legacy_maintain():
        # self.members_snat_create(bigips)

    def lb_snat_create(self, bigips):
        # Ensure snat for subnet exists on bigips
        tenant_id = self.service['loadbalancer']['tenant_id']
        subnet_id = self.net_info['subnet']['id']
        lb_id = self.service['loadbalancer']['id']

        ip_version = netaddr.IPAddress(self.ip_addr).version
        snats_per_subnet = self.count_SNATIPs(ip_version)

        LOG.debug("_assure_flavor_snats: getting snat addrs for: %s" %
                  subnet_id)
        if len(bigips):
            snat_name = self.snat_manager.get_flavor_snat_name(
                subnet_id, lb_id, tenant_id)

            snat_addrs = self.snat_manager.get_snat_addrs(
                self.net_info, tenant_id, snats_per_subnet, lb_id,
                snat_name, self.driver.conf.provider_name
            )

            if len(snat_addrs) != snats_per_subnet:
                raise f5_ex.SNATCreationException(
                    "Unable to satisfy request to allocate %d "
                    "snats.  Actual SNAT count: %d SNATs" %
                    (snats_per_subnet, len(snat_addrs)))
            for bigip in bigips:
                self.snat_manager.assure_bigip_snats(
                    bigip, self.net_info, snat_addrs,
                    tenant_id, self.driver.conf.provider_name,
                    lb_id
                )

    def count_SNATIPs(self, ipversion, flavor=None):
        if not flavor:
            flavor = self.flavor
        return self.FLAVOR_MAP[ipversion][flavor]

    def members_snat_create(self, assure_bigips):
        for subnetinfo in self.subnetsinfo:
            if self.driver.conf.f5_snat_addresses_per_subnet > 0 \
                    and subnetinfo['is_for_member']:

                self._assure_subnet_snats(
                    assure_bigips, self.service, subnetinfo
                )

        if subnetinfo['is_for_member'] and not self.driver.conf.f5_snat_mode:
            try:
                self._allocate_gw_addr(subnetinfo)
            except KeyError as err:
                raise f5_ex.VirtualServerCreationException(err.message)

            for assure_bigip in assure_bigips:
                # If we are not using SNATS, attempt to become
                # the subnet's default gateway.
                self.bigip_selfip_manager.assure_gateway_on_subnet(
                    assure_bigip, subnetinfo, self.traffic_group)

    def _assure_subnet_snats(self, assure_bigips, service, subnetinfo):
        # Ensure snat for subnet exists on bigips
        tenant_id = service['loadbalancer']['tenant_id']
        subnet = subnetinfo['subnet']
        snats_per_subnet = self.driver.conf.f5_snat_addresses_per_subnet
        lb_id = service['loadbalancer']['id']

        assure_bigips = \
            [bigip for bigip in assure_bigips
                if tenant_id not in bigip.assured_tenant_snat_subnets or
                subnet['id'] not in
                bigip.assured_tenant_snat_subnets[tenant_id]]

        LOG.debug("_assure_subnet_snats: getting snat addrs for: %s" %
                  subnet['id'])
        if len(assure_bigips):
            snat_name = self.snat_manager.get_snat_name(
                subnet, tenant_id)
            snat_addrs = self.snat_manager.get_snat_addrs(
                subnetinfo, tenant_id, snats_per_subnet, lb_id,
                snat_name, self.driver.conf.provider_name
            )

            if len(snat_addrs) != snats_per_subnet:
                raise f5_ex.SNATCreationException(
                    "Unable to satisfy request to allocate %d "
                    "snats.  Actual SNAT count: %d SNATs" %
                    (snats_per_subnet, len(snat_addrs)))
            for assure_bigip in assure_bigips:
                self.snat_manager.assure_bigip_snats(
                    assure_bigip, subnetinfo, snat_addrs,
                    tenant_id, self.driver.conf.provider_name)

    def snat_remove(self):
        bigips = self.driver.get_config_bigips()
        if not self.legacy_maintain():
            self.lb_snat_delete(bigips)

    def lb_snat_delete(self, bigips):
        tenant_id = self.service['loadbalancer']['tenant_id']
        subnet_id = self.net_info['subnet']['id']
        lb_id = self.service['loadbalancer']['id']

        ip_version = netaddr.IPAddress(self.ip_addr).version
        snats_per_subnet = self.count_SNATIPs(ip_version)

        LOG.debug("_assure_flavor_snats: getting snat addrs for: %s" %
                  subnet_id)

        deleted_ports = set()

        for bigip in bigips:
            ports = self.snat_manager.delete_flavor_snats(
                bigip, self.net_info, snats_per_subnet,
                tenant_id, self.driver.conf.provider_name,
                lb_id
            )
            deleted_ports = set.union(deleted_ports, ports)

        for port_name in deleted_ports:
            self.driver.plugin_rpc.delete_port_by_name(
                port_name=port_name)

    def snat_update(
        self, old_loadbalancer, loadbalancer
    ):
        bigips = self.driver.get_config_bigips()
        if not self.legacy_maintain():
            self.lb_snat_update(
                bigips, old_loadbalancer, loadbalancer
            )

    def lb_snat_update(
        self, bigips, old_loadbalancer, loadbalancer
    ):
        # Ensure snat for subnet exists on bigips
        tenant_id = self.service['loadbalancer']['tenant_id']
        subnet_id = self.net_info['subnet']['id']
        lb_id = self.service['loadbalancer']['id']
        rd = 0

        if not self.driver.conf.f5_global_routed_mode:
            rd = get_route_domain(self.net_info['network'])

        old_ip_version = netaddr.IPAddress(
            old_loadbalancer['vip_address']
        ).version
        old_snats_per_subnet = self.count_SNATIPs(
            old_ip_version, old_loadbalancer['flavor'])

        ip_version = netaddr.IPAddress(
            loadbalancer['vip_address']
        ).version
        new_snats_per_subnet = self.count_SNATIPs(
            ip_version, loadbalancer['flavor'])

        snat_name = self.snat_manager.get_flavor_snat_name(
            subnet_id, lb_id, tenant_id)
        diff = new_snats_per_subnet - old_snats_per_subnet

        snat_addrs_map = dict()

        if diff < 0:
            for i in range(diff, 0):
                index = old_snats_per_subnet + i
                index_snat_name = self.snat_manager._get_index_snat_name(
                    snat_name, self.driver.conf.provider_name, index)

                ports = self.driver.plugin_rpc.get_port_by_name(
                    port_name=index_snat_name
                )
                if len(ports) > 0:
                    ip_addr = ports[0]['fixed_ips'][0]['ip_address']

                    if rd > 0:
                        snat_addrs_map[index_snat_name] = \
                            ip_addr + '%' + str(rd)
                    else:
                        snat_addrs_map[index_snat_name] = ip_addr

                    self.driver.plugin_rpc.delete_port_by_name(
                        port_name=index_snat_name)

        if diff > 0:
            if self.driver.conf.unlegacy_setting_placeholder:
                LOG.debug('setting vnic_type to normal instead of baremetal')
                vnic_type = "normal"
            else:
                vnic_type = "baremetal"

            for i in range(diff):
                index = old_snats_per_subnet + i
                index_snat_name = self.snat_manager._get_index_snat_name(
                    snat_name, self.driver.conf.provider_name, index)

                ports = self.driver.plugin_rpc.get_port_by_name(
                    port_name=index_snat_name
                )
                if len(ports) > 0:
                    ip_addr = ports[0]['fixed_ips'][0]['ip_address']
                else:
                    new_port = self.driver.plugin_rpc.create_port_on_subnet(
                        subnet_id, mac_address=None, name=index_snat_name,
                        fixed_address_count=1, device_id=lb_id,
                        vnic_type=vnic_type
                    )
                    ip_addr = new_port['fixed_ips'][0]['ip_address']

                if rd > 0:
                    snat_addrs_map[index_snat_name] = \
                        ip_addr + '%' + str(rd)
                else:
                    snat_addrs_map[index_snat_name] = ip_addr

        if snat_addrs_map:
            bigips = self.driver.get_config_bigips()
            for bigip in bigips:
                self.snat_manager.update_flavor_snats(
                    bigip, self.net_info, snat_addrs_map,
                    lb_id, tenant_id, diff
                )
