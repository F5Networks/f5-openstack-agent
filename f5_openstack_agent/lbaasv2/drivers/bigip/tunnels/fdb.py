"""An fdb library housing orchestration means to perform fdb_entries' updates

This library houses the appropriate classes to orchestrate updating fdb vtep
entries.  This library utilizes other, neighboring libraries to accomplish its
task and relies heavily on tunnel logic.
"""
# Copyright 2018 F5 Networks Inc.
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

import re
import socket

from requests import HTTPError

from oslo_log import log as logging

import f5_openstack_agent.lbaasv2.drivers.bigip.l2_service as l2_service
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.decorators \
    as wrapper
# import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.tunnel as tunnel_mod

LOG = logging.getLogger(__name__)


class Fdb(object):
    """Stores pertinant information for an FDB entry manipulation

    This object stores an FDB entry's single-port entry for FDB VTEP
    manipulation from an L2 Population event.

    As such, this object only performs basic validation against each of the
    fields stored within it and returns them when called upon.

    Each value is a read-only value from the caller's prospective.

    Object is deemed as "incomplete" and dismissable if it evaluates as False.
    """
    _false_mac_re = re.compile('^[0:]+$')
    _mac_match_re = re.compile('^[a-zA-Z0-9:]+$')
    _network_id_re = re.compile('^[a-zA-Z0-9\-]+$')
    _route_domain_re = re.compile('%(\d+)$')

    @wrapper.add_logger
    def __init__(self, ip_address, vtep_mac, vtep_ip, network_id,
                 network_type, segment_id, force=False):
        self.network_id = network_id
        self.network_type = network_type
        self.segment_id = segment_id
        self.mac_address = vtep_mac
        route_domain_match = self._route_domain_re.search(ip_address)
        if route_domain_match:
            ip_address = self._route_domain_re.sub('', ip_address)
            self.route_domain = route_domain_match.group(1)
        self._set_ip_address(ip_address, force=force)
        self.vtep_ip = vtep_ip
        self.__partitions = []
        self.__hosts = []

    def __str__(self):
        """Returns string representation of object"""
        value = str("{s.fdb_entry}").format(s=self)
        return value

    def __repr__(self):
        return str("Fdb({s.network_id}: {s.segment_id}: "
                   "{s.ip_address}: {s.record})").format(s=self)

    @staticmethod
    def __is_valid_ip(addr):
        # Returns True if a valid IP address; else false
        try:
            socket.inet_aton(addr)
            return True
        except socket.error:
            return False

    @classmethod
    def __is_nonzero_mac(cls, mac):
        # Returns True if mac is not 00:00:00:00:00:00
        return False if cls._false_mac_re.search(mac) else True

    def __nonzero__(self):
        """Evaluates the VTEP to see if it is valid"""
        return self.__is_nonzero_mac(self.mac_address)

    def _set_route_domain(self, route_domain):
        self._route_domain = int(route_domain)

    def _get_route_domain(self):
        return getattr(self, '_route_domain', 0)

    @wrapper.only_one
    @wrapper.ip_address
    def _set_ip_address(self, addr):
        """Validates and sets given IP Address"""
        self.__ip_address = addr

    def _get_ip_address(self):
        """Returns stored IP Address"""
        return self.__ip_address

    @wrapper.only_one
    @wrapper.not_none
    def _set_segment_id(self, segment_id):
        """Validates and sets given segmentation ID"""
        self.__segment_id = int(segment_id)

    def _get_segment_id(self):
        """Returns stored segmentation ID"""
        return str(self.__segment_id)

    @wrapper.only_one
    def _set_mac_address(self, mac_addr):
        """Validates and sets given mac_address"""
        match = self._mac_match_re.search(mac_addr)
        if not match:
            raise TypeError("Invalid MAC Address: ({})".format(mac_addr))
        self.__mac_address = mac_addr

    def _get_mac_address(self):
        """Returns stored mac address"""
        return self.__mac_address

    @wrapper.only_one
    @wrapper.ip_address
    def _set_vtep_ip(self, vtep):
        """Validates and sets Fdb's vtep_ip"""
        if self.__is_valid_ip(vtep) is False:
            raise TypeError("Invalid IP Address: ({})".format(vtep))
        self.__vtep_ip = vtep

    def _get_vtep_ip(self):
        """Returns stored vtep's IP address"""
        return self.__vtep_ip

    @wrapper.only_one
    def _set_network_id(self, network_id):
        """Validates and sets network's ID"""
        if not self._network_id_re.search(network_id):
            raise TypeError("Not a valid network_id ({})".format(network_id))
        self.__network_id = network_id

    def _get_network_id(self):
        """Returns stored network's ID"""
        return self.__network_id

    @wrapper.only_one
    def _set_network_type(self, network_type):
        """Validates and sets network's type"""
        if network_type not in ['gre', 'vxlan']:
            raise TypeError(
                "Not a valid network type ({})".format(network_type))
        self.__network_type = network_type

    def _get_network_type(self):
        """Returns stored network's Type (vxlan, gre)"""
        return self.__network_type

    @property
    def record(self):
        return dict(endpoint=self.vtep_ip, name=self.mac_address)

    @property
    def fdb_entry(self):
        ports = [{self.ip_address: [[self.mac_address, self.vtep_ip]]}]
        return dict(
            ports=ports, segmentation_id=self.segment_id,
            network_id=self.network_id, network_type=self.network_type)

    @property
    def hosts(self):
        """Returns the list of BIG-IP hostnames linked to this FDB VTEP"""
        return self.__hosts

    @property
    def partitions(self):
        """Returns the list of BIG-IP partitions linked to this FDB VTEP"""
        return self.__partitions

    @property
    def is_valid(self):
        """Returns whether or not the FDB object is pertinent to a BIG-IP"""
        return self.hosts and self.partitions

    def log_create(self, bigip, partition):
        self.logger.debug(
            "Successfully Created Fdb({b.hostname}, {} {s.ip_address}("
            "{s.mac_address}, {s.vtep_ip})".format(
                partition, b=bigip, s=self))

    def log_remove(self, bigip, partition):
        self.logger.debug(
            "Successfully Removed Fdb({b.hostname}, {} {s.ip_address}("
            "{s.mac_address}, {s.vtep_ip})".format(
                partition, b=bigip, s=self))

    ip_address = property(_get_ip_address, _set_ip_address)
    segment_id = property(_get_segment_id, _set_segment_id)
    mac_address = property(_get_mac_address, _set_mac_address)
    vtep_ip = property(_get_vtep_ip, _set_vtep_ip)
    network_id = property(_get_network_id, _set_network_id)
    network_type = property(_get_network_type, _set_network_type)
    route_domain = property(_get_route_domain, _set_route_domain)


