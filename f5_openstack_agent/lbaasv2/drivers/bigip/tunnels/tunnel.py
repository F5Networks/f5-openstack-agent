"""A module for all things network tunnel-based for VXLAN and GRE Tunnels

This module hosts 3 classes:
    - Tunnel
    - TunnelBuilder
    - TunnelHandler

These classes are used to orchestrate the necessary steps for handling the
BIG-IP's tunnels.
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

import json
import re

from collections import namedtuple
from requests import HTTPError

from oslo_log import log as logging

import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 as const
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.cache as cache
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.decorators as wrappers
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.fdb as fdb_mod
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels. \
    network_cache_handler as network_cache_handler

LOG = logging.getLogger(__name__)


def is_valid_fdbs_arg(method):
    """Decorator for wrapper that checks arguments"""
    def fdb_valid_wrapper(self, bigip, fdbs, **kwargs):
        if not isinstance(fdbs, list) and \
                not isinstance(fdbs, fdb_mod.Fdb):
            raise TypeError(
                "The argument ({}) is not a valid fdbs argument!".format(
                    fdbs))
        return method(self, bigip, fdbs, **kwargs)
    return fdb_valid_wrapper


class Tunnel(cache.CacheBase):
    """A Tunnel object for tracking tunnels on the bigip

    This object is meant to simply store the data that would normally be held
    on a BIG-IP's tm.net.tunnels.tunnels.tunnel object and a bigip's
    tm.net.fdb.tunnels.tunnel object.

    This is useful for limiting the number of operations against the BIG-IP's
    REST API; thereby, reducing the overload and speed costs that otherwise
    might occur while involving the BIG-IP.  This greatly expands the
    scalability of a tunnel, L2-Population Event-driven environment.
    """
    __tunnel_type_re = re.compile('_\w+')

    @wrappers.add_logger
    def __init__(self, network_id, tunnel_type, segment_id, bigip_host,
                 partition, local_address, remote_address):
        self.network_id = network_id
        self.tunnel_type = tunnel_type
        self.segment_id = segment_id
        self.bigip_host = bigip_host
        self.partition = partition
        self.local_address = local_address
        self.remote_address = remote_address
        self.__exists = False
        self.__fdbs = []
        super(Tunnel, self).__init__()

    @property
    def __str__(self):
        """Returns a string with tunnel-specific information"""
        return str("Tunnel({s.network_id}: {s.bigip_host}: {s.partition}: "
                   "{s.tunnel_name})").format(s=self)

    @property
    def __dict__(self):
        return dict(
            bigip_host=self.bigip_host, segment_id=self.segment_id,
            tunnel_type=self.tunnel_type, network_id=self.network_id,
            partition=self.partition, exists=self.exists,
            local_address=self.local_address, fdbs=self.fdbs,
            remote_address=self.remote_address)

    def __eq__(self, other):
        return self.network_id == other.network_id and \
            self.tunnel_name == other.tunnel_name and \
            self.local_address == other.local_address and \
            self.remote_address == other.remote_address and \
            self.bigip_host == other.bigip_host

    @wrappers.only_one
    @wrappers.not_none
    def _set_network_id(self, network_id):
        self.__network_id = str(network_id)

    def _get_network_id(self):
        return self.__network_id

    @wrappers.not_none
    def _set_tunnel_type(self, tunnel_type):
        # sets profile if it's a profile sent and regardless, sets tunnel_type
        if self.__tunnel_type_re.search(tunnel_type):
            self.__profile = tunnel_type
            tunnel_type = self.__tunnel_type_re.sub('', tunnel_type)
        self.__tunnel_type = str(tunnel_type)

    def _get_tunnel_type(self):
        return self.__tunnel_type

    @wrappers.only_one
    def _set_segment_id(self, segment_id):
        self.__segment_id = int(segment_id)

    def _get_segment_id(self):
        return str(self.__segment_id)

    @wrappers.only_one
    @wrappers.not_none
    def _set_bigip_host(self, bigip_host):
        self.__bigip_host = str(bigip_host)

    def _get_bigip_host(self):
        return self.__bigip_host

    @wrappers.only_one
    @wrappers.not_none
    def _set_partition(self, partition):
        self.__partition = str(partition)

    def _get_partition(self):
        return self.__partition

    def _set_exists(self, exists):
        current_status = self._get_exists()
        if current_status is False and exists is True and self.__fdbs:
            self.add_fdbs(self.fdbs, force_refresh=True)
        self.__exists = bool(exists)

    def _get_exists(self):
        return self.__exists

    @wrappers.only_one
    @wrappers.ip_address
    def _set_local_address(self, local_address):
        self.__local_address = str(local_address)

    def _get_local_address(self):
        return self.__local_address

    @wrappers.only_one
    @wrappers.ip_address
    def _set_remote_address(self, remote_address):
        self.__remote_address = str(remote_address)

    def _get_remote_address(self):
        return self.__remote_address

    @is_valid_fdbs_arg
    @cache.lock
    def add_fdbs(self, bigip, fdbs, force_refresh=False, init=False):
        """Handles all scenairos of adding one or more FDB's to a Tunnel

        This will utilize the fdb_mod.FdbBuilder and TunnelBuilder to
        orchestrate adding fdb's to the tm_fdb_tunnel and the tm_arp set on
        the provided BIG-IP.

        Args:
            bigip
            fdb
        KWArgs:
            force_refresh - Forces a refresh-create attempt on the provided
                list of objects.  This SHOULD NOT be generally used as it will
                cause an attempt to create for the fdb's ARP and tm_fdb_tunnel
                record FIRST before attempting to update them even if they're
                pre-existing in the tunnel.

        NOTE: the only time force_refresh is used is when a Tunnel exists, but
            the tm_tunnel is in __pending_exists moving into exists status.
        """
        known_macs = set(map(lambda x: x.mac_address, self.__fdbs))

        def add_fdb(fdb):
            self.logger.debug("{}: adding {}".format(self.tunnel_name, fdb))
            tunnel_method = TunnelBuilder.add_fdb_to_tunnel
            fdb_method = fdb_mod.FdbBuilder.add_fdb_to_arp
            new = fdb.mac_address not in known_macs or init
            if not new and not force_refresh:
                tunnel_method = TunnelBuilder.modify_fdb_in_tunnel
                fdb_method = fdb_mod.FdbBulder.update_arp_by_fdb
            tunnel_method(bigip, self, fdb)
            fdb_method(bigip, self, fdb)
            if new:
                self.__fdbs.append(fdb)
            fdb.log_create(bigip, self.partition)

        if isinstance(fdbs, list) and fdbs and \
                isinstance(fdbs[0], fdb_mod.Fdb):
            if not self.exists:
                self.__fdbs.extend(fdbs)
                return
            for fdb in fdbs:
                add_fdb(fdb)
        elif isinstance(fdbs, list):
            pass
        elif isinstance(fdbs, fdb_mod.Fdb):
            if not self.exists:
                self.__fdbs.append(fdb)
            add_fdb(fdb)

    @is_valid_fdbs_arg
    @cache.lock
    def remove_fdbs(self, bigip, fdbs):
        """Handles all scenarios of removing one or more Fdb's from a Tunnel

        This will utilize the fdb_mod.FdbBuilder and TunnelBuilder to
        orchestrate removing fdb's to the tm_fdb_tunnel and the tm_arp set on
        the provided BIG-IP.
        """
        def remove_fdb(fdb):
            self.logger.debug("{}: removing {}".format(self.tunnel_name, fdb))
            TunnelBuilder.remove_record_from_arp(bigip, self, fdb)
            fdb_mod.FdbBuilder.remove_fdb_from_arp(bigip, self, fdb)
            self.__fdbs = filter(lambda x: x.mac_address != fdb.mac_address,
                                 self.__fdbs)
            fdb.log_remove(bigip, self.partition)

        if isinstance(fdbs, list) and fdbs and \
                isinstance(fdbs[0], fdb_mod.Fdb):
            for fdb in fdbs:
                remove_fdb(fdb)
        elif isinstance(fdbs, list):
            for fdb in self.__fdbs:
                remove_fdb(fdb)
        elif isinstance(fdbs, fdb_mod.Fdb):
            remove_fdb(fdbs)

    @property
    def fdbs(self):
        return self.__fdbs

    @property
    def profile(self):
        return getattr(self, '_Tunnel__profile',
                       "{}_ovs".format(self.tunnel_type))

    @property
    def key(self):
        """Another name for segment_id; thus returns segment_id"""
        return self.segment_id

    @property
    def tunnel_name(self):
        """Returns the formatted name of the tunnel"""
        if not hasattr(self, '__tunnel_name'):
            tunnel_name = \
                "tunnel-{s.tunnel_type}-{s.segment_id}".format(s=self)
            self.__tunnel_name = tunnel_name
        return self.__tunnel_name

    def clear_fdbs(self):
        """Clears the stored fdbs attribute"""
        self.fdbs = list()

    bigip_host = property(_get_bigip_host, _set_bigip_host)
    segment_id = property(_get_segment_id, _set_segment_id)
    tunnel_type = property(_get_tunnel_type, _set_tunnel_type)
    network_id = property(_get_network_id, _set_network_id)
    partition = property(_get_partition, _set_partition)
    exists = property(_get_exists, _set_exists)
    local_address = property(_get_local_address, _set_local_address)
    remote_address = property(_get_remote_address, _set_remote_address)


class TunnelBuilder(object):
    """Builds, Destroys, and Helps Orchestrates Tunnels

    This class is not meant to ever be instantiated and acts like a standard
    builds operator library for Tunnels.

    As such, it never holds one or more tunnels; however, it will take or
    return tunnels while performing lifetime orchestration on them.
    """

    def __init__(self, *args, **kwargs):
        # assures that no TunnelBuilder instance is ever created normally...
        raise NotImplementedError(
            "{} is not meant to be instantiated".format(self.__class__))

    @staticmethod
    @wrappers.weakref_handle
    def __tm_tunnel(bigip, tunnel, action):
        # performs all actions on tm_tunnel by action
        def execute(actions, action):
            return actions[action]['method'](**actions[action]['payload'])
        tm_tunnel = bigip.tm.net.tunnels.tunnels.tunnel
        description = json.dumps(
            dict(partition=tunnel.partition, network_id=tunnel.network_id,
                 remote_address=tunnel.remote_address))
        create_payload = dict(
            name=tunnel.tunnel_name, description=description,
            profile=tunnel.profile, key=tunnel.key,
            partition=tunnel.partition, localAddress=tunnel.local_address,
            remoteAddress=tunnel.remote_address)
        load_payload = dict(name=tunnel.tunnel_name,
                            partition=tunnel.partition)
        actions = {'create': dict(payload=create_payload,
                                  method=tm_tunnel.create),
                   'delete': dict(payload=load_payload,
                                  method=tm_tunnel.load),
                   'exists': dict(payload=load_payload,
                                  method=tm_tunnel.exists)}
        laction = 'load' if action is 'delete' else action
        tunnel.logger.debug(
            "executing {} on tm_tunnel({t.bigip_host}, {t.partition}, "
            "{t.tunnel_name})".format(laction, b=bigip, t=tunnel))
        result = execute(actions, action)
        if action in ['create', 'exists', 'load']:
            return result
        second_actions = {'delete': dict(payload={},
                                         method=result.delete)}
        tunnel.logger.debug(
            "executing {} on tm_tunnel({t.bigip_host}, {t.partition}, "
            "{t.tunnel_name})".format(action, b=bigip, t=tunnel))
        result = execute(second_actions, action)
        return result

    @staticmethod
    def __tm_multipoints(bigip, action, tunnel_type='vxlan'):
        # performs all actions on tm_multipoints by action
        tunnel_types = dict(vxlan=bigip.tm.net.tunnels.vxlans.get_collection,
                            gre=bigip.tm.net.tunnels.gres.get_collection)
        actions = {'get_collection': dict(payload={},
                                          method=tunnel_types[tunnel_type])}
        exe = actions[action]
        return exe['method'](**exe['payload'])

    @staticmethod
    def __tm_multipoint(bigip, tunnel_type, name, partition, action):
        def execute(actions, action):
            return actions[action]['method'](**actions[action]['payload'])
        default_profiles = {'gre': {'name': name,
                                    'partition': const.DEFAULT_PARTITION,
                                    'defaultsFrom': 'gre',
                                    'floodingType': 'multipoint',
                                    'encapsulation':
                                    'transparent-ethernet-bridging',
                                    'tm_endpoint':
                                    bigip.tm.net.tunnels.gres.gre
                                    },
                            'vxlan': {'name': name,
                                      'partition': const.DEFAULT_PARTITION,
                                      'defaultsFrom': 'vxlan',
                                      'floodingType': 'multipoint',
                                      'port': const.VXLAN_UDP_PORT,
                                      'tm_endpoint':
                                      bigip.tm.net.tunnels.vxlans.vxlan}}
        create_tunnel = default_profiles[tunnel_type]
        tunnel = dict(name=name, partition=partition)
        tm_multipoint = create_tunnel.pop('tm_endpoint')
        actions = {'create': dict(
                       payload=create_tunnel, method=tm_multipoint.create),
                   'delete': dict(
                       payload=tunnel, method=tm_multipoint.load),
                   'exists': dict(
                       payload=tunnel, method=tm_multipoint.exists)}
        result = execute(actions, action)
        second_actions = {'delete': {'payload': {}, 'method': result.delete}}
        if action in second_actions:
            result = execute(second_actions, action)

    @staticmethod
    def __tm_tunnels(bigip, action, partition=None):
        filter_params = {}
        tm_tunnels = bigip.tm.net.tunnels.tunnels
        actions = {'get_collection': dict(payload=filter_params,
                                          method=tm_tunnels.get_collection)}
        exe = actions[action]
        LOG.debug("Executing {}({}) on bigip.tm.net.tunnels on "
                  "{b.hostname}".format(action, partition, b=bigip))
        return exe['method'](*exe['payload'])

    @classmethod
    @wrappers.weakref_handle
    def __tm_fdb_tunnel(cls, bigip, tunnel, action, record={}):
        # performs all actions on tm_fdb_tunnel by action
        def execute(actions, action):
            exe = actions[action]
            return exe['method'](**exe['payload'])

        tm_tunnel = bigip.tm.net.fdb.tunnels.tunnel
        tunnel_name = tunnel.tunnel_name
        partition = tunnel.partition
        load_payload = dict(name=tunnel_name, partition=partition)
        tunnel_exists = dict(payload=load_payload, method=tm_tunnel.exists)
        load_tunnel = dict(payload=load_payload, method=tm_tunnel.load)
        first_actions = dict(
            modify=load_tunnel,
            load=load_tunnel,
            exists=tunnel_exists,
            get_record=load_tunnel,
            modify_record=load_tunnel,
            create_record=load_tunnel,
            delete_record=load_tunnel,
            records_get_collection=load_tunnel,
            record_exists=load_tunnel)
        tunnel.logger.debug("Executing bigip.tm.net.fdb.tunnels.tunnel.load "
                            "for {} on {b.hostname}".format(action, b=bigip))
        firsts_result = execute(first_actions, action)
        if 'record' in action:
            return cls.__tm_records(firsts_result, tunnel, action, record={})
        else:
            return firsts_result

    @staticmethod
    @wrappers.weakref_handle
    def __tm_records(tm_fdb_tunnel, tunnel, action, record={}):
        if 'get_collection' in action:
            # We've got it!  Send it back...
            return getattr(tm_fdb_tunnel, 'records', [])
        try:
            level = tm_fdb_tunnel.records_s.records
            load = dict(method=level.load,
                        payload=record)
            create = dict(method=level.create,
                          payload=record)
            exists = dict(method=level.exists, payload=record)
            actions = dict(delete_record=load, create_record=create,
                           get_record=load, record_exists=exists,
                           modify_record=load)
            delete = dict()
            modify = record
            tunnel.logger.debug(
                "Performing first for {} on fdb_tunnel.records_s.records for "
                "{}".format(action, record))
            result = actions[action]['method'](**actions[action]['payload'])
            second = {
                'delete_record': dict(payload=delete, method=result.delete),
                'modify_record': dict(payload=modify, method=result.modify)}
            if action in second:
                tunnel.logger.debug(
                    "Performing {} on fdb_tunnel.records_s.records for "
                    "{}".format(action, record))
                result = second[action]['method'](**second[action]['payload'])
            return result
        except AttributeError:
            responses = dict(delete_record=None, record_exists=False,
                             record_get_collection=[])
            if 'delete_record' == action:
                LOG.warning("Could not delete non-existent "
                            "record {}".format(record))
            if action in responses:
                return responses[action]
            elif 'load_record' == action:
                raise EnvironmentError("Could not find record "
                                       "{}".format(record))
            elif action in ['create_record', 'modify_record']:
                tm_fdb_tunnel.modify(records=[record])

    @staticmethod
    def __create_tunnel_from_dict(params, bigip):
        # Takes a model dict created by the l2service and generates a Tunnel
        network_id = params.get('network_id', None)
        tunnel_type = params.get(
            'tunnel_type', params.get(
                'network_type', params.get(
                    'profile', None)))
        segment_id = params.get(
            'segment_id', params.get(
                'key', ''))
        bigip_host = bigip.hostname if bigip else ''
        partition = params.get('partition', None)
        local_address = params.get('localAddress', None)
        # what follows comes from the replaced code...
        remote_address = params.get('remoteAddress', '0.0.0.0')
        tunnel = Tunnel(network_id, tunnel_type, segment_id, bigip_host,
                        partition, local_address, remote_address)
        return tunnel

    @staticmethod
    def _check_if_fdbs(method):
        """A classmethod decorator that will add check_if_fdbs_wrapper"""
        def check_if_fdbs_wrapper(cls, bigip, tunnel, fdb):
            """Wrapper that splits on fdb being an iterator-type

            If fdb is an iterator, then a list instance of it is sent to the
            appropriate tunnel method to handle the fdb addition.

            Args of wrapped class:
                cls - this class
                bigip - f5.bigip.ManagementRoot object instance
                tunnel - Tunnel object instance
                fdb - Fdb object instance
            Returns:
                whatever it calls' returns
            """
            if isinstance(fdb, list) or isinstance(fdb, tuple) or \
                    isinstance(fdb, set):
                return tunnel.addfdbs(bigip, list(fdb))
            else:
                return method(cls, bigip, tunnel, fdb)

    @classmethod
    @wrappers.weakref_handle
    def get_records_from_tunnel(cls, bigip, tunnel):
        records = cls.__tm_fdb_tunnel(bigip, tunnel, 'records_get_collection')
        return records

    @classmethod
    @wrappers.http_error(error={409: "tunnel_profile alrady exists"})
    def create_multipoint_profile(cls, bigip, tunnel_type, name, partition):
        """Creates a multipoint tunnel profile on the provided partition

        This object method will create either a vxlan or gre multipoint tunnel
        profile on the BIG-IP for the provided partition (usually Common).

        As such, it manuplates bigip.tm.net.tunnels.<gres|vxlans>.<gre|vxlan>

        This can then be used as a base profile for any created:
            bigip.tm.tunnels.tunnels.tunnel
        """
        cls.__tm_multipoint(bigip, tunnel_type, name, partition, 'create')

    @classmethod
    @wrappers.http_error(error={409: "tunnel_profile alrady exists"})
    def get_multipoint_profiles(cls, bigip):
        """Grabs all multipoint tunnel profiles on the bigip

        This object method will create either a vxlan or gre multipoint tunnel
        profile on the BIG-IP for the provided partition (usually Common).

        As such, it manuplates bigip.tm.net.tunnels.<gres|vxlans>.<gre|vxlan>

        This can then be used as a base profile for any created:
            bigip.tm.tunnels.tunnels.tunnel
        """
        profiles = cls.__tm_multipoints(bigip, 'get_collection')
        profiles.extend(cls.__tm_multipoints(bigip, 'get_collection', 'gre'))
        return profiles

    @staticmethod
    def _create_tunnel_from_tm_tunnel(bigip, tm_tunnel):
        description = json.loads(tm_tunnel.description)
        partition = description.get('partition')
        network_id = description.get('network_id')
        remote_address = description.get('remote_address')
        tunnel_type = 'vxlan' if 'vxlan' in tm_tunnel.name else 'gre'
        segment_id = tm_tunnel.key
        bigip_host = bigip.host
        local_address = bigip.local_ip
        return Tunnel(network_id, tunnel_type, segment_id, bigip_host,
                      partition, local_address, remote_address)

    @classmethod
    def get_multipoint_tunnels(cls, bigip):
        """Grabs and/or handles all scenarios for grabbing all tunnels

        This will read from the BIG-IP the list of existing tunnels and return
        them in a list.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
        Returns:
            list(Tunnel) object instances
        """
        tm_tunnels = cls.__tm_tunnels(bigip, 'get_collection')
        tunnels = list()
        for tm_tunnel in tm_tunnels:
            tunnel = cls._create_tunnel_from_tm_tunnel(bigip, tm_tunnel)
            tunnels.append(tunnel)
        return tunnels

    @classmethod
    @wrappers.http_error(error={404: "tunnel_profile not found"})
    def delete_multipoint_profile(cls, bigip, tunnel_type, name, partition):
        """Deletes a multipoint tunnel profile on the provided partition"""
        cls.__tm_multipoint(bigip, tunnel_type, name, partition, 'delete')

    @classmethod
    @wrappers.weakref_handle
    def create_tunnel(cls, bigip, params=None, tunnel=None):
        """Creates a tunnel object and attempts to push creation to BIG-IP

        This method will look at the arguments given and make the
        determination of whether to create or update the BIG-IP (if possible),
        or simply return the created Tunnel object.

        Of the objects given, only what is necessary to create the tunnel will
        be used.  Erroneous keys will be ignored.

        This creates/updates the bigip.tm.net.tunnels.tunnels.tunnel

        Args:
            bigip - if None, then it will not attempt to update a BIG-IP
        KWArgs:
            params - a dictionary of network_id, network_type|tunnel-type,
                segmentation_id|key, partition, localAddress, remoteAddress
            tunnel - An already created Tunnel object instance
        Returns:
            new_tunnel or provided tunnel
        """
        if params and not tunnel:
            tunnel = cls.__create_tunnel_from_dict(params, bigip)
        if bigip:
            cls.__tm_tunnel(bigip, tunnel, 'create')
        return tunnel

    @classmethod
    @wrappers.weakref_handle
    def check_exists(cls, bigip, tunnel):
        """Checks existential status of a tunnel on the bigip"""
        return cls.__tm_tunnel(bigip, tunnel, 'exists')

    @classmethod
    @wrappers.weakref_handle
    @wrappers.http_error(
        debug={404: "Attempted delete on non-existent tunnel"})
    def delete_tunnel(cls, bigip, tunnel):
        """Same as create_tunnel, but it will attempt to delete

        This method WILL error if a bigip is not given!  Thus, IT CANNOT BE
        None.

        Deletes bigip.tm.net.tunnels.tunnels.tunnel instance

        Args:
            bigip - it will delete the tunnel from the BIG-IP
        KWArgs:
            params - a dictionary of network_id, network-type|tunnel_type,
                segmentation_id|key, partition
            tunnel - An already created Tunnel Object instance
        Returns:
            None
        """
        tunnel.remove_fdbs(bigip, [])
        cls.__tm_tunnel(bigip, tunnel, 'delete')

    @classmethod
    @wrappers.weakref_handle
    def add_fdb_to_tunnel(cls, bigip, tunnel, fdb):
        """Creates a new record on a tunnel from the Fdb object given

        This method will create a tunnel, fdb record on the given bigip's
        tunnel.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
            tunnel - Tunnel object instance
            fdb - Fdb object instance
        Returns:
            Non
        """
        try:
            record = fdb.record
            cls.__tm_fdb_tunnel(bigip, tunnel, 'create_record', record=record)
        except HTTPError as error:
            if error.response.status_code == 404:
                LOG.error(
                    "Attempted to update an FDB record on a bigip that did "
                    "not have the associated tunnel... creating it ({}, {})".
                    format(tunnel, fdb))
                cls.create_tunnel

    @classmethod
    @wrappers.weakref_handle
    @wrappers.http_error(
        debug={404: "Attempted delete on non-existent record"})
    def remove_record_from_arp(cls, bigip, tunnel, fdb):
        def remove(fdb):
            record = fdb.record
            cls.__tm_fdb_tunnel(bigip, tunnel, 'delete_record', record=record)

        if isinstance(fdb, list):
            for my_fdb in fdb:
                remove(my_fdb)
        else:
            remove(fdb)

    @classmethod
    @wrappers.weakref_handle
    def modify_fdb_in_tunnel(cls, bigip, tunnel, fdb):
        """Modifies a tunnel, fdb record that previously exists

        This will utilize the
            bigip.tm.net.fdb.tunnels.tunnel.load().records_s.records
        sdk feature to simply modify a single record rather than update the
        whole set of records resulting in a large update against the BIG-IP
        backplane.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
            tunnel - Tunnel object instance
            fdb - Fdb object instance
        Returns:
            None
        """
        try:
            cls.__tm_tunnel(bigip, tunnel, fdb, 'modify_record')
        except HTTPError as error:
            if error.response.status_code == 404:
                if 'record' in error:
                    cls.add_fdb_to_tunnel(bigip, tunnel, fdb)
                else:
                    LOG.error(
                        "Attempted to update a fdb record on a bigip that did"
                        " not have the tunnel to begin with ({}, {})".format(
                            tunnel, fdb))
                    cls.create_tunnel(bigip, tunnel=tunnel)
                    cls.add_fdb_to_tunnel(bigip, tunnel, fdb)


class TunnelHandler(cache.CacheBase):
    """A handler for orchestration interactions with tunnels

    This object is meant to primarily handle all interactions regarding
    tunnels including, but not limited to:
        * Creating gre and vxlan tunnel, multipoint profiles
        * Creating gre and vxlan multipoint tunnels
        * Handling tunnel interactions
        * Caching tunnel information
    This is part of a six-part class orchestration involving:
        fdb.Fdb
        fdb.FdbBuilder
        network_cache_handler.NetworkCacheHandler
        Tunnel
        TunnelBuilder
    Each class has its dominion on what it can do, and what it orchestrates
    will be as close to the concerning object as possible.  Builders are the
    only classes that can directly influence BIG-IP's for tunnels as the agent
    gets.  This, this is a good starting point for that kind of
    troubleshooting.

    Memory issues regarding network_cache:
        If there are lingering fdb's, their point of cache is in the Tunnel
        object.
        If there are lingering Tunnels, look to this object's __pending_exists
        and the NetworkCachHandler's __existing_tunnels lists.  All other
        references should be weakref.WeakProxy instances!
    """
    __profile = namedtuple('Profile', 'host, name, partiton, check')

    @wrappers.add_logger
    def __init__(self, tunnel_rpc, l2pop_rpc, context):
        self.tunnel_rpc = tunnel_rpc
        self.l2pop_rpc = l2pop_rpc
        self.context = context
        self.__network_cache_handler = \
            network_cache_handler.NetworkCacheHandler()
        self.__multipoint_profiles = []
        self.__pending_exists = []
        self.__profiles = []
        super(TunnelHandler, self).__init__()

    @staticmethod
    def _get_bigips_by_hostname(bigips):
        return {x.hostname: x for x in bigips}

    @wrappers.weakref_handle
    @cache.lock
    def tunnel_sync(self, bigips):
        """Checks the list of tunnels that are in pending exist status

        This should be part of the AgentManager's periodic sync methodologies
        and will first collect the bigips by hostname and then loop through
        the list of tunnels in __pending_exists to validate their existence.

        Remmber, a tunnel is only ever added to __pending_exists when it is
        first created.  This should prevent us from attempting to add or
        handle fdbs on a tunnel that does not exist.
        """
        by_hostname = self._get_bigips_by_hostname(bigips)
        new_pending_exists = list()
        for cnt, tunnel in enumerate(self.__pending_exists):
            exists = \
                TunnelBuilder.check_exists(
                    by_hostname[tunnel.bigip_host], tunnel)
            if not exists:
                new_pending_exists.append(tunnel)
                continue
            self.__network_cache_handler.network_cache = tunnel
            self.notify_tunnel_existence(tunnel)
        self.__pending_exists = new_pending_exists

    @wrappers.weakref_handle
    def check_fdbs(self, bigips, fdbs):
        """Checks the given fdbs against the network cache and returns hosts

        By first checking all __pending_exists tunnels for existence status,
        then by performing a check against the network_cache.  This will
        generate a dict(<bigip hostname>=tuple([tunnel, fdb])).
        """
        self.tunnel_sync(bigips)
        hosts = self.__network_cache_handler.check_fdb_entries_networks(
            fdbs)
        return hosts

    def __generate_profile(self, host, name, partition):
        payload = [host, name, partition]
        payload.append("{}:{}:{}".format(*payload))
        return self.__profile(*payload)

    def __add_profile(self, profile):
        self.__profiles.append(profile)

    def __remove_profile(self, profile):
        for cnt, iprofile in enumerate(self.__profiles):
            if iprofile.check == profile.check:
                self.__profiles.pop(cnt)
                break

    def __multipoint_exists(self, profile):
        for iprofile in self.__profiles:
            if iprofile.check == profile.check:
                return True
        return False

    @cache.lock
    def __add_pending_exists(self, tunnel):
        self.logger.debug("Caching Tunnel({t.bigip_host}, {t.partition}, "
                          "{t.tunnel_name})".format(t=tunnel))
        self.__pending_exists.append(tunnel)

    @cache.lock
    def __create_profile(self, bigip, tunnel_type, name, partition):
        # Performs necessary actions to create a multipoint tunnel
        payload = [bigip.hostname, name, partition]
        payload.append(self.__generate_profile(*payload))
        profile = self.__profile(*payload)
        if not self.__multipoint_exists(profile):
            msg = "Creating {} profile ({}, {}) on {}".format(
                    tunnel_type, name, partition, bigip.hostname)
            self.logger.debug(msg)
            TunnelBuilder.create_multipoint_profile(
                bigip, tunnel_type, name, partition)
            self.__add_profile(profile)

    @cache.lock
    def __delete_profile(self, bigip, tunnel_type, name, partition):
        # Deletes a bigip.tm.net.tunnels.<type>
        msg = "Deleting {} profile ({}, {}) on {}".format(
                tunnel_type, name, partition, bigip.hostname)
        self.logger.debug(msg)
        TunnelBuilder.delete_multipoint_profile(
            bigip, tunnel_type, name, partition)
        profile = self.__generate_profile(bigip.hostname, name, partition)
        if not self.__multipoint_exists(profile):
            self.logger.error("Attempted delete on tunnel profile '{}' "
                              "that is not in cache!")
            return
        self.__remove_profile(profile)

    def __purge_profiles(self, bigips):
        # Removes bigip.tm.net.tunnels.<type> tunnel profile
        by_hostname = self._get_bigips_by_hostname(bigips)
        for profile in self.__profiles:
            if profile.host in by_hostname:
                tunnel_type = 'vxlan' if 'vxlan' in profile.name else 'gre'
                msg = str("Deleting {} profile ({p.name}, {p.partition}) on "
                          "{p.host}").format(
                        tunnel_type, p=profile)
                self.logger.debug(msg)
                bigip = by_hostname[profile.host]
                TunnelBuilder.delete_multipoint_profile(
                    bigip, tunnel_type, profile.name, profile.partition)
        self.__profiles = list()

    def __purge_tunnels(self, bigips):
        # Removes everything in the caches bigip.tm.net.tunnels.tunnel down
        by_hostname = self.get_bigips_by_hostname(bigips)
        self.__network_cache_handler.purge_tunnels(by_hostname)
        for tunnel in self.__pending_exists:
            TunnelBuilder.delete_tunnel(by_hostname[tunnel.bigip_host],
                                        tunnel)

    def create_l2gre_multipoint_profile(self, bigip, name, partition):
        """Creates a multi-point tunnel on the partition provided

        This call will create the bigip.tm.net.tunnels.gre.gre on the
        partition given.

        Args:
            bigip - f5.bigip.ManagementRoot instance
            name - string of the tunnel's name
            partition - partition that the tunnel will be associated with
        Returns:
            tunnel - the resulting, created object
        """
        self.logger.debug("Creating profile (gre, {}, {}, "
                          "{b.hostname}".format(name, partition, b=bigip))
        self.__create_profile(bigip, 'gre', name, partition)

    def delete_l2gre_multipoint_profile(self, bigip, name, partition):
        """Deletes a multi-point tunnel on the partition provided

        This call will delete the bigip.tm.net.tunnels.gre.gre on the
        partition given.

        Args:
            bigip - f5.bigip.ManagementRoot instance
            name - string of the tunnel's name
            partition - partition that the tunnel will be associated with
        Returns:
            tunnel - the resulting, deleted object
        """
        self.logger.debug("Deleting profile (gre, {}, {}, "
                          "{b.hostname}".format(name, partition, b=bigip))
        self.__delete_profile(bigip, 'gre', name, partition)

    def create_vxlan_multipoint_profile(self, bigip, name, partition):
        """Creates a multi-point tunnel on the partition provided

        This call will create the bigip.tm.net.tunnels.vxlans.vxlan on the
        partition given.

        Args:
            bigip - f5.bigip.ManagementRoot instance
            name - string of the tunnel's name
            partition - partition that the tunnel will be associated with
        Returns:
            tunnel - the resulting, created object
        """
        self.logger.debug("Creating profile (vxlan, {}, {}, "
                          "{b.hostname}".format(name, partition, b=bigip))
        self.__create_profile(bigip, 'vxlan', name, partition)

    def delete_vxlan_multipoint_profile(self, bigip, name, partition):
        """Deletes a multi-point tunnel on the partition provided

        This call will delete the bigip.tm.net.tunnels.vxlans.vxlan on the
        partition given.

        Args:
            bigip - f5.bigip.ManagementRoot instance
            name - string of the tunnel's name
            partition - partition that the tunnel will be associated with
        Returns:
            None
        """
        self.logger.debug("Deleting profile (vxlan, {}, {}, "
                          "{b.hostname}".format(name, partition, b=bigip))
        self.__delete_profile(bigip, 'vxlan', name, partition)

    @wrappers.weakref_handle
    def create_multipoint_tunnel(self, bigip, model):
        """Creates a multipoint tunnel on the BIG-IP

        This call will create the bigip.tm.tunnels.tunnel on the partition
        with the parameters given.

        Args:
            bigip - f5.bigip.ManagementRoot instance
            model - a dict of params recognizable by the TunnelBuilder
        Returns:
            None
        """
        self.logger.debug("Creating tunnel ({b.hostname}, {partition}, "
                          "{name})".format(b=bigip, **model))
        try:
            tunnel = TunnelBuilder.create_tunnel(bigip, params=model)
        except HTTPError as error:
            if error.response.status_code == 409:
                self.logger.debug("Attempted to create a new tunnel ({}) "
                                  "where one already existed".format(model))
            return
        self.__add_pending_exists(tunnel)

    @cache.lock
    def remove_multipoint_tunnel(self, bigip, name, partition):
        """Deletes a multipoint tunnel off of the BIG-IP

        This call will delete the bigip.tm.tunnels.tunnel on the partition
        by name.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
            name - Name of the tunnel
            partition - Name of the BIG-IP partition
        Returns:
            None
        """
        self.logger.debug(
            "Deleting Tunnel({b.hostname}, {}, {})".format(
                partition, name, b=bigip))
        tunnel = self.__network_cache_handler.remove_tunnel(
            bigip.hostname, name=name, partition=partition)
        if not tunnel:
            for itunnel in self.__pending_exists:
                if itunnel.tunnel_name == name and \
                        itunnel.partition == partition:
                    tunnel = itunnel
                    break
            else:
                raise cache.CacheError("Could not find tunnel({}, {}) "
                                       "to delete".format(name, partition))
        try:
            TunnelBuilder.delete_tunnel(bigip, tunnel)
        except HTTPError as error:
            tunnel.logger.error(
                "Attempted self destruction, but ran into a REST error: "
                "{}".format(error))
            # re-apply tunnel
            self.__network_cache_handler.network_cache = tunnel

    @cache.lock
    def purge_multipoint_profiles(self, bigips):
        """This is the ultimate big hammer for all things tunnel!

        This will destroy everything in the list of BIG-IP's that relate to
        tunnels.

        WARNING: Without Neutron, there is no return tunnel-wise from this
        event.

        Args:
            bigips - list(f5.bigip.ManagementRoot) instances
        Returns:
            None
        """
        self.logger.warn("Purging all existing multipoint profiles!")
        self.__purge_tunnels()
        self.__purge_profiles(bigips)

    @cache.lock
    def purge_tunnels(self, bigips):
        """Purges the cache of all tunnels, fdbs, and related objects

        This is a "big hammer" for purging all tunnels off of the BIG-IP.
        This does _not_ include multipoint profiles!

        There is no returning from this point, and all purged tunnel content
        will be reflected (purged as well) on the correlated BIG-IP.

        The only time that this would make sense to do is IFF there were no
        longer any loadbalancers with the same tenant_id located on the
        BIG-IP.

        Args:
            bigips - list(f5.bigip.ManagementRoot) object instances
        Returns:
            None
        """
        self.__purge_tunnels(self, bigips)

    @cache.lock
    def agent_init(self, bigips):
        """Performs actions to initialize all tunnel caches needed

        This will initialize all tunnels and tunnel profiles on the BIG-IP.
        This will then depend on the auto-triaging performed via purge
        orphaned objects.

        Args:
            bigip - f5.bigip.ManagementRoot object instance
        """
        profiles = list()
        for bigip in bigips:
            profiles = TunnelBuilder.get_multipoint_profiles(bigip)
            for profile in profiles:
                payload = [bigip.hostname, profile.name, profile.partition]
                payload.append(self.__generate_profile(*payload))
                tprofile = self.__profile(*payload)
                self.__add_profile(tprofile)
            if profiles:
                tunnels = TunnelBuilder.get_multipoint_tunnels(bigip)
                for tunnel in tunnels:
                    self.__network_cache_handler.network_cache = tunnel
                    records = TunnelBuilder.get_records_from_tunnel(
                            bigip, tunnel)
                    tunnel.add_fdbs(
                        bigip,
                        fdb_mod.FdbBuilder.create_fdbs_from_bigip_records(
                            bigip, records, tunnel), init=True)

    @wrappers.weakref_handle
    def notify_tunnel_existence(self, tunnel):
        """Performs a notification on the tunnel_rpc that a tunnel is online

        THis will take a tunnel and notify the tunnel_rpc that the tunnel is
        now online.

        Args:
            tunnel - Tunnel object instance
        Returns:
            None
        """
        self.tunnel_rpc.tunnel_sync(self.context, tunnel.local_address,
                                    tunnel.tunnel_type)

    @wrappers.weakref_handle
    def notify_vtep_existence(self, hosts, removed=False):
        """Notifies l2population rpc connection of vtep(s) being handled

        This will take the dict of bigip hosts and consolidate into single Fdb
        objects.  Then notify the l2pop_rpc that the object got in __init__.

        Args:
            hosts: {bigip.hostname: [[tunnels], [fdbs]]}
        Returns:
            None
        """
        fdbs_by_mac = dict()
        for host in hosts:
            for fdb in hosts[host][1]:
                mac = fdb.mac_address
                if mac not in fdbs_by_mac:
                    notify = self.l2pop_rpc.add_fdb_entries if not removed \
                        else self.l2pop_rpc.remove_fdb_entries
                    entry = {
                        fdb.network_id: {
                            'ports': {fdb.vtep_ip: [const.F5_FLOODING_ENTRY]},
                            'network_type': fdb.network_type,
                            'segment_id': fdb.segment_id}}
                    notify(self.context, entry)
                    fdbs_by_mac[fdb.mac_address] = fdb

    @cache.lock
    def _get_tunnels_by_network(self, network):
        network_id = network['id']
        segment_id = network['provider:segmentation_id']
        hosts = self.__network_cache_handler.get_tunnels_by_designation(
            network_id, segment_id)
        for tunnel in self.__pending_exists:
            if int(tunnel.segment_id) == int(segment_id) and \
                    tunnel.network_id == network_id:
                host = tunnel.bigip_host
                if host in hosts:
                    hosts[host].append(tunnel)
                else:
                    hosts[host] = [tunnel]
        return hosts

    @wrappers.weakref_handle
    def handle_fdbs_from_loadbalancer_and_members(self, bigips, loadbalancer,
                                                  members, remove=False):
        """Handles corner-case of service request with new LB and members

        This method will handle the caching of new FDB entries for a new
        loadbalancer and associated members if/when there are new members.

        As such, it will discover the relelvant tunnel by loadbalancer's
        network and associate the new network type's vteps.

        Args:
            bigips - [f5.bigip.ManagementRoot] instances
            loadbalancer - service request's loadbalancer | None
            members - service request's members associated with that
                loadbalancer | []
        Returns:
            None
        """
        if loadbalancer:
            network = loadbalancer.get('network', None)
        else:
            network = members[0]['network']
        by_host_names = self._get_tunnels_by_network(network)
        hosts = self._get_bigips_by_hostname(bigips)
        for host_name in by_host_names:
            bigip = hosts[host_name]
            for tunnel in by_host_names[host_name]:
                fdb_mod.FdbBuilder.handle_fdbs_by_loadbalancer_and_members(
                    bigip, tunnel, loadbalancer, members, remove=remove)

    def get_bigip_net_short_name(self, network_name):
        """Returns tunnel-/<type>-<key>/ for the short name"""
        self.logger.debug("Getting tunnel key for {}".format(network_name))
        short_name = network_name.replace('tunnel-', '')
        short_name = network_name.replace('tunnel-', '')
        return short_name
