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
import os
import urllib

from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from requests.exceptions import HTTPError

from f5.bigip.tm.net.vlan import TagModeDisallowedForTMOSVersion
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import get_filter

LOG = logging.getLogger(__name__)


class NetworkHelper(object):

    l2gre_multipoint_profile_defaults = {
        'name': None,
        'partition': const.DEFAULT_PARTITION,
        'defaultsFrom': 'gre',
        'floodingType': 'multipoint',
        'encapsulation': 'transparent-ethernet-bridging'
    }

    vxlan_multipoint_profile_defaults = {
        'name': None,
        'partition': const.DEFAULT_PARTITION,
        'defaultsFrom': 'vxlan',
        'floodingType': 'multipoint',
        'port': const.VXLAN_UDP_PORT
    }

    ppp_profile_defaults = {
        'name': None,
        'partition': const.DEFAULT_PARTITION,
        'defaultsFrom': 'ppp',
        'floodingType': 'none',
    }

    route_domain_defaults = {
        'name': None,
        'partition': '/' + const.DEFAULT_PARTITION,
        'id': 0,
        'strict': 'disabled',
    }

    route_defaults = {
        'name': None,
        'partition': '/' + const.DEFAULT_PARTITION,
    }

    def __init__(self, conf=None):
        if conf:
            self.conf = conf

    @log_helpers.log_method_call
    def create_l2gre_multipoint_profile(self, bigip, name,
                                        partition=const.DEFAULT_PARTITION):
        p = bigip.tm.net.tunnels.gres.gre
        if p.exists(name=name, partition=partition):
            obj = p.load(name=name, partition=partition)
        else:
            payload = NetworkHelper.l2gre_multipoint_profile_defaults
            payload['name'] = name
            payload['partition'] = partition
            obj = p.create(**payload)
        return obj

    @log_helpers.log_method_call
    def create_vxlan_multipoint_profile(self, bigip, name,
                                        partition=const.DEFAULT_PARTITION):
        p = bigip.tm.net.tunnels.vxlans.vxlan
        if p.exists(name=name, partition=partition):
            obj = p.load(name=name, partition=partition)
        else:
            payload = NetworkHelper.vxlan_multipoint_profile_defaults
            payload['name'] = name
            payload['partition'] = partition
            obj = p.create(**payload)
        return obj

    @log_helpers.log_method_call
    def create_ppp_profile(self, bigip, name,
                           partition=const.DEFAULT_PARTITION):
        pf = bigip.tm.net.tunnels.ppps.ppp
        if pf.exists(name=name, partition=partition):
            p = pf.load(name=name, partition=partition)
        else:
            payload = NetworkHelper.ppp_profile_defaults
            payload['name'] = name
            payload['partition'] = partition
            p = pf.create(**payload)
        return p

    @log_helpers.log_method_call
    def create_tunnel(self, bigip, model):
        payload = {'name': model.get('name', None),
                   'partition': model.get('partition',
                                          const.DEFAULT_PARTITION),
                   'profile': model.get('profile', None)}
        description = model.get('description', None)
        if description:
            payload['description'] = description
        tf = bigip.tm.net.tunnels.tunnels.tunnel
        if tf.exists(name=payload['name'], partition=payload['partition']):
            t = tf.load(name=payload['name'], partition=payload['partition'])
        else:
            t = tf.create(**payload)
        return t

    @log_helpers.log_method_call
    def create_multipoint_tunnel(self, bigip, model):
        payload = {'name': model.get('name', None),
                   'partition': model.get('partition',
                                          const.DEFAULT_PARTITION),
                   'profile': model.get('profile', None),
                   'key': model.get('key', 0),
                   'localAddress': model.get('localAddress', None),
                   'remoteAddress': model.get('remoteAddress', '0.0.0.0')}
        description = model.get('description', None)
        if description:
            payload['description'] = description
        route_domain_id = model.pop('route_domain_id',
                                    const.DEFAULT_ROUTE_DOMAIN_ID)
        t = bigip.tm.net.tunnels.tunnels.tunnel
        if t.exists(name=payload['name'], partition=payload['partition']):
            obj = t.load(name=payload['name'], partition=payload['partition'])
        else:
            obj = t.create(**payload)
            if not payload['partition'] == const.DEFAULT_PARTITION:
                self.add_vlan_to_domain_by_id(bigip, payload['name'],
                                              payload['partition'],
                                              route_domain_id)
        return obj

    @log_helpers.log_method_call
    def get_tunnel_key(self, bigip, name, partition=const.DEFAULT_PARTITION):
        t = bigip.tm.net.tunnels.tunnels.tunnel
        obj = t.load(name=name, partition=partition)
        return obj.key

    def get_l2gre_tunnel_key(self, bigip, name,
                             partition=const.DEFAULT_PARTITION):
        return self.get_tunnel_key(bigip, name, partition)

    def get_vxlan_tunnel_key(self, bigip, name,
                             partition=const.DEFAULT_PARTITION):
        return self.get_tunnel_key(bigip, name, partition)

    @log_helpers.log_method_call
    def get_vlan_id(self, bigip, name, partition=const.DEFAULT_PARTITION):
        v = bigip.tm.net.vlans.vlan
        obj = v.load(name=name, partition=partition)
        return obj.tag

    @log_helpers.log_method_call
    def get_selfip_addr(self, bigip, name, partition=const.DEFAULT_PARTITION):
        try:
            s = bigip.tm.net.selfips.selfip
            if s.exists(name=name, partition=partition):
                obj = s.load(name=name, partition=partition)
                return obj.address
        except HTTPError as err:
            LOG.error("Error getting selfip address for %s. "
                      "Repsponse status code: %s. Response "
                      "message: %s." % (name,
                                        err.response.status_code,
                                        err.message))
        return None

    def _get_route_domain_name(self, name):
        # Returns the properly formatted route domain name
        # for external_gateway_mode, it should be rd-{}
        if hasattr(self, 'conf') and self.conf.external_gateway_mode and not \
                name.startswith('rd-'):
            rd_fmt = 'rd-{0}'
        else:
            rd_fmt = '{0}'
        return rd_fmt.format(name)

    def _get_route_name(self, name=None):
        # Returns the properly formatted route name
        # Not implemented for any other scenario besides external_gateway_mode
        if not hasattr(self, 'conf') or \
                not self.conf.external_gateway_mode:
            raise NotImplementedError("Routes are not implemented outside of"
                                      "common networks!")
        return "rt-{}".format(name) if name and not name.startswith('rt-') \
            else name

    def route_domain_exists(self, bigip, partition=const.DEFAULT_PARTITION,
                            domain_id=None, name=None):
        """Returns True if the Route Domain exists on the bigip else False

        This method will attempt to extract whether or not the Route Domain
        exists off of the BIG-IP and return a boolean.
        args:
            bigip - should be a f5.bigip.RootManager object instance
        kwargs:
            partition - default is Common - a string that contains the name of
                the tenant's partition
            domain_id - int containing the domain's id
            name - str containing the name of the route domain; otherwise
                default is used
        """
        if partition == 'Common' and \
                (not hasattr(self, 'conf') or
                 not self.conf.external_gateway_mode):
            return True
        name = self._get_route_domain_name(name) if name else partition
        r = bigip.tm.net.route_domains.route_domain
        if domain_id:
            name += '_aux_' + str(domain_id)
        return r.exists(name=name, partition=partition)

    @log_helpers.log_method_call
    def get_route_domain(self, bigip, partition=const.DEFAULT_PARTITION,
                         name=None):
        """Returns a Route Domain object as extracted from the BIG-IP

        This metod will take the bigip and extract the Route Domain object from
        it.  It will then return this object to the caller.
        """
        # this only works when the domain was created with is_aux=False,
        # same as the original code.
        if hasattr(self, 'conf') and self.conf.external_gateway_mode:
            name = self._get_route_domain_name(name) if name else partition
        elif partition == 'Common':
            name = '0'
        else:
            name = partition
        r = bigip.tm.net.route_domains.route_domain
        return r.load(name=name, partition=partition)

    @log_helpers.log_method_call
    def get_route_domain_by_id(self, bigip, partition=const.DEFAULT_PARTITION,
                               id=const.DEFAULT_ROUTE_DOMAIN_ID):
        """Returns the route domain by id

        This takes in an id and attempts to find the domain by ID and partition
        off of the BIG-IP and returns the Route Domain object.
        args:
            bigip - should be a f5.bigip.RootManager object instance
        kwargs:
            partition - default is Common - a str that contains the name of the
                tenant's partition
            domain_id - int containing the domain's id
        """
        ret_rd = None
        rdc = bigip.tm.net.route_domains
        params = {}
        if partition:
            params = {
                'params': get_filter(bigip, 'partition', 'eq', partition)
            }
        route_domains = rdc.get_collection(requests_params=params)
        for rd in route_domains:
            if rd.id == id:
                ret_rd = rd
                break
        return ret_rd

    @log_helpers.log_method_call
    def _get_next_domain_id(self, bigip):
        """Get next route domain id """
        rd_ids = sorted(self.get_route_domain_ids(bigip, partition=''))
        rd_ids.remove(0)

        lowest_available_index = 1
        for i in range(len(rd_ids)):
            if lowest_available_index < rd_ids[i]:
                break
            elif rd_ids[i] == lowest_available_index:
                lowest_available_index = lowest_available_index + 1
            else:
                raise LookupError(
                    "The list of route domain ids is out of order")

        return lowest_available_index

    @log_helpers.log_method_call
    def create_route_domain(self, bigip, partition=const.DEFAULT_PARTITION,
                            strictness=False, is_aux=False, name=None):
        """Creates the route domain based upon settings in config

        This method will create the Route Domain object per partition in the
        standard case; however, in common networking configuration, it will
        create a Route Domain on the Common partition labeling it by:
            rd-h<name given>

        args:
            bigip - f5.bigip.RootManager object instance
        kwargs:
            partition - name of the partition
            strictness - level of strictness setting
            is_aux - whether or not it is 'aux' in definition
            name - name of the RD as it should have
        """
        if name and self.conf.external_gateway_mode:
            name = self._get_route_domain_name(name)
        else:
            name = partition
        rd = bigip.tm.net.route_domains.route_domain
        id = self._get_next_domain_id(bigip)
        if is_aux:
            name += '_aux_' + str(id)
        payload = NetworkHelper.route_domain_defaults
        payload['name'] = name
        payload['partition'] = '/' + partition
        payload['id'] = id
        if strictness:
            payload['strict'] = 'enabled'
        else:
            payload['parent'] = '/' + const.DEFAULT_PARTITION + '/0'
        return rd.create(**payload)

    @log_helpers.log_method_call
    def delete_route_domain(self, bigip, partition=const.DEFAULT_PARTITION,
                            name=None):
        """Deletes the route domain off of the bigip instance

        This will attempt to delete the provided Route Domain from off of the
        BIG-IP.

        args:
            bigip - f5.bigip.RootManager object instance
        kwargs:
            partition - name of the partition
            strictness - level of strictness setting
            name - name of the RD as it should have
        """
        if hasattr(self, 'conf') and self.conf.external_gateway_mode:
            name = self._get_route_domain_name(name) if name else partition
        else:
            name = partition
        r = bigip.tm.net.route_domains.route_domain
        obj = r.load(name=name, partition=partition)
        obj.delete()

    @log_helpers.log_method_call
    def get_route_domain_ids(self, bigip, partition=const.DEFAULT_PARTITION):
        rdc = bigip.tm.net.route_domains
        params = {}
        if partition:
            params = {
                'params': get_filter(bigip, 'partition', 'eq', partition)
            }
        route_domains = rdc.get_collection(requests_params=params)
        rd_ids_list = []
        for rd in route_domains:
            rd_ids_list.append(rd.id)
        return rd_ids_list

    @log_helpers.log_method_call
    def get_route_domain_names(self, bigip, partition=const.DEFAULT_PARTITION):
        rdc = bigip.tm.net.route_domains
        params = {}
        if partition:
            params = {
                'params': get_filter(bigip, 'partition', 'eq', partition)
            }
        route_domains = rdc.get_collection(requests_params=params)
        rd_names_list = []
        for rd in route_domains:
            rd_names_list.append(rd.name)
        return rd_names_list

    @log_helpers.log_method_call
    def route_exists(self, bigip, partition=const.DEFAULT_PARTITION,
                     name=None):
        """Returns whether or not the Route object exists on the BIG-IP

        This object method will attempt to load the Route object from the
        BIG-IP using the F5 CCCL library.  If the Route does not exist on the
        BIG-IP, then it will return False else True.
        Args:
            bigip - f5.bigip.RootManager object instance
        Kwargs:
            partition - name of the partition (or tenant)
            name - name of the Route object on the BIG-IP
        """
        name = self._get_route_name(name)
        rc = bigip.tm.net.routes.route
        return rc.exists(name=name, partition=partition)

    @log_helpers.log_method_call
    def get_route(self, bigip, partition=const.DEFAULT_PARTITION, name=None):
        """Returns the BIG-IP Route object as per its name and partition"""
        payload = {'name': self._get_route_name(name), 'partition': partition}
        rc = bigip.tm.net.routes.route
        return rc.load(**payload)

    @log_helpers.log_method_call
    def create_route(self, bigip, name=None, partition=const.DEFAULT_PARTITION,
                     gateway_ip='0.0.0.0', rd_id=0, destination_ip='0.0.0.0',
                     netmask='255.255.255.0'):
        """Creates the Route object on the BIG-IP

        This object method will attempt to create the provided Route object on
        the BIG-IP provided.

        Args:
            bigip - f5.bigip.RootManager object instance
        Kwargs:
            partition - partition name
            name - name of the Route object on the BIG-IP
        """
        name = self._get_route_name(name)
        if self.route_exists(bigip, name=name, partition=partition):
            LOG.info(str("Skipping create of route {} as it already exists!"
                         ).format(name))
            return
        rc = bigip.tm.net.routes.route
        destination_ip = '{}%{}/{}'.format(destination_ip, rd_id, netmask)
        gateway_ip = '{}%{}'.format(gateway_ip, rd_id)

        payload = NetworkHelper.route_defaults.copy()
        payload.update(dict(name=name, partition=partition, gw=gateway_ip,
                            network=destination_ip))
        rc.create(**payload)

    @log_helpers.log_method_call
    def delete_route(self, bigip, name=None,
                     partition=const.DEFAULT_PARTITION):
        """Deletes the provided Route off of the BIG-IP

        This method will attempt to take the name and partition and delete it
        from the provided bigip.
        Args:
            bigip - f5.bigip.RootManager obj instnace
        Kwargs:
            partition - name of the partition (or tenant)
            name - name of the Route that is to be deleted
        """
        payload = {'partition': partition, 'name': self._get_route_name(name)}
        if not self.route_exists(bigip, **payload):
            return
        route = self.get_route(bigip, **payload)
        route.delete()

    @log_helpers.log_method_call
    def get_vlans_in_route_domain(self,
                                  bigip,
                                  partition=const.DEFAULT_PARTITION):
        """Get VLANs in Domain """
        rd = self.get_route_domain(bigip, partition)
        return getattr(rd, 'vlans', [])

    @log_helpers.log_method_call
    def create_vlan(self, bigip, model):
        name = model.get('name', None)
        partition = model.get('partition', const.DEFAULT_PARTITION)
        tag = model.get('tag', 0)
        description = model.get('description', None)
        route_domain_id = model.get('route_domain_id',
                                    const.DEFAULT_ROUTE_DOMAIN_ID)
        if not name:
            return None
        v = bigip.tm.net.vlans.vlan
        if v.exists(name=name, partition=partition):
            obj = v.load(name=name, partition=partition)
        else:
            payload = {'name': name,
                       'partition': partition,
                       'tag': tag}

            if description:
                payload['description'] = description
            obj = v.create(**payload)
            interface = model.get('interface', None)
            if interface:
                payload = {'name': interface}
                if tag:
                    payload['tagged'] = True
                else:
                    payload['untagged'] = True

                i = obj.interfaces_s.interfaces
                try:
                    i.create(**payload)
                except TagModeDisallowedForTMOSVersion as e:
                    # Providing the tag-mode is not supported
                    LOG.warn(e.message)
                    i.create(**payload)

            if not partition == const.DEFAULT_PARTITION:
                self.add_vlan_to_domain_by_id(bigip, name, partition,
                                              route_domain_id)
        return obj

    @log_helpers.log_method_call
    def delete_vlan(
            self,
            bigip,
            name,
            partition=const.DEFAULT_PARTITION):
        """Delete VLAN from partition."""
        v = bigip.tm.net.vlans.vlan
        if v.exists(name=name, partition=partition):
            obj = v.load(name=name, partition=partition)
            obj.delete()

    @log_helpers.log_method_call
    def add_vlan_to_domain(
            self,
            bigip,
            name,
            partition=const.DEFAULT_PARTITION):
        """Add VLANs to Domain."""
        rd = self.get_route_domain(bigip, partition)
        existing_vlans = getattr(rd, 'vlans', [])
        if name in existing_vlans:
            return False

        existing_vlans.append(name)
        rd.modify(vlans=existing_vlans)
        return True

    @log_helpers.log_method_call
    def add_vlan_to_domain_by_id(self, bigip, name,
                                 partition=const.DEFAULT_PARTITION,
                                 id=const.DEFAULT_ROUTE_DOMAIN_ID):
        """Add VLANs to Domain by ID."""
        rd = self.get_route_domain_by_id(bigip, partition, id)
        if rd:
            existing_vlans = getattr(rd, 'vlans', [])
            if name in existing_vlans:
                return False
        else:
            return False
        existing_vlans.append(name)
        rd.modify(vlans=existing_vlans)
        return True

    @log_helpers.log_method_call
    def get_vlans_in_route_domain_by_id(self, bigip,
                                        partition=const.DEFAULT_PARTITION,
                                        id=const.DEFAULT_ROUTE_DOMAIN_ID):
        rd = self.get_route_domain_by_id(bigip, partition, id)
        vlans = []
        if not rd:
            return vlans
        if getattr(rd, 'vlans', None):
            for vlan in rd.vlans:
                vlans.append(vlan)
        return vlans

    @log_helpers.log_method_call
    def arp_delete_by_mac(self,
                          bigip,
                          mac_address,
                          partition=const.DEFAULT_PARTITION):
        """Delete arp using the mac address."""
        ac = bigip.tm.net.arps.get_collection(partition=partition)
        for arp in ac:
            if arp.macAddress == mac_address:
                arp.delete()

    @log_helpers.log_method_call
    def arp_delete(self,
                   bigip,
                   ip_address,
                   partition=const.DEFAULT_PARTITION):
        if ip_address:
            address = urllib.quote(self._remove_route_domain_zero(ip_address))
            arp = bigip.tm.net.arps.arp
            try:
                if arp.exists(name=address, partition=partition):
                    obj = arp.load(name=address, partition=partition)
                    obj.delete()
            except HTTPError as err:
                LOG.error("Error deleting arp %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (address,
                                            err.response.status_code,
                                            err.message))

            return True

        return False

    @log_helpers.log_method_call
    def arp_delete_by_subnet(self, bigip, subnet=None, mask=None,
                             partition=const.DEFAULT_PARTITION):
        if not subnet:
            return []
        mask_div = subnet.find('/')
        if mask_div > 0:
            try:
                rd_div = subnet.find('%')
                if rd_div > -1:
                    network = netaddr.IPNetwork(
                        subnet[0:mask_div][0:rd_div] + subnet[mask_div:])
                else:
                    network = netaddr.IPNetwork(subnet)
            except Exception as exc:
                LOG.error('arp_delete_by_subnet', exc.message)
                return []
        elif not mask:
            return []
        else:
            try:
                rd_div = subnet.find('%')
                if rd_div > -1:
                    network = netaddr.IPNetwork(subnet[0:rd_div] + '/' + mask)
                else:
                    network = netaddr.IPNetwork(subnet + '/' + mask)
            except Exception as exc:
                LOG.error('ARP', exc.message)
                return []

        return self._arp_delete_by_network(bigip, partition, network)

    @log_helpers.log_method_call
    def _arp_delete_by_network(self, bigip, partition, network):
        """Delete ARP entry if address in network"""
        if not network:
            return []
        mac_addresses = []
        ac = bigip.tm.net.arps
        params = {'params': get_filter(bigip, 'partition', 'eq', partition)}
        try:
            arps = ac.get_collection(requests_params=params)
        except HTTPError as err:
            LOG.error("Error getting ARPs."
                      "Repsponse status code: %s. Response "
                      "message: %s." % (err.response.status_code,
                                        err.message))
            return mac_addresses

        for arp in arps:
            address_index = arp.ipAddress.find('%')
            if address_index > -1:
                address = netaddr.IPAddress(arp.ipAddress[0:address_index])
            else:
                address = netaddr.IPAddress(arp.ipAddress)

            if address in network:
                mac_addresses.append(arp.macAddress)
                try:
                    arp.delete()
                except HTTPError as err:
                    LOG.error("Error deleting ARP %s."
                              "Repsponse status code: %s. Response "
                              "message: %s." % (arp.ipAddress,
                                                err.response.status_code,
                                                err.message))
        return mac_addresses

    @log_helpers.log_method_call
    def split_addr_port(self, dest):
        if len(dest.split(':')) > 2:
            # ipv6: bigip syntax is addr.port
            parts = dest.split('.')
        else:
            # ipv4: bigip syntax is addr:port
            parts = dest.split(':')
        return (parts[0], parts[1])

    @log_helpers.log_method_call
    def get_virtual_service_insertion(
            self,
            bigip,
            partition=const.DEFAULT_PARTITION):
        """Returns list of virtual server addresses"""
        vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        va_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)
        virtual_servers = vs_helper.get_resources(bigip, partition=partition)
        virtual_services = []

        for virtual_server in virtual_servers:
            name = virtual_server.name
            virtual_address = {name: {}}
            dest = os.path.basename(virtual_server.destination)
            (vip_addr, vip_port) = self.split_addr_port(dest)

            # Get virtual address associated with the virtual server.
            # split_addr_port can return a tuple where the vip addr is either
            # a name of the virt address, or the actual IP address.
            # This code gets a reference to the virt address in the event the
            # virtual server destination is a named resource, not an IP addr.
            try:
                vaddr = va_helper.load(
                    bigip, name=vip_addr, partition=partition)
            except HTTPError:
                continue
            else:
                # there was no exception: legit VA, so use address from VA
                vip_addr = vaddr.raw['address']

            virtual_address[name]['address'] = vip_addr
            virtual_address[name]['netmask'] = virtual_server.mask
            virtual_address[name]['protocol'] = virtual_server.ipProtocol
            virtual_address[name]['port'] = vip_port
            virtual_services.append(virtual_address)

        return virtual_services

    @log_helpers.log_method_call
    def get_node_addresses(self, bigip, partition=const.DEFAULT_PARTITION):
        """Get the addresses of nodes within the partition."""
        nodes = bigip.tm.ltm.nodes.get_collection(partition=partition)

        node_addrs = []
        for node in nodes:
            node_addrs.append(node.address)

        return node_addrs

    @log_helpers.log_method_call
    def add_fdb_entry(
            self,
            bigip,
            tunnel_name,
            mac_address=None,
            vtep_ip_address=None,
            arp_ip_address=None,
            partition=const.DEFAULT_PARTITION):

        try:
            tunnel = bigip.tm.net.fdb.tunnels.tunnel
            if tunnel.exists(name=tunnel_name, partition=partition):
                obj = tunnel.load(name=tunnel_name, partition=partition)
                if not obj.records_s.records.exists(name=mac_address):
                    obj.records_s.records.create(
                        name=mac_address, endpoint=vtep_ip_address)
                    if const.FDB_POPULATE_STATIC_ARP:
                        # arp_ip_address is typcially member address.
                        if arp_ip_address:
                            try:
                                LOG.debug("Creating ARP with IP address %s and"
                                          "MAC addess %s" % (arp_ip_address,
                                                             mac_address))
                                arp = bigip.tm.net.arps.arp
                                arp.create(ipAddress=arp_ip_address,
                                           macAddress=mac_address,
                                           partition=partition,
                                           name=mac_address)
                            except Exception as e:
                                LOG.error('add_fdb_entry',
                                          'could not create static arp: %s'
                                          % e.message)
                                return False
                return True
            else:
                LOG.debug("Tunnel %s does not exist." % tunnel_name)
        except HTTPError as err:
            LOG.error("Error checking tunnel %s. "
                      "Repsponse status code: %s. Response "
                      "message: %s." % (tunnel_name,
                                        err.response.status_code,
                                        err.message))
        return False

    @log_helpers.log_method_call
    def delete_fdb_entry(
            self,
            bigip,
            mac_address=None,
            tunnel_name=None,
            arp_ip_address=None,
            partition=const.DEFAULT_PARTITION):

        if const.FDB_POPULATE_STATIC_ARP and arp_ip_address:
            self.arp_delete(bigip,
                            ip_address=arp_ip_address,
                            partition=partition)
        try:
            tunnel = bigip.tm.net.fdb.tunnels.tunnel
            if tunnel.exists(name=tunnel_name, partition=partition):
                obj = tunnel.load(name=tunnel_name, partition=partition)
                r = obj.records_s.records
                if r.exists(name=mac_address):
                    r = r.load(name=mac_address)
                    r.delete()

        except HTTPError as err:
            LOG.error("Error updating tunnel %s. "
                      "Repsponse status code: %s. Response "
                      "message: %s." % (tunnel_name,
                                        err.response.status_code,
                                        err.message))

    @log_helpers.log_method_call
    def add_fdb_entries(self, bigip, fdb_entries=None):
        # Add vxlan fdb entries
        for tunnel_name in fdb_entries:
            folder = fdb_entries[tunnel_name]['folder']
            tunnel_records = fdb_entries[tunnel_name]['records']
            for mac in tunnel_records:
                record = tunnel_records[mac]
                ip_address = record['ip_address']
                if ip_address == '0.0.0.0':
                    ip_address = ''
                self.add_fdb_entry(
                    bigip,
                    tunnel_name,
                    mac_address=mac,
                    vtep_ip_address=record['endpoint'],
                    arp_ip_address=ip_address,
                    partition=folder)

    @log_helpers.log_method_call
    def delete_fdb_entries(self, bigip, fdb_entries=None):
        for tunnel_name in fdb_entries:
            folder = fdb_entries[tunnel_name]['folder']
            tunnel_records = fdb_entries[tunnel_name]['records']
            for mac in tunnel_records:
                self.delete_fdb_entry(
                    bigip,
                    tunnel_name=tunnel_name,
                    mac_address=mac,
                    partition=folder)

    @log_helpers.log_method_call
    def get_fdb_entry(self,
                      bigip,
                      tunnel_name=None,
                      mac=None,
                      partition=const.DEFAULT_PARTITION):

        try:
            tunnel = bigip.tm.net.fdb.tunnels.tunnel
            if tunnel.exists(name=tunnel_name, partition=partition):
                obj = tunnel.load(name=tunnel_name, partition=partition)
                records = obj.records_s.get_collection()
                if mac is None:
                    return records

                for record in records:
                    if record['name'] == mac:
                        LOG.debug("FOUND RECORD for MAC %s" % mac)
                        return record

        except Exception as err:
            LOG.error("Error in get_fdb_entry"
                      "Repsponse status code: %s. Response "
                      "message: %s." % (err.response.status_code,
                                        err.message))

        return []

    @log_helpers.log_method_call
    def delete_all_fdb_entries(
            self,
            bigip,
            tunnel_name,
            partition=const.DEFAULT_PARTITION):
        """Delete all fdb entries."""
        try:
            t = bigip.tm.net.fdb.tunnels.tunnel
            obj = t.load(name=tunnel_name, partition=partition)
            obj.modify(records=None)
        except HTTPError as err:
            LOG.error("Error deleting all fdb entries %s. "
                      "Repsponse status code: %s. Response "
                      "message: %s." % (tunnel_name,
                                        err.response.status_code,
                                        err.message))

    @log_helpers.log_method_call
    def delete_tunnel(
            self,
            bigip,
            tunnel_name,
            partition=const.DEFAULT_PARTITION):
        """Delete a vxlan or gre tunnel."""
        t = bigip.tm.net.fdb.tunnels.tunnel
        try:
            if t.exists(name=tunnel_name, partition=partition):
                obj = t.load(name=tunnel_name, partition=partition)

                if const.FDB_POPULATE_STATIC_ARP and hasattr(obj, "records"):
                    for record in obj.records:
                        self.arp_delete_by_mac(
                            bigip,
                            record['name'],
                            partition=partition
                        )

                    obj.modify(records=[])
        except HTTPError as err:
            LOG.error("Error updating tunnel %s. "
                      "Repsponse status code: %s. Response "
                      "message: %s." % (tunnel_name,
                                        err.response.status_code,
                                        err.message))

        try:
            ts = bigip.tm.net.tunnels.tunnels.tunnel
            if ts.exists(name=tunnel_name, partition=partition):
                obj = ts.load(name=tunnel_name, partition=partition)
                obj.delete()
        except HTTPError as err:
            LOG.error("Error deleting tunnel %s. "
                      "Repsponse status code: %s. Response "
                      "message: %s." % (tunnel_name,
                                        err.response.status_code,
                                        err.message))

    @log_helpers.log_method_call
    def get_tunnel_folder(self, bigip, tunnel_name=None):
        tunnels = bigip.tm.net.fdb.tunnels.get_collection()
        for tunnel in tunnels:
            if tunnel.name == tunnel_name:
                return tunnel.partition

        return None

    def _remove_route_domain_zero(self, ip_address):
        """Remove route domain zero from ip_address """
        decorator_index = ip_address.find('%0')
        if decorator_index > 0:
            ip_address = ip_address[:decorator_index]
        return ip_address

    def get_route_domain_count(self, bigip, partition=''):
        """Return number of route domains, exluding route domain 0"""
        route_domain_ids = self.get_route_domain_ids(
            bigip, partition=partition)
        if 0 in route_domain_ids:
            route_domain_ids.remove(0)
        return len(route_domain_ids)

    def get_tunnel_count(self, bigip, partition='/'):
        """Return sum of VXLAN and GRE tunnels"""
        all_tunnels = bigip.tm.net.tunnels.tunnels.get_collection(
            partition=partition)

        tunnels = [item for item in all_tunnels if
                   item.profile.find('vxlan') > 0 or
                   item.profile.find('gre') > 0]
        return len(tunnels)

    def get_vlan_count(self, bigip, partition='/'):
        """Return number of VLANs"""
        return len(bigip.tm.net.vlans.get_collection(partition=partition))
