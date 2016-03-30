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
import os

import constants_v2 as const
import netaddr
import os

from oslo_log import log as logging


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

    route_domain_defaults = {
        'name': None,
        'partition': '/' + const.DEFAULT_PARTITION,
        'id': 0,
        'strict': 'disabled',
    }

    def create_l2gre_multipoint_profile(self, bigip, name,
                                        partition=const.DEFAULT_PARTITION):
        p = bigip.net.tunnels_s.gres.gre
        if p.exists(name=name, partition=partition):
            p.load(name=name, partition=partition)
        else:
            payload = NetworkHelper.l2gre_multipoint_profile_defaults
            payload['name'] = name
            payload['partition'] = partition
            p.create(**payload)
        return p

    def create_vxlan_multipoint_profile(self, bigip, name,
                                        partition=const.DEFAULT_PARTITION):
        p = bigip.net.tunnels_s.vxlans.vxlan
        if p.exists(name=name, partition=partition):
            p.load(name=name, partition=partition)
        else:
            payload = NetworkHelper.vxlan_multipoint_profile_defaults
            payload['name'] = name
            payload['partition'] = partition
            p.create(**payload)
        return p

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
        t = bigip.net.tunnels_s.tunnels.tunnel
        if t.exists(name=payload['name'], partition=payload['partition']):
            t.load(name=payload['name'], partition=payload['partition'])
        else:
            t.create(**payload)
            if not payload['partition'] == const.DEFAULT_PARTITION:
                self.add_vlan_to_domain_by_id(bigip, payload['name'],
                                              payload['partition'],
                                              route_domain_id)
        return t

    def get_tunnel_key(self, bigip, name, partition=const.DEFAULT_PARTITION):
        t = bigip.net.tunnels_s.tunnels.tunnel
        t.load(name=name, partition=partition)
        return t.key

    def get_l2gre_tunnel_key(self, bigip, name,
                             partition=const.DEFAULT_PARTITION):
        return self.get_tunnel_key(bigip, name, partition)

    def get_vxlan_tunnel_key(self, bigip, name,
                             partition=const.DEFAULT_PARTITION):
        return self.get_tunnel_key(bigip, name, partition)

    def get_vlan_id(self, bigip, name, partition=const.DEFAULT_PARTITION):
        v = bigip.net.vlans.vlan
        v.load(name=name, partition=partition)
        return v.tag

    def get_selfip_addr(self, bigip, name, partition=const.DEFAULT_PARTITION):
        s = bigip.net.selfips.selfip
        s.load(name=name, partition=partition)
        return s.address

    # this method isn't present in the new f5-sdk
    def strip_folder_and_prefix(self, path):
        import os
        OBJ_PREFIX = 'uuid_'
        """ Strip folder and prefix """
        if isinstance(path, list):
            for i in range(len(path)):
                if path[i].find('~') > -1:
                    path[i] = path[i].replace('~', '/')
                if path[i].startswith('/Common'):
                    path[i] = path[i].replace(OBJ_PREFIX, '')
                else:
                    path[i] = \
                        os.path.basename(str(path[i])).replace(OBJ_PREFIX, '')
            return path
        else:
            if path.find('~') > -1:
                path = path.replace('~', '/')
            if path.startswith('/Common'):
                return str(path).replace(OBJ_PREFIX, '')
            else:
                return os.path.basename(str(path)).replace(OBJ_PREFIX, '')

    def get_selfips(self, bigip, partition=const.DEFAULT_PARTITION,
                    vlan_name=None):
        if not vlan_name.startswith('/'):
            vlan_name = "/%s/%s" % (partition, vlan_name)
        sc = bigip.net.selfips
        params = {'params': {'$filter': 'partition eq %s' % partition}}
        selfips = sc.get_collection(requests_params=params)
        selfips_list = []
        for selfip in selfips:
            if vlan_name and selfip.vlan != vlan_name:
                continue
            selfip.name = self.strip_folder_and_prefix(selfip.name)
            selfips_list.append(selfip)
        return selfips_list

    def delete_selfip(self, bigip, name, partition=const.DEFAULT_PARTITION):
        """Delete the selfip if it exists. """
        s = bigip.net.selfips.selfip
        if s.exists(name=name, partition=partition):
            s.load(name=name, partition=partition)
            s.delete()

    def route_domain_exists(self, bigip, partition=const.DEFAULT_PARTITION,
                            domain_id=None):
        if partition == 'Common':
            return True
        r = bigip.net.route_domains.route_domain
        name = partition
        if domain_id:
            name += '_aux_' + str(domain_id)
        return r.exists(name=name, partition=partition)

    def get_route_domain(self, bigip, partition=const.DEFAULT_PARTITION):
        # this only works when the domain was created with is_aux=False,
        # same as the original code.
        if partition == 'Common':
            name = '0'
        else:
            name = partition
        r = bigip.net.route_domains.route_domain
        r.load(name=name, partition=partition)
        return r

    def get_route_domain_by_id(self, bigip, partition=const.DEFAULT_PARTITION,
                               id=const.DEFAULT_ROUTE_DOMAIN_ID):
        ret_rd = None
        rdc = bigip.net.route_domains
        params = {}
        if partition:
            params = {'params': {'$filter': 'partition eq %s' % partition}}
        route_domains = rdc.get_collection(requests_params=params)
        for rd in route_domains:
            if rd.id == id:
                ret_rd = rd
                break
        return ret_rd

    def _get_next_domain_id(self, bigip):
        """Get next route domain id """
        rd_ids = sorted(self.get_route_domain_ids(bigip, partition=''))
        rd_ids.remove(0)

        lowest_available_index = 1
        for i in range(len(rd_ids)):
            if rd_ids[i] < lowest_available_index:
                if len(rd_ids) > (i + 1):
                    if rd_ids[i + 1] > lowest_available_index:
                        return lowest_available_index
                    else:
                        lowest_available_index = lowest_available_index + 1
            elif rd_ids[i] == lowest_available_index:
                lowest_available_index = lowest_available_index + 1
        else:
            return lowest_available_index

    def create_route_domain(self, bigip, partition=const.DEFAULT_PARTITION,
                            strictness=False, is_aux=False):
        rd = bigip.net.route_domains.route_domain
        name = partition
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
        rd.create(**payload)
        return rd

    def delete_route_domain(self, bigip, partition=const.DEFAULT_PARTITION,
                            name=None):
        r = bigip.net.route_domains.route_domain
        if not name:
            name = partition
        r.load(name=name, partition=partition)
        r.delete()

    def get_route_domain_ids(self, bigip, partition=const.DEFAULT_PARTITION):
        rdc = bigip.net.route_domains
        params = {}
        if partition:
            params = {'params': {'$filter': 'partition eq %s' % partition}}
        route_domains = rdc.get_collection(requests_params=params)
        rd_ids_list = []
        for rd in route_domains:
            rd_ids_list.append(rd.id)
        return rd_ids_list

    def get_route_domain_names(self, bigip, partition=const.DEFAULT_PARTITION):
        rdc = bigip.net.route_domains
        params = {}
        if partition:
            params = {'params': {'$filter': 'partition eq %s' % partition}}
        route_domains = rdc.get_collection(requests_params=params)
        rd_names_list = []
        for rd in route_domains:
            rd_names_list.append(rd.name)
        return rd_names_list

    def get_vlans_in_route_domain(self,
                                  bigip,
                                  partition=const.DEFAULT_PARTITION):
        """Get VLANs in Domain """
        rd = self.get_route_domain(bigip, partition)
        return getattr(rd, 'vlans', [])

    def create_vlan(self, bigip, model):
        name = model.get('name', None)
        partition = model.get('partition', const.DEFAULT_PARTITION)
        tag = model.get('tag', 0)
        description = model.get('description', None)
        route_domain_id = model.get('route_domain_id',
                                    const.DEFAULT_ROUTE_DOMAIN_ID)
        if not name:
            return None
        v = bigip.net.vlans.vlan
        if v.exists(name=name, partition=partition):
            v.load(name=name, partition=partition)
        else:
            payload = {'name': name,
                       'partition': partition,
                       'tag': tag}
            if description:
                payload['description'] = description
            v.create(**payload)
            interface = model.get('interface', None)
            if interface:
                payload = {'name': interface,
                           ('tagged' if tag else 'untagged'): True}
                i = v.interfaces_s.interfaces
                i.create(**payload)
            if not partition == const.DEFAULT_PARTITION:
                self.add_vlan_to_domain_by_id(bigip, name, partition,
                                              route_domain_id)
        return v

    def delete_vlan(
            self,
            bigip,
            name,
            partition=const.DEFAULT_PARTITION):
        """Delete VLAN from partition."""
        v = bigip.net.vlans.vlan
        if v.exists(name=name, partition=partition):
            v.load(name=name, partition=partition)
            v.delete()

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
        rd.vlans = existing_vlans
        rd.update()
        return True

    def add_vlan_to_domain_by_id(self, bigip, name,
                                 partition=const.DEFAULT_PARTITION,
                                 id=const.DEFAULT_ROUTE_DOMAIN_ID):
        """Add VLANs to Domain by ID."""
        rd = self.get_route_domain_by_id(bigip, partition, id)
        existing_vlans = getattr(rd, 'vlans', [])
        if name in existing_vlans:
            return False

        existing_vlans.append(name)
        rd.vlans = existing_vlans
        rd.update()
        return True

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

    def arp_delete_by_mac(self,
                          bigip,
                          mac_address,
                          partition=const.DEFAULT_PARTITION):
        """Delete arp using the mac address."""
        ac = bigip.net.arps.get_collection()
        for arp in ac:
            if arp.macAddress == mac_address:
                arp.delete()

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
                LOG.error('ARP', exc.message)
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

        return self._delete_by_network(bigip, partition, network)

    def _delete_by_network(self, bigip, partition, network):
        """Delete for network """
        if not network:
            return []
        mac_addresses = []
        ac = bigip.net.arps
        params = {'params': {'$filter': 'partition eq %s' % partition}}
        arps = ac.get_collection(requests_params=params)
        for arp in arps:
            ad_rd_div = arp.ipAddress.find('%')
            if ad_rd_div > -1:
                address = netaddr.IPAddress(arp.ipAddress[0:ad_rd_div])
            else:
                address = netaddr.IPAddress(arp.ipAddress)

            if address in network:
                mac_addresses.append(arp.macAddress)
                arp.delete()
        return mac_addresses

    def get_snatpool_member_use_count(self, bigip, member_name):
        snat_count = 0
        snatpools = bigip.ltm.snatpools.get_collection()
        for snatpool in snatpools:
            for member in snatpool.members:
                if member_name == os.path.basename(member):
                    snat_count += 1
        return snat_count

    def split_addr_port(self, dest):
        if len(dest.split(':')) > 2:
            # ipv6: bigip syntax is addr.port
            parts = dest.split('.')
        else:
            # ipv4: bigip syntax is addr:port
            parts = dest.split(':')
        return (parts[0], parts[1])

    def get_virtual_service_insertion(
            self,
            bigip,
            partition=const.DEFAULT_PARTITION):
        """Get a list of virtual servers."""
        vs = bigip.ltm.virtuals
        virtual_services = vs.get_collection()
        services = []

        for virtual_server in virtual_services:
            service = {'name': {}}
            dest = os.path.basename(virtual_server.destination)
            (vip_addr, vip_port) = self.split_addr_port(dest)

            name = self.strip_folder_and_prefix(virtual_server.name)
            service[name]['address'] = vip_addr
            service[name]['netmask'] = virtual_server.mask
            service[name]['protocol'] = virtual_server.ipProtocol
            service[name]['port'] = vip_port
            services.append(service)

        return services

    def get_node_addresses(self, bigip, partition=const.DEFAULT_PARTION):
        """Get the addresses of nodes within the partition."""
        nodes = bigip.ltm.nodes.get_collection()

        node_addrs = []
        for node in nodes:
            node_addrs.append(node.address)

        return node_addrs

    def add_fdb_entry(
            self,
            bigip,
            tunnel_name,
            partition=const.DEFAULT_PARTITION,
            mac_address=None,
            vtep_ip_address=None,
            arp_ip_address=None):
        pass

    def delete_fdb_entry(
            self,
            bigip,
            partition=const.DEFAULT_PARTITION,
            mac_address=None,
            tunnel_name=None,
            arp_ip_address=None):
        pass

    def delete_all_fdb_entries(
            self,
            bigip,
            tunnel_name,
            partition=const.DEFAULT_PARTITION):
        """Delete all fdb entries."""
        t = bigip.net.fdb.tunnels.tunnel
        t.load(name=tunnel_name, partition=partition)
        LOG.debug(t.raw)
        t.update(records=None)

    def delete_tunnel(
            self,
            bigip,
            tunnel_name,
            partition=const.DEFAULT_PARTITION):
        """Deletes a vxlan or gre tunnel."""
        t = bigip.net.fdb.tunnels.tunnel
        if t.exists(name=tunnel_name, partition=partition):
            t.load(name=tunnel_name, partition=partition)

            if const.FDB_POPULATE_STATIC_ARP:
                for record in t.records:
                    self.arp_delete_by_mac(
                        bigip,
                        record.name,
                        partition=partition
                    )

                t.update(records=[])

        ts = bigip.net.fdb.tunnels_s.tunnels.tunnel
        ts.load(name=tunnel_name, partition=partition)
        ts.delete()
