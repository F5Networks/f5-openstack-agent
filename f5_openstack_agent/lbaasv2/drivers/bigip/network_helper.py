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

    def get_route_domain(self, bigip, partition):
        # this only works when the domain was created with is_aux=False,
        # same as the original code.
        if partition == 'Common':
            name = '0'
        else:
            name = partition
        r = bigip.net.route_domains.route_domain
        r.load(name=name, partition=partition)
        return r

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

    def add_vlan_to_domain(self,
                           bigip,
                           name,
                           partition=const.DEFAULT_PARTITION):
        """Add VLANs to Domain """
        rd = self.get_route_domain(bigip, partition)
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
        rdc = bigip.net.route_domains
        params = {'params': {'$filter': 'partition eq %s' % partition}}
        route_domains = rdc.get_collection(requests_params=params)
        rds_list = []
        for rd in route_domains:
            if rd.id == id:
                # there can be only one...
                rds_list.append(rd)
                break
        vlans = []
        if not rds_list:
            return vlans
        rd = rds_list[0]
        if getattr(rd, 'vlans', None):
            for vlan in rd.vlans:
                vlans.append(vlan)
        return vlans

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
            except Exception:
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
            except Exception:
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
