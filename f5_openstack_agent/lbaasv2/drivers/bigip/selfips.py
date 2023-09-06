# coding=utf-8
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

import constants_v2 as const
import netaddr
from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import RouteDomain
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import SelfIP
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import VirtualAddress
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import VirtualServer
from f5_openstack_agent.lbaasv2.drivers.bigip import utils
from requests import HTTPError

LOG = logging.getLogger(__name__)


class BigipSelfIpManager(object):

    def __init__(self, driver, l2_service, l3_binding):
        self.driver = driver
        self.l2_service = l2_service
        self.l3_binding = l3_binding
        self.network_helper = NetworkHelper()

    def _create_bigip_selfip(self, bigip, model):
        selfip = SelfIP()
        try:
            selfip.create(bigip, model)
        except HTTPError as err:
            if (err.response.status_code == 400 and
                err.response.text.find(
                    "must be one of the vlans "
                    "in the associated route domain") > 0):
                try:
                    rd_id = utils.vlan_to_rd_id(model['vlan'])
                    r = RouteDomain()
                    r.add_vlan_by_id(bigip, rd_id, model["vlan"],
                                     model["partition"])
                    selfip.create(bigip, model)
                except HTTPError as err:
                    LOG.exception("After bind vlan to route domain. "
                                  "Error creating selfip %s. " %
                                  model["name"])
                    raise f5_ex.SelfIPCreationException(err.messgae)
            else:
                LOG.error("selfip creation error message: %s" %
                          err.message)
                LOG.error("selfip creation error status: %s" %
                          err.response.status_code)
                LOG.error("selfip creation error text: %s" %
                          err.response.text)
                raise
        except Exception as err:
            LOG.error("Failed to create selfip")
            LOG.exception(err.message)
            raise f5_ex.SelfIPCreationException("selfip creation")

    def assure_bigip_selfip(self, bigip, service, subnetinfo, vlan_mac):
        u"""Ensure the BigIP has a selfip address on the tenant subnet."""

        network = None
        subnet = None

        if 'network' in subnetinfo:
            network = subnetinfo['network']
        if 'subnet' in subnetinfo:
            subnet = subnetinfo['subnet']

        if not network or not subnet:
            LOG.error('Attempted to create selfip and snats '
                      'for network with not id...')
            raise KeyError("network and subnet need to be specified")

        tenant_id = service['loadbalancer']['tenant_id']
        lb_id = service['loadbalancer']['id']

        # If we have already assured this subnet.. return.
        # Note this cache is periodically cleared in order to
        # force assurance that the configuration is present.
        if tenant_id in bigip.assured_tenant_snat_subnets and \
                subnet['id'] in bigip.assured_tenant_snat_subnets[tenant_id]:
            return True

        device = service['device']
        # llinfo is a list of dict type
        llinfo = device['device_info'].get('local_link_information', None)

        if llinfo:
            link_info = llinfo[0]
        else:
            link_info = dict()
            llinfo = [link_info]

        link_info.update({"lb_mac": vlan_mac})
        binding_profile = {
             "local_link_information": llinfo
        }

        selfip_address = self._get_bigip_selfip_address(
            bigip, subnet, lb_id, binding_profile)
        if 'route_domain_id' not in network:
            LOG.error("network route domain is not set")
            raise KeyError()

        selfip_address += '%' + str(network['route_domain_id'])

        if self.l2_service.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = self.driver.service_adapter.\
                get_folder_name(service['loadbalancer']['tenant_id'])

        # Get the name of the vlan.
        (network_name, preserve_network_name) = \
            self.l2_service.get_network_name(
                bigip, network, service['device'])

        netmask = netaddr.IPNetwork(subnet['cidr']).prefixlen
        address = selfip_address + ("/%d" % netmask)
        name = "local-" + bigip.device_name \
            + "-" + subnet['id']
        model = {
            "name": name,
            "address": address,
            "vlan": network_name,
            "floating": "disabled",
            "partition": network_folder
        }
        self._create_bigip_selfip(bigip, model)

        if self.l3_binding:
            self.l3_binding.bind_address(subnet_id=subnet['id'],
                                         ip_address=selfip_address)

    def _get_bigip_selfip_address(
            self, bigip, subnet, lb_id, binding_profile
    ):
        u"""Ensure a selfip address is allocated on Neutron network."""

        # Get ip address for selfip to use on BIG-IP.
        if self.driver.conf.unlegacy_setting_placeholder:
            LOG.debug('setting vnic_type to normal instead of baremetal')
            vnic_type = "normal"
        else:
            vnic_type = "baremetal"

        selfip_address = ""
        selfip_name = "local-" + bigip.device_name + "-" + subnet['id']
        ports = self.driver.plugin_rpc.get_port_by_name(port_name=selfip_name)
        if len(ports) > 0:
            port = utils.update_port(
                ports[0], binding_profile,
                self.driver.plugin_rpc
            )
        else:
            host_passed = None
            if self.driver.conf.separate_host:
                LOG.info('using separate_host:')
                LOG.info(bigip.device_name)
                host_passed = bigip.device_name
            LOG.info('host_passed here is:')
            LOG.info(host_passed)

            port = self.driver.plugin_rpc.create_port_on_subnet(
                subnet_id=subnet['id'],
                name=selfip_name,
                fixed_address_count=1,
                device_id=lb_id,
                vnic_type=vnic_type,
                binding_profile=binding_profile,
                host_passed=host_passed
            )

        if port and 'fixed_ips' in port:
            fixed_ip = port['fixed_ips'][0]
            selfip_address = fixed_ip['ip_address']

        return selfip_address

    # TODO(clean) no one use this anymore, delete the code
    def assure_gateway_on_subnet(self, bigip, subnetinfo, traffic_group):
        """Ensure """
        network = None
        subnet = None

        if 'network' in subnetinfo:
            network = subnetinfo['network']
        if 'subnet' in subnetinfo:
            subnet = subnetinfo['subnet']

        if not network or not subnet:
            raise KeyError("network and subnet must be specified to create "
                           "gateway on subnet.")

        if not subnet['gateway_ip']:
            raise KeyError("attempting to create gateway on subnet without "
                           "gateway ip address specified.")

        if subnet['id'] in bigip.assured_gateway_subnets:
            return True

        (network_name, preserve_network_name) = \
            self.l2_service.get_network_name(bigip, network)

        if self.l2_service.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = self.driver.service_adapter.\
                get_folder_name(subnet['tenant_id'])

        # Create a floating SelfIP for the given traffic-group.
        floating_selfip_name = "gw-" + subnet['id']
        netmask = netaddr.IPNetwork(subnet['cidr']).prefixlen
        address = subnet['gateway_ip'] + "%" + str(network['route_domain_id'])
        address += ("/%d" % (netmask))
        model = {
            'name': floating_selfip_name,
            'address': address,
            'vlan': network_name,
            'floating': True,
            'traffic-group': traffic_group,
            'partition': network_folder
        }

        self._create_bigip_selfip(bigip, model)

        if self.l3_binding:
            self.l3_binding.bind_address(subnet_id=subnet['id'],
                                         ip_address=subnet['gateway_ip'])

        # Setup a wild card ip forwarding virtual service for this subnet
        gw_name = "gw-" + subnet['id']
        vs = VirtualServer()
        if not vs.exists(bigip, name=gw_name, partition=network_folder):
            try:
                vs.create(bigip, {
                    "name": gw_name,
                    "partition": network_folder,
                    "destination": "0.0.0.0:0",
                    "mask": "0.0.0.0",
                    "vlansEnabled": True,
                    "vlans": [network_name],
                    "sourceAddressTranslation": {"type": "automap"},
                    "ipForward": True
                })
            except Exception as err:
                LOG.exception(err)
                raise f5_ex.VirtualServerCreationException(
                    "Failed to create gateway virtual service on subnet %s",
                    subnet['id']
                )

        # Put the virtual server address in the specified traffic group
        virtual_address = VirtualAddress()
        try:
            virtual_address.update(bigip, {
                "name": "0.0.0.0",
                "partition": network_folder,
                "trafficGroup": traffic_group
            })
        except Exception as err:
            LOG.exception(err)
            raise f5_ex.VirtualServerCreationException(
                "Failed to add virtual address to traffic group %s",
                traffic_group)

        # bigip.assured_gateway_subnets.append(subnet['id'])

    def delete_gateway_on_subnet(self, bigip, subnetinfo):
        network = None
        subnet = None

        if 'network' in subnetinfo:
            network = subnetinfo['network']
        if 'subnet' in subnetinfo:
            subnet = subnetinfo['subnet']

        if not network or not subnet:
            LOG.error('Attempted to create selfip and snats '
                      'for network with no id...')
            raise KeyError("network and subnet must be specified")

        if not subnet['gateway_ip']:
            raise KeyError("attempting to create gateway on subnet without "
                           "gateway ip address specified.")

        if self.l2_service.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = self.driver.service_adapter.\
                get_folder_name(subnet['tenant_id'])

        if self.driver.conf.f5_populate_static_arp:
            self.network_helper.arp_delete_by_subnet(
                bigip,
                partition=network_folder,
                subnet=subnetinfo['subnet']['cidr'],
                mask=None
            )

        floating_selfip_name = "gw-" + subnet['id']
        self.delete_selfip(
            bigip, floating_selfip_name, network_folder)

        if self.l3_binding:
            self.l3_binding.unbind_address(subnet_id=subnet['id'],
                                           ip_address=subnet['gateway_ip'])

        gw_name = "gw-" + subnet['id']
        vs = VirtualServer()
        try:
            vs.delete(name=gw_name, partition=network_folder)
        except Exception as err:
            LOG.exception(err)
            raise f5_ex.VirtualServerDeleteException(
                "Failed to delete gateway service on subnet %s", subnet['id'])

        if subnet['id'] in bigip.assured_gateway_subnets:
            bigip.assured_gateway_subnets.remove(subnet['id'])

        return gw_name

    def get_selfip_addr(self, bigip, name, partition=const.DEFAULT_PARTITION):
        selfip_addr = ""
        try:
            s = SelfIP()
            if s.exists(bigip, name=name, partition=partition):
                obj = s.load(bigip, name=name, partition=partition)

                # The selfip address on BigIP is actually a network,
                # parse out the address portion.
                if obj.address:
                    (selfip_addr, netbits) = obj.address.split("/")

        except HTTPError as err:
            LOG.exception("Error getting selfip address for %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (name,
                                            err.response.status_code,
                                            err.message))
        except Exception:
            LOG.exception("Error getting selfip address for %s.", name)

        return selfip_addr

    def get_selfips(self, bigip, partition=const.DEFAULT_PARTITION,
                    vlan_name=None):
        selfips_list = []

        if vlan_name:
            if not vlan_name.startswith('/'):
                vlan_name = "/%s/%s" % (partition, vlan_name)

        try:
            s = SelfIP()
            selfips_list = [
                selfip
                for selfip in s.get_resources(bigip, partition=partition)
                if vlan_name == selfip.vlan or not vlan_name
            ]
        except HTTPError as err:
            LOG.exception("Error getting selfips for vlan(%s). "
                          "Response status code: %s. "
                          "Response message: %s." % (
                              vlan_name,
                              err.response.status_code,
                              err.message))
            raise f5_ex.SelfIPQueryException(
                "Failed to get selfips assigned to vlan")

        return selfips_list

    def delete_selfip(self, bigip, name, partition=const.DEFAULT_PARTITION):
        """Delete the selfip if it exists."""
        try:
            s = SelfIP()
            s.delete(bigip, name=name, partition=partition)
        except HTTPError as err:
            LOG.exception("Error deleting selfip %s. "
                          "Response status code: %s. Response "
                          "message: %s." % (name,
                                            err.response.status_code,
                                            err.message))
            raise f5_ex.SelfIPDeleteException(
                "Failed to delete selfip %s." % name)