class FdbBuilder(object):
    """Library class for creating, manipulating, and altering Fdb's

    This library class is meant to only orchestrate Fdb objects, but can use
    Tunnel, TunnelHandler, and f5.bigip.ManagementRoot objects to do so.
    """

    def __init__(self):
        raise NotImplementedError("This class is not meant to be "
                                  "instantiated")

    @staticmethod
    def __tm_arp(bigip, tunnel, fdb, action):
        tm_arp = bigip.tm.net.arps.arp
        partition = tunnel.partition
        mac_address = fdb.mac_address
        ip_address = fdb.ip_address
        load_payload = dict(name=mac_address, partition=partition)
        create_payload = dict(ipAddress=ip_address, macAddress=mac_address,
                              partition=partition)
        actions = {'load': dict(payload=load_payload, method=tm_arp.load),
                   'create': dict(payload=create_payload,
                                  method=tm_arp.create),
                   'modify': dict(payload=load_payload, method=tm_arp.load),
                   'delete': dict(payload=load_payload, method=tm_arp.load)}
        laction = actions[action]
        fdb.logger.debug(
            "Performing {} on bigip.tm.net.arps.arp for ({t.partition}, "
            "{f.mac_address}, {f.ip_address}) on {b.hostname}".format(
                action, f=fdb, t=tunnel, b=bigip))
        arp = laction['method'](**laction['payload'])
        if action in ['delete', 'modify']:
            if action == 'delete':
                arp.delete()
                return None
            elif action == 'modify':
                # should be extremely rare...
                arp.modify(**actions['create']['payload'])
        return arp

    @classmethod
    def __tm_arps(cls, bigip, action='get_collection', tunnel=None, fdb=None):
        tm_arps = bigip.tm.net.arps
        if fdb and action in ['load', 'modify', 'create']:
            return cls.__tm_arp(bigip, tunnel, fdb, action)
        elif fdb and action == 'get_collection':
            partition = fdb.partition
        elif tunnel and action == 'get_collection':
            partition = tunnel.partition
        else:
            raise ValueError("Improper combination ({}, {} and {})".format(
                tunnel, fdb, action))
        params = {'params': dict(filter="partition eq {}".format(partition))}
        return tm_arps.get_collection(requests_params=params)

    @staticmethod
    def _check_entries(tunnel_handler, bigips, fdbs):
        """Checks the given list(Fdb) instances against the network

        This staticmethod will orchestrate the needed steps to collect a dict
        of BIG-IP hostnames, each with a list of valid Fdb/VTEP arps to
        update.

        Args:
            tunnel_handler - the tunnels.tunnel.TunnelHandler instance for
                the runtime agent
            fdbs - a list(Fdb) objects that hold the port VTEPs to be updated
        Returns:
            hosts - dict(bigip.hostname=[Fdb])
        """
        fdbs = filter(lambda x: x, fdbs)
        return tunnel_handler.check_fdbs(bigips, fdbs)

    @classmethod
    def _update_bigips(cls, bigips, hosts, remove=False):
        """Performs updates on the BIG-IP's by hosts with remove or add

        This staticmethod will call the bigip.tm.net.fdb.tunnels.tunnel.load
        and use this object to update the BIG-IP's tunnel record with the
        given FdbVTEPS.  It will also orchestrate the
        bigip.tm.net.arps.arp.create, delete, or update as needed.

        Args:
            bigips - list(f5.bigip.ManagementRoot) instances
            fdbs - a list(Fdb) objects that hold the port VTEPs to be updated
            hosts - a dict(bigip.hostname: [{fdb: Fdb, tunnel: tunnel}])
        Returns:
            None
        Expected Exceptions:
            requests.HTTPError - something bad happened in a POST or GET with
                the bigip being updated
        """
        bigips_by_hostname = {x.hostname: x for x in bigips}
        for host in hosts:
            tunnels, fdbs = hosts[host]
            for tunnel in tunnels:
                tunnel.add_fdbs(bigips_by_hostname[host], fdbs)

    @classmethod
    def _consolidate_entries(cls, fdb_entries, network_id=None,
                             tunnel_type=None, segment_id=None,
                             ip_address=None):
        """Performs consolidation of fdb_entries' raw dict form to Fdb's

        This staticmethod will consolidate the list of fdb_entries into a list
        of Fdb object instances.  These instances are then what's used to
        house all data relating to individual fdb's.

        Args:
            fdb_entries - {network_id, segment_id, ports: {ip: [[mac, ip]]},
                           network_type}
        """
        LOG.debug("Received fdb entries: {}".format(fdb_entries))

        keys = fdb_entries.keys() if isinstance(fdb_entries, dict) else []

        def generate_fdb(fdb_entry):
            fdbs = list()
            vtep_mac, vtep_ip = fdb_entry
            fdbs.append(
                Fdb(ip_address, vtep_mac, vtep_ip, network_id,
                    tunnel_type, segment_id))
            return fdbs

        if isinstance(fdb_entries, list):
            fdbs = list()
            for fdb_entry in fdb_entries:
                LOG.debug("Calling generate_fdb({})".format(fdb_entry))
                fdbs.extend(generate_fdb(fdb_entry))
        elif keys and 'segment_id' in fdb_entries[keys[0]]:
            fdbs = []
            for network_id in keys:
                fdb_entry = fdb_entries[network_id]
                added_payload = dict(
                    network_id=network_id,
                    segment_id=fdb_entry.pop('segment_id'),
                    tunnel_type=fdb_entry.pop('network_type'))
                fdb_ports = fdb_entry.pop('ports')
                LOG.debug("calling _consolidate_entries"
                          "({}, {})".format(fdb_ports, added_payload))
                fdbs.extend(cls._consolidate_entries(
                    fdb_ports, **added_payload))
        elif isinstance(fdb_entries, dict):
            fdbs = list()
            for ip_address in keys:
                added_payload = dict(
                    ip_address=ip_address, network_id=network_id,
                    segment_id=segment_id, tunnel_type=tunnel_type)
                fdb_address = fdb_entries.get(ip_address)
                LOG.debug("calling _consolidate_entries"
                          "({}, {})".format(fdb_address, added_payload))
                fdbs.extend(cls._consolidate_entries(
                    fdb_entries.get(ip_address), **added_payload))
        return fdbs

    @classmethod
    def handle_fdbs(cls, fdb_entry, tunnel_handler, bigips,
                    remove=False):
        """Performs operations to update fdb_entries on the BIG-IP's given

        This classmethod will attempt to handle the CUD operation of an L2
        population event for one or more vteps in a given fdb_entry.

        This method will also handle updating the tunnel_rpc of any created
        tunnels.

        Args:
            fdb_entry - a {network_id, segment_id, ports: {ip: [[mac, ip]]},
                           network_type}
                L2 Population-event given listing of vteps.
            tunnel_handler - the single instance of the
                tunnels.tunnel.TunnelHandler object (weakref) from the
                AgentManager.
            bigips - a [f5.bigip.ManagementRoot] instances
        KWArgs:
            remove - bool that informs the BIG-IP to remove (True) or create
                (False) the provided VTEP arps from the tunnel
        """
        fdbs = cls._consolidate_entries(fdb_entry)
        hosts = cls._check_entries(tunnel_handler, bigips, fdbs)
        cls._update_bigips(bigips, hosts, remove)
        tunnel_handler.notify_vtep_existence(hosts)

    @classmethod
    @wrapper.weakref_handle
    def handle_fdbs_by_loadbalancer_and_members(
            cls, bigip, tunnel, loadbalancer, members, remove=False):
        """Creates a list of fdb's from a loadbalancer/members values pair

        When network_service determines that a loadbalancer is new and with it
        a list of members, this will take that loadbalancer and list of
        members and add the resulting fdbs to the provided tunnel.

        Args:
            bigips - [f5.bigip.ManagementRoot] object instances
            tunnel - Tunnel object instance
            loadbalancer - service request's loadbalancer object
            members - list of member objects
        Returns:
            [Fdb] object instances
        """
        vtep_key = "{}_vteps".format(tunnel.tunnel_type)

        def create_fdb_by_vtep(tunnel, network, ip_address, mac,
                               vtep_address, force=False):
            fdb = Fdb(ip_address, mac, vtep_address, network['id'],
                      tunnel.tunnel_type, tunnel.segment_id, force=force)
            return fdb

        fdbs = list()
        if loadbalancer:
            network = loadbalancer['network']
        else:
            network = members[0]['network']
        loadbalancer_vteps = loadbalancer.get(vtep_key, []) if loadbalancer \
            else []
        for vtep_address in loadbalancer_vteps:
            fake_mac = l2_service.get_tunnel_fake_mac(network, vtep_address)
            fdbs.append(
                create_fdb_by_vtep(tunnel, network, '', fake_mac,
                                   vtep_address, force=True))
        for member in members:
            mac = member.get('port', {}).get('mac_address', None)
            addr = member.get('address', None)
            vteps = member.get(vtep_key, [])
            my_id = member.get('id', 'ID not supplied')
            member_str = "member({}), [mac: {}, ip: {}]".format(
                my_id, mac, addr)
            if not mac or not addr:
                message = str(
                    "Was unable to generate Fdb for new  {}".format(
                        member_str))
                if vteps:
                    message += " [{}]".format(vteps)
                    LOG.error(message)
                else:
                    LOG.debug(message)
                continue
            LOG.debug("Creating Fdb's for {} [{}]".format(member_str, vteps))
            for vtep_address in vteps:
                fdbs.append(
                    create_fdb_by_vtep(
                        tunnel, network, addr, mac, vtep_address))
        tunnel_method = tunnel.remove_fdbs if remove else tunnel.add_fdbs
        tunnel_method(bigip, fdbs)

    @classmethod
    def create_fdbs_from_bigip_records(cls, bigip, records, tunnel):
        """Grab all records of object aware in the tunnel (added fdb_entries)

        This method is multi-faceted in that it will...
            - Grab the existing ARP objects
            - Grab the existing tunnel records
            - Consolidate VTEP MAC's with ARP entries
            - Return the list of matched Fdb objects

        It should be noted that it is expected that there will be more records
        than ARP entries as the network primatives including the gateway,
        SNAT, NAT, and neutron-created ports will exist on the tunnel.  These
        artifacts are used to actually route the traffic.

        NOTE: this is a forced refresh from known state on the BIG-IP; thus,
        this is extremely HEAVY and it is recommended to be used sparingly

        Args:
            records - list of tm_fdb_tunnel.records from the BIG-IP (raw)
            tunnel - a Tunnel object associated with the tm_fdb_tunnel object
        Returns:
            None
        """
        network_id = tunnel.network_id
        segment_id = tunnel.segment_id
        tunnel_type = tunnel.tunnel_type
        fdbs = list()
        existing_arps = cls.__tm_arps(bigip, tunnel=tunnel,
                                      action='get_collection')
        existing_arps = {x.endpoint: x.name for x in existing_arps}
        for record in records:
            vtep_ip = record.endpoint
            vtep_mac = record.name
            ip_address = existing_arps[vtep_mac]
            fdbs.append(
                Fdb(ip_address, vtep_mac, vtep_ip, network_id, tunnel_type,
                    segment_id))
        return fdbs

    @classmethod
    def add_fdb_to_arp(cls, bigip, tunnel, fdbs):
        """Adds the list of fdbs' VTEPs to the bigip and tunnel_rpc

        This method will add a list of vteps to the tm.net.arps.arp and
        for each of these add the ip address to the tunnel_rpc.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
            tunnel - Tunnel object to be manipulated
            fdbs - list of relevant fdb's
        Returns:
            None
        """
        if isinstance(fdbs, list):
            tunnel.add_fdbs(bigip, fdbs)
        elif isinstance(fdbs, Fdb):
            if fdbs.ip_address:  # loadbalancers don't need flood prevention
                try:
                    cls.__tm_arp(bigip, tunnel, fdbs, 'create')
                except HTTPError as error:
                    if error.response.status_code == '409':
                        cls.__tm_arp(bigip, tunnel, fdbs, 'modify')

    @classmethod
    def update_arp_by_fdb(cls, bigip, tunnel, fdb):
        """Updates a tm_arp object with the given fdb data"""
        cls.__tm_arp(bigip, tunnel, fdb, 'modify')

    @staticmethod
    def remove_arps(bigip, tunnel, fdbs):
        """Removes a tm.net.arps.arp entry from off the BIG-IP

        For the purposes of reducing BIG-IP ARP flooding, this method is meant
        to destroy a single arp object off of the bigip via load & delete.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
            tunnel - tunnels.tunnel.Tunnel object instance
            fdbs - list(Fdb) object instances
        KWargs:
            None
        Returns:
            None
        """
        tunnel.remove_fdbs(bigip, fdbs)

    @classmethod
    @wrapper.http_error(
        warn={'400': "Attempted delete on non-existent arp",
              '404': "Attempted delete on non-existent arp"})
    def remove_fdb_from_arp(cls, bigip, tunnel, fdbs):
        """Removes the list of fdb vteps from the provided BIG-IP

        This method will remove a list of vteps from the tm.net.arps.arp and
        for each of these add the ip address to the tunnel_rpc.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
            tunnel - Tunnel object to be manipulated
            fdbs - one or more fdbs (list(Fdb) or Fdb)
        """
        if isinstance(fdbs, list):
            for fdb in fdbs:
                cls.remove_fdb_from_arp(bigip, tunnel, fdb)
        elif isinstance(fdbs, Fdb):
            if fdbs.ip_address:  # loadbalancer ips don't need flood prevention
                cls.__tm_arp(bigip, tunnel, fdbs, 'delete')
        else:
            raise TypeError(
                "fdbs is neither a list(Fdb) nor an Fdb! {}".format(fdbs))
