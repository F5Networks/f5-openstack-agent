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

import copy
import math
import netaddr
from requests import HTTPError

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.l2_service import \
    L2ServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import SelfIP
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import Vlan
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.route import RouteHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.selfips import BigipSelfIpManager
from f5_openstack_agent.lbaasv2.drivers.bigip.snats import BigipSnatManager
from f5_openstack_agent.lbaasv2.drivers.bigip import utils

LOG = logging.getLogger(__name__)


def get_route_domain(network, device):
    net_type = network['provider:network_type']
    shared = network['shared']

    if shared:
        LOG.info("route domain: 0 for shared network: %s"
                 % network)
        return 0

    vtep_node_ip = utils.get_node_vtep(device)
    LOG.info(
        "Get vtep_node_ip %s." % vtep_node_ip
    )
    vlanid = utils.get_vtep_vlan(network, vtep_node_ip)

    if not net_type:
        raise f5_ex.InvalidNetworkType(
            'Provider network attributes not complete:'
            'Provider:network_type - {0} '
            'Provider:segmentation_id - {1}'
            'Provider network - {2}'
            .format(net_type, vlanid,
                    network))

    LOG.info("route domain: %s for network: %s"
             % (vlanid, network))

    return vlanid


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
            self.driver, self.l2_service)

        self.vlan_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.vlan)
        self.rds_cache = {}
        self.network_helper = NetworkHelper(conf=self.conf)
        self.service_adapter = self.driver.service_adapter

    def tunnel_sync(self, tunnel_ips):
        self.l2_service.tunnel_sync(tunnel_ips)

    def set_tunnel_rpc(self, tunnel_rpc):
        # Provide FDB Connector with ML2 RPC access
        self.l2_service.set_tunnel_rpc(tunnel_rpc)

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access
        self.l2_service.set_l2pop_rpc(l2pop_rpc)

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

    # TODO(pzhang): delete this seems useless?
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

    def prep_mb_network(self, service):
        if self.conf.f5_global_routed_mode:
            return
        if not self.is_service_connected(service):
            raise f5_ex.NetworkNotReady(
                "Network segment(s) definition incomplete"
            )
        if self.conf.use_namespaces:
            try:
                LOG.debug(
                    "Annotating the service definition networks "
                    "with route domain ID."
                )
                self._annotate_service_route_domains(service)
            except f5_ex.InvalidNetworkType as exc:
                LOG.warning(exc.message)
            except Exception as err:
                LOG.exception(err)
                raise f5_ex.RouteDomainCreationException(
                    "Route domain annotation error"
                )

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
        self.lb_netinfo_to_assure(service)
        bigips = service['bigips']
        for bigip in bigips:
            # Make sure the L2 network is established
            self.l2_service.assure_bigip_network(
                bigip, service['lb_netinfo']['network'],
                service['device']
            )

    def config_lb_default_route(self, service):
        route_helper = RouteHelper(
            service['lb_netinfo'],
            self.l2_service
        )
        bigips = service['bigips']
        for bigip in bigips:
            route_helper.create_route_for_net(bigip)

    def remove_lb_default_route(
            self, bigip, subnet, service):
        route_helper = RouteHelper(
            service['lb_netinfo'],
            self.l2_service
        )
        route_helper.remove_default_route(
            bigip, subnet)

    def config_selfips(self, service, **kwargs):
        lb_network = kwargs.get("network", service['lb_netinfo']["network"])
        lb_subnets = kwargs.get("subnets", service['lb_netinfo']["subnets"])

        subnetinfo = {'network': lb_network}
        for bigip in service['bigips']:
            device = service['device']
            vlan_mac = utils.get_vlan_mac(
                self.vlan_manager, bigip, lb_network, device)
            for subnet in lb_subnets:
                subnetinfo['subnet'] = subnet
                self.bigip_selfip_manager.assure_bigip_selfip(
                    bigip, service, subnetinfo, vlan_mac)

    def config_snat(self, service):
        flavor = service["loadbalancer"].get("flavor")
        if flavor in [11, 12, 13]:
            MyHelper = SNATHelper
        elif flavor in [1, 2, 3, 4, 5, 6, 21]:
            lb_id = service["loadbalancer"]["id"]
            rpc = self.driver.plugin_rpc
            port_v4_name = self.bigip_snat_manager.get_snat_name(lb_id, 4)
            port_v6_name = self.bigip_snat_manager.get_snat_name(lb_id, 6)
            port_v4 = rpc.get_port_by_name(port_name=port_v4_name)
            port_v6 = rpc.get_port_by_name(port_name=port_v6_name)
            portc = len(port_v4 or port_v6)

            if portc == 0:
                # Need to rebuild with large SNAT style
                MyHelper = LargeSNATHelper
            else:
                network_name = "snat-" + lb_id
                nets, netc = rpc.get_network_by_name(name=network_name)
                if netc > 0:
                    # Large SNAT style
                    MyHelper = LargeSNATHelper
                else:
                    # Legacy SNAT style
                    MyHelper = SNATHelper
        elif flavor in [7, 8]:
            MyHelper = LargeSNATHelper
        else:
            # Impossible path
            MyHelper = LargeSNATHelper

        snat_helper = MyHelper(
            self.driver, service, service['lb_netinfo'],
            self.bigip_snat_manager,
            self.l2_service,
            snat_network_type=self.conf.snat_network_type,
            net_service=self
        )
        snat_helper.snat_create()

    def remove_flavor_snat(self, service, rm_port=True):
        flavor = service["loadbalancer"].get("flavor")
        if flavor in [11, 12, 13]:
            MyHelper = SNATHelper
        else:
            MyHelper = LargeSNATHelper

        snat_helper = MyHelper(
            self.driver, service, service['lb_netinfo'],
            self.bigip_snat_manager,
            self.l2_service,
            snat_network_type=self.conf.snat_network_type,
            net_service=self
        )
        snat_helper.snat_remove(rm_port=rm_port)

    def snat_network_exists(self, lb_id):
        network_name = "snat-" + lb_id

        rpc = self.driver.plugin_rpc
        nets, netc = rpc.get_network_by_name(name=network_name)

        if netc > 1:
            # Invalid path
            raise Exception("SNAT network %s count is %s.",
                            network_name,  netc)
        elif netc == 1:
            return True
        else:
            return False

    def snat_subnet_size(self, lb_id):
        subnet_v4_name = "snat-v4-" + lb_id
        subnet_v6_name = "snat-v6-" + lb_id

        rpc = self.driver.plugin_rpc
        snet4s, snet4c = rpc.get_subnet_by_name(name=subnet_v4_name)
        snet6s, snet6c = rpc.get_subnet_by_name(name=subnet_v6_name)

        size4 = 0
        size6 = 0
        if snet4c > 1:
            # Invalid path
            raise Exception("SNAT subnet %s count is %s.",
                            subnet_v4_name, snet4c)
        elif snet4c == 1:
            cidr4 = snet4s[0]["cidr"]
            size4 = 32 - int(cidr4.split("/")[-1])

        if snet6c > 1:
            # Invalid path
            raise Exception("SNAT subnet %s count is %s.",
                            subnet_v6_name, snet6c)
        elif snet6c == 1:
            cidr6 = snet6s[0]["cidr"]
            size6 = 128 - int(cidr6.split("/")[-1])

        if size4 > 0 and size6 > 0 and size4 != size6:
            # Invalid path
            raise Exception("SNAT subnet size v4 %s and v6 %s is "
                            "inconsistent.", subnet_v4_name,
                            subnet_v6_name)

        return size4 or size6

    def snat_port_exists(self, lb_id):
        port_v4_name = self.bigip_snat_manager.get_snat_name(lb_id, 4)
        port_v6_name = self.bigip_snat_manager.get_snat_name(lb_id, 6)

        rpc = self.driver.plugin_rpc
        port_v4 = rpc.get_port_by_name(port_name=port_v4_name)
        port_v6 = rpc.get_port_by_name(port_name=port_v6_name)
        port4c = len(port_v4)
        port6c = len(port_v6)
        portc = port4c + port6c

        if port4c > 1:
            # Invalid path
            raise Exception("SNAT v4 port %s count is %s.",
                            port_v4_name,  port4c)
        elif port6c > 1:
            # Invalid path
            raise Exception("SNAT v6 port %s count is %s.",
                            port_v6_name, port6c)
        elif portc > 0:
            return True
        else:
            return False

    def update_flavor_snat(
        self, old_loadbalancer, loadbalancer, service
    ):
        # NOTE(qzhao): There are totally 4 supported update cases:
        # Case 1:
        #   The movement inside of old style of flavor 1-6, or the movement
        #   from old style of flavor 21 to old style of flavor 1-6.
        # Case 2:
        #   The movement inside of new style of flavor 1-8,21.
        # Case 3:
        #   The movement inside of old style of flavor 11-13.
        # Case 4:
        #   The movement from old style of flavor 1-6,21 to new style of
        #   flavor 7-8,21.
        # Others are not supported.

        lb_id = loadbalancer["id"]
        new = loadbalancer.get("flavor")
        old = old_loadbalancer.get("flavor")

        if old == new:
            if new == 21:
                new_maxc = loadbalancer.get("max_concurrency")
                old_maxc = old_loadbalancer.get("max_concurrency")
                if old_maxc == new_maxc:
                    return
            else:
                return

        if (11 <= old <= 13 and not 11 <= new <= 13) or \
           (11 <= new <= 13 and not 11 <= old <= 13):
            raise f5_ex.SNATCreationException(
                "Flavor 11/12/13 do not support large SNAT style")

        snat_network_exists = self.snat_network_exists(lb_id)
        snat_subnet_size = self.snat_subnet_size(lb_id)
        snat_port_exists = self.snat_port_exists(lb_id)

        migrate = False
        if 11 <= old <= 13 and 11 <= new <= 13:
            # Case 3
            MyHelper = SNATHelper
        elif snat_network_exists and snat_subnet_size == 7:
            # Case 2
            MyHelper = LargeSNATHelper
        elif ((1 <= old <= 6 and 1 <= new <= 6) or
                (old == 21 and 1 <= new <= 6)) and \
                not snat_network_exists and snat_port_exists:
            # Case 1
            MyHelper = SNATHelper
        elif 1 <= old <= 6 and new in [7, 8, 21]:
            # Case 4
            MyHelper = LargeSNATHelper
            migrate = True
        else:
            raise f5_ex.SNATCreationException(
                "Unsupported loadbalancer flavor change")

        snat_helper = MyHelper(
            self.driver, service, service['lb_netinfo'],
            self.bigip_snat_manager,
            self.l2_service,
            snat_network_type=self.conf.snat_network_type,
            net_service=self
        )

        if migrate:
            # Only remove SNAT port
            snat_helper.snat_remove(rm_pool=False)
            snat_helper.snat_create()
        else:
            snat_helper.snat_update(old_loadbalancer, loadbalancer)

    def _rd_exist(self, addr):
        return "%" in addr

    def _annotate_service_route_domains(self, service):
        # Add route domain notation to pool member and vip addresses.
        tenant_id = service['loadbalancer']['tenant_id']
        loadbalancer = service['loadbalancer']
        bigips = service['bigips']
        device = service['device']
        rd_id = None

        if 'vip_address' in service['loadbalancer']:
            if 'network_id' in loadbalancer:
                lb_network = self.service_adapter.get_network_from_service(
                    service, loadbalancer['network_id'])
                if loadbalancer["provisioning_status"] in [
                        constants_v2.PENDING_DELETE, constants_v2.ERROR]:
                    self.assign_delete_route_domain(
                        tenant_id, lb_network, device)
                else:
                    self.assign_route_domain(
                        tenant_id, lb_network, device, bigips)

                if not self._rd_exist(
                    service['loadbalancer']['vip_address']
                ):
                    rd_id = '%' + str(lb_network['route_domain_id'])
                    service['loadbalancer']['vip_address'] += rd_id
            else:
                service['loadbalancer']['vip_address'] += '%0'

        if 'members' in service:
            for member in service['members']:
                if 'address' in member and not self._rd_exist(
                    member['address']
                ):
                    if rd_id:
                        member['address'] += rd_id
                    else:
                        member['address'] += '%0'

    def is_common_network(self, network):
        return self.l2_service.is_common_network(network)

    def assign_delete_route_domain(self, tenant_id, network, device):
        LOG.info("Assgin route domain for deleting")
        if self.l2_service.is_common_network(network):
            network['route_domain_id'] = 0
            return

        route_domain = get_route_domain(network, device)
        self.set_network_route_domain(network, route_domain)
        LOG.info("Finish set route domain %s for deleting" %
                 route_domain)

    def assign_route_domain(
            self, tenant_id, network, device, bigips):
        LOG.info(
            "Start creating Route Domain of network %s "
            "for tenant: %s" % (network, tenant_id)
        )
        if self.l2_service.is_common_network(network):
            network['route_domain_id'] = 0
            return

        for bigip in bigips:
            self.create_rd_by_net(
                bigip, tenant_id, network, device)

        LOG.info(
            "Finished creating Route Domain of network %s "
            "for tenant: %s" % (network, tenant_id)
        )

    def create_rd_by_net(
            self, bigip, tenant_id, network, device):
        LOG.info("Create Route Domain by network %s", network)

        partition = self.service_adapter.get_folder_name(
            tenant_id
        )
        name = self.get_rd_name(network)
        route_domain = get_route_domain(network, device)
        self.set_network_route_domain(network, route_domain)

        try:
            self.network_helper.create_route_domain(
                bigip,
                route_domain,
                name,
                partition=partition,
                strictness=self.conf.f5_route_domain_strictness
            )

            LOG.info("create route domain: %s, %s on bigip: %s"
                     % (name, route_domain, bigip.hostname))
        except HTTPError:
            # FIXME(pzhang): what to do with multiple agent race?
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

    # TODO(pzhang): delete this on one use this?
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

    def post_service_networking(self, service, rm_port=True):
        # Assure networks are deleted from big-ips
        if self.conf.f5_global_routed_mode:
            return

        # L2toL3 networking layer
        # Non Shared Config -  Local Per BIG-IP
        self.update_bigip_l2(service)

        # Delete shared config objects
        deleted_names = set()
        for bigip in service['bigips']:
            deleted_names |= self._delete_shared_nets_config(
                bigip, service)

        if rm_port:
            for port_name in deleted_names:
                self.driver.plugin_rpc.delete_port_by_name(
                    port_name=port_name)

    def update_bigip_l2(self, service):
        # Update fdb entries on bigip
        loadbalancer = service['loadbalancer']
        service_adapter = self.service_adapter

        bigips = service['bigips']

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

            mb_net = member.get('network_id')
            if mb_net:
                member['network'] = service_adapter.get_network_from_service(
                    service, mb_net)
                if member.get('provisioning_status', None) == \
                        constants_v2.F5_PENDING_DELETE:
                    delete_members.append(member)
                else:
                    update_members.append(member)

        lb_net = loadbalancer.get('network_id')
        if lb_net:
            loadbalancer['network'] = service_adapter.get_network_from_service(
                service, lb_net
            )

        if delete_loadbalancer or delete_members:
            self.l2_service.delete_fdb_entries(
                bigips, delete_loadbalancer, delete_members)

        if update_loadbalancer or update_members:
            self.l2_service.add_fdb_entries(
                bigips, update_loadbalancer, update_members)

        LOG.debug("update_bigip_l2 complete")

    def _delete_shared_nets_config(self, bigip, service):
        deleted_names = set()
        delete_gateway = self.bigip_selfip_manager.delete_gateway_on_subnet

        subnets_to_delete = self._get_subnets_to_delete(
            bigip, service
        )

        # A set of networks to be deleteed
        networks = {}

        for subnetinfo in subnets_to_delete:
            try:
                if not self.conf.f5_snat_mode:
                    gw_name = delete_gateway(bigip, subnetinfo)
                    deleted_names.add(gw_name)

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

                # only when lb vlan is not in use,
                # it means network is not used,
                # and subnets (selfip, vlan, route_doamin) of
                # network is not used
                if not subnetinfo['network_vlan_inuse']:

                    self.remove_lb_default_route(
                        bigip, subnetinfo['subnet'], service
                    )

                    local_selfip_name = "local-" + bigip.device_name \
                        + "-" + subnet['id']

                    self.bigip_selfip_manager.delete_selfip(
                        bigip,
                        local_selfip_name,
                        partition=network_folder
                    )

                    deleted_names.add(local_selfip_name)

                    networks[network["id"]] = (network, network_folder)

                    if self.conf.f5_network_segment_physical_network:
                        opflex_net_id = network.get('id')
                        if opflex_net_id:
                            opflex_net_port = "bigip-opflex-{}".format(
                                opflex_net_id)
                            deleted_names.add(opflex_net_port)
            except Exception as exc:
                LOG.debug("_delete_shared_nets_config: exception: %s\n"
                          % str(exc.message))

        for id in networks.keys():
            network, folder = networks[id]
            self.delete_route_domain(bigip, folder, network)
            self.l2_service.delete_bigip_network(
                bigip, network, service['device'])

        return deleted_names

    def _get_subnets_to_delete(self, bigip, service):
        # Clean up any Self IP, SNATs, networks, and folder for
        # services items that we deleted.
        subnets_to_delete = []
        network = service['lb_netinfo']['network']

        for subnet in service['lb_netinfo']['subnets']:
            subnetinfo = dict()

            route_domain = network.get('route_domain_id', None)
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
                subnetinfo['network'] = network
                subnetinfo['subnet'] = subnet
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
                vip_addr = utils.strip_domain_address(dest)
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
                node_addr = utils.strip_domain_address(node)
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
            if err.response.status_code == 400:
                LOG.warning(
                    "Route domain may referenced by self-ips when"
                    "concurrent deleting lb: %s", err.message
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

    def lb_netinfo_to_assure(self, service):
        # Examine service and return active networks

        network_id = service['loadbalancer']['network_id']
        network = service['networks'][network_id]
        subnets = self.driver.plugin_rpc.get_subnets_info(
            subnet_ids=network['subnets']
        )
        service['lb_netinfo'] = {'network': network, 'subnets': subnets}

        self.check_lb_netinfo(service)

    def check_lb_netinfo(self, service):
        # in case of create mutliple or duplicate
        # selfip, route, SNAT IPs
        status = service['loadbalancer']['provisioning_status']
        network = service['lb_netinfo']['network']
        subnets = service['lb_netinfo']['subnets']

        if not network:
            LOG.error("Not found network info of network: %s.\n" %
                      network)
            raise Exception(
                "Can not find network info about service %s.\n" %
                service
            )

        if not subnets:
            LOG.error(
                "Not found subnet info of network: %s\n."
                "SNAT IP can not be created." %
                network
            )
            raise Exception(
                "Can not find subnet info about service %s\n." %
                service
            )

        if status not in [
                constants_v2.PENDING_DELETE,
                constants_v2.ERROR
        ]:
            if len(subnets) > 2:
                LOG.warning(
                    "The loadbalancer network %s has more than 2 subnet "
                    "we may create SNAT IPs not as you excepted.\n" %
                    subnets
                )
                raise Exception(
                    "Number of subnets is more than 2 in network"
                    "subnet info is: %s, network info is: %s.\n" %
                    (subnets, network)
                )

            ipv4_subnet = [
                subnet for subnet in subnets if subnet['ip_version'] == 4
            ]
            ipv6_subnet = [
                subnet for subnet in subnets if subnet['ip_version'] == 6
            ]

            if len(ipv4_subnet) > 1 or len(ipv6_subnet) > 1:
                raise Exception(
                    "The number of IPv4 or IPv6 subent is more than 1, "
                    "network info is: %s\n" % service['lb_netinfo']
                )


class SNATHelper(object):

    FLAVOR_MAP = constants_v2.FLAVOR_SNAT_MAP

    def __init__(self, driver, service, lb_netinfo,
                 snat_manager, l2_service, **kwargs):
        self.driver = driver
        self.service = service
        self.snat_manager = snat_manager
        self.l2_service = l2_service
        self.flavor = service['loadbalancer'].get('flavor')
        self.traffic_group = self.driver.get_traffic_group_1()
        self.partition = self.driver.service_adapter.get_folder_name(
            service['loadbalancer'].get('tenant_id')
        )

        self.snat_net = copy.deepcopy(lb_netinfo)

    def snat_pools_exist(self):
        snatpool_name = \
            self.driver.service_adapter.get_folder_name(
                self.service['loadbalancer'].get('id')
            )

        if self.l2_service.is_common_network(
            self.snat_net['network']
        ):
            partition = 'Common'
        else:
            partition = self.driver.service_adapter.get_folder_name(
                self.service['loadbalancer'].get('tenant_id')
            )

        bigips = self.service['bigips']

        result = False
        for bigip in bigips:
            result = self.snat_manager.snatpool_exist(
                bigip, snatpool_name, partition
            )
            if not result:
                LOG.warning(
                    "Cannot find SNAT pool %s on bigip %s" %
                    (snatpool_name, bigip.hostname)
                )

    def snat_create(self):
        # Ensure snat for subnet exists on bigips
        bigips = self.service['bigips']
        tenant_id = self.service['loadbalancer']['tenant_id']
        lb_id = self.service['loadbalancer']['id']

        device = self.service['device']
        masq_mac = device['device_info']['masquerade_mac']
        # llinfo is a list of dict type
        llinfo = device['device_info'].get('local_link_information', None)

        if llinfo:
            link_info = llinfo[0]
        else:
            link_info = dict()
            llinfo = [link_info]

        link_info.update({"lb_mac": masq_mac})
        binding_profile = {
            "local_link_information": llinfo
        }

        snat_addrs = set()

        LOG.debug("before snat create port")
        for subnet in self.snat_net['subnets']:
            LOG.info("Creating snat addrs for subnet: %s" %
                     subnet)

            ip_version = subnet['ip_version']
            snats_per_subnet = self.count_SNATIPs(
                ip_version, self.service['loadbalancer'])

            if len(bigips):
                snat_name = self.snat_manager.get_snat_name(
                    lb_id, ip_version)

                if self.driver.conf.unlegacy_setting_placeholder:
                    LOG.debug(
                        'setting vnic_type to normal instead of baremetal'
                    )
                    vnic_type = "normal"
                else:
                    vnic_type = "baremetal"

                port = self.driver.plugin_rpc.get_port_by_name(
                    port_name=snat_name
                )

                if len(port) == 0:
                    port = self.driver.plugin_rpc.create_port_on_subnet(
                        subnet_id=subnet['id'],
                        name=snat_name,
                        fixed_address_count=snats_per_subnet,
                        device_id=lb_id,
                        vnic_type=vnic_type,
                        binding_profile=binding_profile
                    )
                else:
                    port = port[0]

                snat_addrs |= {
                    addr_info['ip_address'] for addr_info in port['fixed_ips']
                }

                if not port or len(port['fixed_ips']) != snats_per_subnet:
                    raise f5_ex.SNATCreationException(
                        "Unable to satisfy request to allocate %d "
                        "snats.  Actual SNAT count: %d SNATs"
                        "The subnet info is: %s." %
                        (snats_per_subnet, len(snat_addrs), subnet)
                    )
        LOG.debug("after snat create port")

        snat_info = {}
        snat_info[
            'pool_name'
        ] = self.driver.service_adapter.get_folder_name(lb_id)
        snat_info['addrs'] = snat_addrs

        if self.l2_service.is_common_network(self.snat_net['network']):
            snat_info['network_folder'] = 'Common'
            snat_info['pool_folder'] = 'Common'
        else:
            snat_info['network_folder'] = self.partition
            snat_info['pool_folder'] = self.partition

        for bigip in bigips:
            self.snat_manager.assure_bigip_snats(
                bigip, self.snat_net, snat_info,
                tenant_id, snat_name
            )

    def count_SNATIPs(self, ipversion, lb):
        flavor = lb["flavor"]
        maxc = lb.get("max_concurrency", 1000000)
        if maxc is None:
            maxc = 1000000

        if flavor != 21:
            return self.FLAVOR_MAP[ipversion][flavor]

        v4_snat = int(math.ceil(float(maxc) / 65536))

        # Max snat ip number is 122
        if v4_snat > 122:
            v4_snat = 122

        if ipversion == 6 and v4_snat > 1:
            return v4_snat - 1
        else:
            return v4_snat

    def snat_remove(self, rm_pool=True, rm_port=True):
        bigips = self.service['bigips']
        self.snat_pools_exist()
        self.lb_snat_delete(bigips, rm_pool, rm_port)

    def lb_snat_delete(self, bigips, rm_pool=True, rm_port=True):
        lb_id = self.service['loadbalancer']['id']
        LOG.debug("Getting snat addrs for: %s" %
                  self.snat_net['subnets'])

        if rm_pool:
            snat_pool = self.driver.service_adapter.get_folder_name(lb_id)
            if self.l2_service.is_common_network(self.snat_net['network']):
                partition = 'Common'
            else:
                partition = self.partition

            for bigip in bigips:
                self.snat_manager.delete_flavor_snats(
                    bigip, partition, snat_pool
                )

        if rm_port:
            for subnet in self.snat_net['subnets']:
                snat_name = self.snat_manager.get_snat_name(
                    lb_id, subnet['ip_version'])

                # Large SNAT style need to delete network after delete port,
                # so that cast=False.
                if self.flavor in [11, 12, 13]:
                    cast = True
                else:
                    cast = False
                self.driver.plugin_rpc.delete_port_by_name(
                    port_name=snat_name, cast=cast)

    def snat_update(
        self, old_loadbalancer, loadbalancer
    ):
        bigips = self.service['bigips']
        self.snat_pools_exist()
        self.lb_snat_update(
            bigips, old_loadbalancer, loadbalancer
        )

    def lb_snat_update(
        self, bigips, old_loadbalancer, loadbalancer
    ):
        # Ensure snat for subnet exists on bigips
        lb_id = self.service['loadbalancer']['id']
        rd = self.snat_net["network"]["route_domain_id"]

        new_snat_addrs = set()

        for subnet in self.snat_net['subnets']:
            ip_version = subnet['ip_version']
            snat_name = self.snat_manager.get_snat_name(
                lb_id, ip_version)

            old_flavor = old_loadbalancer['flavor']
            new_flavor = loadbalancer['flavor']
            old_maxc = old_loadbalancer.get("max_concurrency", 0)
            new_maxc = loadbalancer.get("max_concurrency", 0)
            if old_flavor != new_flavor or \
               (old_flavor == new_flavor == 21 and old_maxc != new_maxc):
                old_port = self.driver.plugin_rpc.get_port_by_name(
                    port_name=snat_name
                )

                new_snats_per_subnet = self.count_SNATIPs(
                    ip_version, loadbalancer)

                if len(old_port) == 0:
                    raise Exception(
                        "Can not find SNAT port %s in Neutron" % snat_name
                    )

                if len(old_port) > 1:
                    LOG.warning(
                        "Find multiple SNAT port in Neutron %s \n" %
                        old_port
                    )
                    raise Exception(
                        "There should be one port with multiple IPs, "
                        "but we got multiple ports %s \n" % old_port
                    )

                old_port = old_port[0]
                if new_snats_per_subnet != len(old_port['fixed_ips']):
                    port = self.driver.plugin_rpc.update_port_on_subnet(
                        port_id=old_port['id'],
                        subnet_id=subnet['id'],
                        fixed_address_count=new_snats_per_subnet
                    )
                else:
                    port = old_port

                new_snat_addrs |= {
                    netinfo['ip_address'] + '%' + str(rd)
                    for netinfo in port['fixed_ips']
                }

        pool_name = self.driver.service_adapter.get_folder_name(
            lb_id
        )
        LOG.debug(
            "Update SNAT Pool %s to new SNAT IP %s" %
            (pool_name, new_snat_addrs)
        )
        if self.l2_service.is_common_network(self.snat_net['network']):
            partition = 'Common'
        else:
            partition = self.partition

        if new_snat_addrs:
            bigips = self.service['bigips']
            for bigip in bigips:
                self.snat_manager.update_flavor_snats(
                    bigip, partition, pool_name,
                    list(new_snat_addrs)
                )


class LargeSNATHelper(SNATHelper):

    def __init__(self, driver, service, lb_netinfo,
                 snat_manager, l2_service, **kwargs):
        super(LargeSNATHelper, self).__init__(
            driver, service, lb_netinfo, snat_manager, l2_service
        )
        self.net_service = kwargs.get("net_service")
        self.snat_network_type = kwargs.get("snat_network_type")

    def snat_create(self):
        # Create dedicated SNAT network
        self.create_large_snat_network()

        # Modify snat network information in memory and utilize
        # the existing code to allocate SNAT IPs
        self.snat_net["network"] = self.large_snat_network
        self.snat_net["subnets"] = []
        for key in self.large_snat_subnet:
            self.snat_net["subnets"].append(self.large_snat_subnet[key])

        super(LargeSNATHelper, self).snat_create()

        # SDN will assign vlan id after creating port with vtep ip in binding
        # profile. Have to create vlan in BIGIP after allocating SNAT address.
        self.create_vlan_selfip()

    def snat_update(
        self, old_loadbalancer, loadbalancer
    ):
        lb_id = self.service['loadbalancer']['id']
        network_name = "snat-" + lb_id
        subnet_v4_name = "snat-v4-" + lb_id
        subnet_v6_name = "snat-v6-" + lb_id
        rpc = self.driver.plugin_rpc

        # Get large SNAT network
        nets, netc = rpc.get_network_by_name(name=network_name)
        if netc != 1:
            raise Exception("Found %s snat networks %s",
                            netc, network_name)
        self.large_snat_network = nets[0]
        self.large_snat_network["route_domain_id"] = \
            self.snat_net["network"]["route_domain_id"]

        ip_versions = []
        for subnet in self.snat_net["subnets"]:
            if subnet["ip_version"] not in ip_versions:
                ip_versions.append(subnet["ip_version"])

        self.large_snat_subnet = {}
        # Get large SNAT subnets
        for ip_version in ip_versions:
            if ip_version == 4:
                snet4s, snet4c = rpc.get_subnet_by_name(name=subnet_v4_name)
                if snet4c != 1:
                    raise Exception("Found %s snat v4 subnets %s",
                                    snet4c, subnet_v4_name)
                self.large_snat_subnet[ip_version] = snet4s[0]
            if ip_version == 6:
                snet6s, snet6c = rpc.get_subnet_by_name(name=subnet_v6_name)
                if snet6c != 1:
                    raise Exception("Found %s snat v6 subnets %s",
                                    snet6c, subnet_v6_name)
                self.large_snat_subnet[ip_version] = snet6s[0]

        # Modify snat network information in memory and utilize
        # the existing code to allocate SNAT IPs
        self.snat_net["network"] = self.large_snat_network
        self.snat_net["subnets"] = []
        for key in self.large_snat_subnet:
            self.snat_net["subnets"].append(self.large_snat_subnet[key])

        super(LargeSNATHelper, self).snat_update(old_loadbalancer,
                                                 loadbalancer)

    def snat_remove(self, rm_pool=True, rm_port=True):
        # NOTE(qzhao): Must delete vlan in bigip before deleting
        # snat port in neutron, because SDN might deallocate vlan
        # id when removing snat port.

        self.delete_vlan_selfip()
        super(LargeSNATHelper, self).snat_remove(rm_pool, rm_port)
        self.delete_large_snat_network(rm_port)

    def create_large_snat_network(self, ip_version=4):
        tenant_id = self.service['loadbalancer']['tenant_id']
        lb_id = self.service['loadbalancer']['id']
        flavor = self.service["loadbalancer"].get("flavor")
        network_name = "snat-" + lb_id
        subnet_v4_name = "snat-v4-" + lb_id
        subnet_v6_name = "snat-v6-" + lb_id

        # Identify VIP router id
        vip_subnet_id = self.service['loadbalancer']['vip_subnet_id']
        router_id = self.driver.plugin_rpc.get_router_id_by_subnet(
            subnet_id=vip_subnet_id)

        if not router_id:
            raise Exception("No router found for subnet " + vip_subnet_id)

        # Create large SNAT network. SNAT network type can be vlan or vxlan.
        # It depends on SDN vendor's choice.
        body = {
            "tenant_id": tenant_id,
            "name": network_name,
            "shared": False,
            "admin_state_up": True,
            "provider:network_type":
                self.snat_network_type,
            "availability_zone_hints":
                self.snat_net["network"]["availability_zones"]
        }
        self.large_snat_network = self.driver.plugin_rpc.create_network(**body)
        snat_network_id = self.large_snat_network['id']

        self.large_snat_subnet = {}

        ip_versions = []
        for subnet in self.snat_net["subnets"]:
            if subnet["ip_version"] not in ip_versions:
                ip_versions.append(subnet["ip_version"])

        # Default SNAT subnet size is always 128 (7 length)
        subnet_size = 7

        # NOTE(qzhao): Legacy flavor 8 may already allocate 64 size subnet.
        # If any one of those subnet is missing, need to rebuild the subnet
        # with the same size.

        if flavor == 8:
            rpc = self.driver.plugin_rpc
            snet4s, snet4c = rpc.get_subnet_by_name(name=subnet_v4_name)
            snet6s, snet6c = rpc.get_subnet_by_name(name=subnet_v6_name)

            size4 = subnet_size
            size6 = subnet_size
            if snet4c > 0 and snet6c == 0:
                cidr4 = snet4s[0]["cidr"]
                size4 = 32 - int(cidr4.split("/")[-1])
            elif snet6c > 0 and snet4c == 0:
                cidr6 = snet6s[0]["cidr"]
                size6 = 128 - int(cidr6.split("/")[-1])

            subnet_size = min(subnet_size, size4, size6)

        LOG.debug("before creating and attaching for large SNAT")
        # Create large SNAT subnets
        for ip_version in ip_versions:
            if ip_version == 6:
                prefixlen = 128 - subnet_size
            else:
                prefixlen = 32 - subnet_size

            if ip_version == 6:
                pool_id = self.driver.conf.snat_subnetpool_v6
                subnet_name = subnet_v6_name
            else:
                pool_id = self.driver.conf.snat_subnetpool_v4
                subnet_name = subnet_v4_name

            self.large_snat_subnet[ip_version] = \
                self.driver.plugin_rpc.create_subnet(
                    name=subnet_name,
                    tenant_id=tenant_id,
                    network_id=snat_network_id,
                    ip_version=ip_version,
                    subnetpool_id=pool_id,
                    prefixlen=prefixlen,
                    cidr=None,
                    enable_dhcp=False,
                    allocation_pools=None,
                    dns_nameservers=None,
                    host_routes=None
                )

            # Attach VIP router
            self.driver.plugin_rpc.attach_subnet_to_router(
                router_id=router_id,
                subnet_id=self.large_snat_subnet[ip_version]['id']
            )
        LOG.debug("after creating and attaching for large SNAT")

        # Needn't create route domain
        # Only create snat vlan in VIP route domain
        self.large_snat_network["route_domain_id"] = \
            self.snat_net["network"]["route_domain_id"]

    def create_vlan_selfip(self):
        LOG.debug("before large snat vlan create")
        snat_network_id = self.large_snat_network['id']
        rd_id = self.large_snat_network["route_domain_id"]

        # Refresh snat network after creating snat port
        self.large_snat_network = \
            self.driver.plugin_rpc.get_network_by_id(id=snat_network_id)

        if "segments" in self.large_snat_network:
            for segment in self.large_snat_network["segments"]:
                if segment["provider:network_type"] == "vlan":
                    self.large_snat_network["provider:network_type"] = "vlan"
                    self.large_snat_network["provider:segmentation_id"] = \
                        segment["provider:segmentation_id"]
                    self.large_snat_network["provider:physical_network"] = \
                        segment["provider:physical_network"]

        if "provider:segmentation_id" not in self.large_snat_network:
            msg = "Missing vlan segmentation_id in network " + snat_network_id
            LOG.error(msg)
            raise Exception(msg)

        LOG.debug("large snat vlan id is %s",
                  str(self.large_snat_network["provider:segmentation_id"]))

        self.large_snat_network["route_domain_id"] = rd_id

        bigips = self.service['bigips']
        for bigip in bigips:
            self.l2_service.assure_bigip_network(
                bigip, self.large_snat_network,
                self.service['device']
            )
        LOG.debug("after large snat vlan create")

        LOG.debug("before large snat selfip create")
        # Create selfip in bigips
        self.net_service.config_selfips(
            self.service,
            network=self.large_snat_network,
            subnets=self.large_snat_subnet.values()
        )
        LOG.debug("after large snat selfip create")

    def delete_vlan_selfip(self):
        lb_id = self.service['loadbalancer']['id']
        subnet_v4_name = "snat-v4-" + lb_id
        subnet_v6_name = "snat-v6-" + lb_id

        bigips = self.service['bigips']

        # NOTE(qzhao): Delete SelfIP of SNAT subnet. Also need to gather vlan
        # name from selfip, because it is hard to query vlan id here from
        # Neutron, if SNAT network has multiple segments.
        s = SelfIP()
        vlans = []
        for name in [subnet_v4_name, subnet_v6_name]:
            subnets, _ = self.driver.plugin_rpc.get_subnet_by_name(name=name)
            for subnet in subnets:
                for bigip in bigips:
                    selfip = "local-" + bigip.device_name + "-" + subnet["id"]
                    ret = s.load(bigip, name=selfip, partition=self.partition,
                                 ignore=[404])
                    if ret:
                        vlan = ret.vlan[ret.vlan.index("/", 1) + 1::]
                        if vlan not in vlans:
                            vlans.append(vlan)
                        s.delete(bigip, name=selfip, partition=self.partition)

        # Delete SNAT vlan
        # TODO(qzhao): This implementation does not deleting vlans from F5OS.
        # Need to refactor the whole deleting procedure in the future.
        v = Vlan()
        for bigip in bigips:
            for vlan in vlans:
                v.delete(bigip, name=vlan, partition=self.partition)

    def delete_large_snat_network(self, rm_port=True):
        lb_id = self.service['loadbalancer']['id']
        network_name = "snat-" + lb_id
        subnet_v4_name = "snat-v4-" + lb_id
        subnet_v6_name = "snat-v6-" + lb_id

        # Identify VIP router id
        vip_subnet_id = self.service['loadbalancer']['vip_subnet_id']
        router_id = self.driver.plugin_rpc.get_router_id_by_subnet(
            subnet_id=vip_subnet_id)

        if not router_id:
            LOG.warning(
                "router %s not found for subnet %s" %
                (router_id, vip_subnet_id)
            )
            # raise Exception("No router found for subnet " + vip_subnet_id)

        # Detach VIP router
        if router_id and rm_port:
            self.driver.plugin_rpc.detach_subnet_from_router(
                router_id=router_id, subnet_name=subnet_v4_name)
            self.driver.plugin_rpc.detach_subnet_from_router(
                router_id=router_id, subnet_name=subnet_v6_name)

        bigips = self.service['bigips']

        # Delete SelfIP neutron port
        for name in [subnet_v4_name, subnet_v6_name]:
            subnets, _ = self.driver.plugin_rpc.get_subnet_by_name(name=name)
            for subnet in subnets:
                for bigip in bigips:
                    selfip = "local-" + bigip.device_name + "-" + subnet["id"]
                    if rm_port:
                        self.driver.plugin_rpc.delete_port_by_name(
                            port_name=selfip, cast=False)

        # Empty subnets can be deleted along with network
        if rm_port:
            self.driver.plugin_rpc.delete_network_by_name(
                name=network_name
            )
