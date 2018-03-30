"""A library that hosts tm.net action objects

These objects are used to perform a single action on the BIG-IP efficiently.
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

from requests import HTTPError

import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 as const
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.decorators as wrappers


class TmNetActionBase(object):
    """Creates a base tm action object against the BIG-IP

    This is a base action class that will house base functionality of the
    TmAction specific object.

    obj = TmNetAction(bigip.tm.net.obj, action)

    The action argument is a string of create, load, modify, or delete.
    The bigip.tm.net.obj is just a shortening of the tm type modification on
        the BIG-IP.
    """
    _possible_actions = []  # replace me in a specific!

    def __init__(self, bigip, action):
        self.action = action
        self._set_tm(bigip)
        self._payloads = []

    def __call__(self, *args, **kwargs):
        action = self.action
        execute = None
        blessed_actions = self._possible_actions
        if action in blessed_actions:
            execute = getattr(self, action)
        else:
            raise ValueError("Invalid action choice {}".format(self.action))
        return execute(*args, **kwargs)

    def _set_tm(self, bigip):
        self.tm = bigip.tm.net

    def _get_tm(self, bigip):
        raise NotImplementedError("Should be defined in specific")

    def execute(self, action=None, payload={}):
        """Performs execution on the provided action on object instantiation

        This method will attempt to perform the provided action on the
        bigip.tm.net...
        object instance

        Args:
            None
        KWArgs:
            action - string specific of an action that getattr can be applied
            to for self.tm.  That said, modify and delete will load the object
            first.
        """
        raise NotImplementedError("This object is not implemented!")

    def _execute(self, action=None, payload={}):
        # performs a BIG-IP action execution in a logger frame...
        my_action = getattr(self.tm, action)
        payload = dict() if isinstance(payload, type(None)) else payload
        self.logger.debug(
            "Executing {} {}({})".format(action, my_action, payload))
        ret_val = my_action(**payload)
        self.logger.debug(
            "Successfuly executed {} {}({})!".format(
                action, my_action, payload))
        return ret_val

    def load_payload(self):
        """Creates a payload of the general-case's load, which is tunnels"""
        tunnel = self.tunnel
        return dict(name=tunnel.tunnel_name, partition=tunnel.partition)

    def load(self):
        """Performs a load operation for the object, if load is the action"""
        payload = self.load_payload()
        return self._execute(action='load', payload=payload)

    def delete(self):
        """Performs a delete operation for the object, if delete is the action

        There is no validation against the action, persay
        """
        payload = self.load_payload()
        loaded = self.load(**payload)
        loaded.delete()

    def exists(self):
        """Performs an exists operation for the object, if that's the action"""
        payload = self.load_payload()
        return self._execute(action='exists', payload=payload)

    def create(self):
        """Performs an create operation for the object, if that's the action"""
        payload = self.create_payload()
        return self._execute(action='create', payload=payload)

    def modify(self, *args, **kwargs):
        """Performs an modify operation for the object, if that's the action"""
        old_tm = self.tm
        try:
            load_payload = self.load_payload()
            self.tm = self._execute(action='load', payload=load_payload)
            return self._execute(action='modify', payload=kwargs)
        finally:
            self.tm = old_tm

    def get_collection(self, *args, **kwargs):
        """Performs a get_collection on a collection-based tm object"""
        payload = self.get_collection_payload()
        return self.tm.get_collection(**payload)

    def not_supported(self, *args, **kwargs):
        """A general no-opt raise for actions unrecognized"""
        raise NotImplementedError(
            "action '{}' not supported for this object".format(self.action))


class TmTunnelsProfiles(TmNetActionBase):
    """Extract bigip.tm.net.tunnels.vxlans|gres.get_collection"""
    _possible_actions = ['get_collection']

    @wrappers.add_logger
    def __init__(self, bigip, action, tunnel_type):
        self.logger.debug(
            "Performing {} on {} Profile({}s)".format(
                action, bigip.hostname, tunnel_type))
        self.tunnel_type = tunnel_type
        super(TmTunnelsProfiles, self).__init__(bigip, action)

    def _set_tm(self, bigip):
        super(TmTunnelsProfiles, self)._set_tm(bigip)
        self.tm = getattr(self.tm.tunnels, "{}s".format(self.tunnel_type))

    def execute(self):
        """Performs a call to self and returns"""
        return self()

    def get_collection_payload(self):
        """Returns expected payload for get_collection"""
        return {}


class TmTunnelsProfile(TmNetActionBase):
    """Extract bigip.tm.net.tunnels.vxlans|gres.vxlan|gre.CRUD"""
    _possible_actions = ['create', 'modify', 'delete', 'load']

    @wrappers.add_logger
    def __init__(self, bigip, tunnel_type, name, partition, action):
        self.logger.debug(
            "Performing {} on {} Profile({}s)".format(
                action, bigip.hostname, tunnel_type))
        self.tunnel_type = tunnel_type
        self.name = name
        self.partition = partition
        super(TmTunnelsProfile, self).__init__(bigip, action)

    def _set_tm(self, bigip):
        super(TmTunnelsProfile, self)._set_tm(bigip)
        tunnel_type = self.tunnel_type
        self.logger.debug("tunnel_type: {}".format(tunnel_type))
        if tunnel_type is 'vxlan':
            self.tm = self.tm.tunnels.vxlans.vxlan
        elif tunnel_type is 'gre':
            self.tm = self.tm.tunnels.gres.gre

    def create_payload(self):
        ttype = self.tunnel_type
        base = dict(name=self.name, partition=self.partition,
                    floodingType='multipoint', defaultsFrom=ttype)
        if ttype is 'vxlan':
            base.update(dict(port=const.VXLAN_UDP_PORT))
        elif ttype is 'gre':
            base.update(encapsulation='transparent-ethernet-bridging')
        else:
            raise ValueError("Unrecognized tunnel-type: '{}'".format(ttype))
        return base

    def load_payload(self):
        return dict(name=self.name, partition=self.partition)

    def execute(self):
        """Performs a call to self and returns"""
        return self()


class FdbTunnel(TmNetActionBase):
    """Creates a TmTunnel TmNetAction object for manipulating Tunnels

    This object is used to interact with the
    bigip.tm.net.fdb.tunnels.tunnel objects for basic CRUD operations ONLY
    and performs no tracking.

    There should be an object per action
    """
    _possible_actions = ['load', 'exists', 'modify']

    @wrappers.add_logger
    def __init__(self, bigip, tunnel, action):
        self.logger.debug(
            "Performing {} on {} Tunnel({t.tunnel_name}, "
            "{t.partition})".format(
                action, hex(id(tunnel)), t=tunnel))
        super(FdbTunnel, self).__init__(bigip, action)
        self.tunnel = tunnel

    def _set_tm(self, bigip):
        super(FdbTunnel, self)._set_tm(bigip)
        self.tm = self.tm.fdb.tunnels.tunnel

    def execute(self):
        """An over-writing execute method that calls self"""
        return self()


class TmTunnel(TmNetActionBase):
    """Creates a TmTunnel TmNetAction object for manipulating Tunnels

    This object is used to interact with the
    bigip.tm.net.tunnels.tunnels.tunnel objects for basic CRUD operations ONLY
    and performs no tracking.

    There should be an object per action
    """
    _possible_actions = ['load', 'delete', 'create', 'exists']

    @wrappers.add_logger
    def __init__(self, bigip, tunnel, action):
        self.logger.debug(
            "Performing {} on {} Tunnel({t.tunnel_name}, "
            "{t.partition})".format(action, hex(id(tunnel)), t=tunnel))
        super(TmTunnel, self).__init__(bigip, action)
        self.bigip = bigip
        self.tunnel = tunnel

    def _set_tm(self, bigip):
        super(TmTunnel, self)._set_tm(bigip)
        self.tm = self.tm.tunnels.tunnels.tunnel

    def create_payload(self):
        """Specifies payload for create action"""
        tunnel = self.tunnel
        description = json.dumps(
            dict(partition=tunnel.partition, network_id=tunnel.network_id,
                 remote_address=tunnel.remote_address))
        create_payload = dict(
            name=tunnel.tunnel_name, description=description,
            profile=tunnel.profile, key=tunnel.key,
            partition=tunnel.partition, localAddress=tunnel.local_address,
            remoteAddress=tunnel.remote_address)
        return create_payload

    def load(self):
        payload = self.load_payload()
        return self.tm.load(**payload)

    def execute(self):
        """An over-writing execute method that calls self"""
        return self()

    def delete(self):
        """Assure action of delete on the TmTunnel"""
        load_payload = self.load_payload()
        fdb_tunnel_load = FdbTunnel(self.bigip, self.tunnel, 'load')
        arps_get_collection = TmArps(self.bigip, 'get_collection',
                                     self.tunnel)
        fdb_tunnel = fdb_tunnel_load()
        records = []
        if hasattr(fdb_tunnel, 'records_s'):
            records = fdb_tunnel.records_s.get_collection()
        arps = arps_get_collection()
        for record in records:
            name = record.name
            for arp in arps:
                if arp.name == name:
                    arp.delete()
                    break
            record.delete()
        # Best attempt at eliminating a race...
        tunnel = self.tm.load(**load_payload)
        tunnel.delete()


class TmTunnels(TmNetActionBase):
    """Extract bigip.tm.net.tunnels.tunnels.get_collection"""
    _possible_actions = ['get_collection']

    @wrappers.add_logger
    def __init__(self, bigip, action, partition):
        self.logger.debug(
            "Performing {} on {}'s Tunnels".format(action, bigip.hostname))
        self.partition = partition
        super(TmTunnels, self).__init__(bigip, action)

    def get_collection_payload(self):
        """Specifies a payload of a filter for partition for get_collection"""
        payload = {}
        filter_params = {}
        partition = getattr(self, 'partition', None)
        if partition and isinstance(partition, (str, type(u''))):
            filter_params = {'$filter': 'partition eq {}'.format(partition)}
            payload = dict(requests_params=filter_params)
        return payload

    def _set_tm(self, bigip):
        super(TmTunnels, self)._set_tm(bigip)
        self.tm = self.tm.tunnels.tunnels

    def execute(self):
        """Performs a call to self and returns"""
        return self()


class TmRecord(TmNetActionBase):
    """Creates a TmRecords TmNetAction object for manipulating FDB Records

    This object is used to interact with the
    bigip.tm.net.fdb.tunnels.tunnel.load().records_s.records objects for basic
    CRUD operations ONLY and performs no tracking.

    There should be an object per action.
    """
    _possible_actions = ['load', 'modify', 'delete', 'create', 'exists']

    @wrappers.add_logger
    def __init__(self, bigip, action, tunnel, fdbs):
        self.logger.debug("called with ({}, {}, {}, {})".format(
            bigip, action, tunnel, fdbs))
        self.logger.debug(
            "Performing {} on {} Tunnel({t.tunnel_name}, {t.partition}) "
            "Fdbs({})".format(action, hex(id(tunnel)), fdbs, t=tunnel))
        self.fdbs = fdbs
        self.tunnel = tunnel
        super(TmRecord, self).__init__(bigip, action)

    def _set_tm(self, bigip):
        super(TmRecord, self)._set_tm(bigip)
        fdb_tunnel_load = FdbTunnel(bigip, self.tunnel, 'load')
        self.tm = fdb_tunnel_load()

    def no_opt(self):
        self.logger.debug(
            "Attempted '{} on non-existent records for Tunnel({})".format(
                self.action, self.tunnel.tunnel_name))
        return False

    def load_payload(self, fdb):
        return dict(name=fdb.mac_address)

    def create_payload(self, fdb):
        return fdb.record

    def _get_tm_record(self):
        records = getattr(self.tm, 'records_s', None)
        records = getattr(records, 'records', None)
        if records:
            self.tm = records
            return True
        return False

    def create(self):
        """Creates a new record or modifies the fdbTunnel's records attr"""
        tm_confirmed = False
        fdbs = [self.fdbs] if not isinstance(self.fdbs, list) else self.fdbs
        for fdb in fdbs:
            if not tm_confirmed and not self._get_tm_record():
                break
            tm_confirmed = True
            payload = self.create_payload(fdb)
            self.tm.create(**payload)
        else:
            return
        self._create_records()

    def _create_records(self):
        fdbs = self.fdbs if isinstance(self.fdbs, list) else [self.fdbs]
        records = [self.create_payload(fdb) for fdb in fdbs]
        self.tm.modify(records=records)

    def delete(self):
        """Deletes the fdbs given from off the FdbTunnel"""
        tm_confirmed = False
        fdbs = self.fdbs
        fdbs = [fdbs] if not isinstance(fdbs, list) else fdbs
        for fdb in fdbs:
            global tm_confirmed
            if not tm_confirmed and not self._get_tm_record():
                break
            tm_confirmed = True
            payload = self.load_payload(fdb)
            record = self.tm.load(**payload)
            record.delete()
        else:
            return
        self.logger.debug(
            "Attempted to delete record where no records resided"
            " Tunnel({t.tunnel_name}, {t.partition}) Fdbs({})".format(
                fdbs, t=self.tunnel))

    def modify(self):
        """Attempts to modify the given fdbs' tunnel records with provided

        This method will take the fdbs given originally (at object init) and
        attempt to modify the provided fdb records in fdbs.  If there are no
        such records on the fdb_tunnel, then the records will be created with
        this list of fdbs.  Otherwise, the ones not found will be created via
        create().

        Args:
            None
        Returns:
            None
        Exceptions:
            requests.HTTPError if something bad happens
        """
        fdbs = self.fdbs
        fdbs = [fdbs] if not isinstance(fdbs, list) else fdbs
        the_unfound = []
        tm_confirmed = False
        for fdb in fdbs:
            if not tm_confirmed and not self._get_tm_record():
                the_unfound.extend(fdbs)
                break
            tm_confirmed = True
            payload = self.load_payload(fdb)
            try:
                record = self.tm.load(**payload)
                record.modify(endpoint=fdb.vtep_ip)
            except HTTPError as error:
                if int(error.response.status_code) is 404:
                    the_unfound.append(fdb)
        if the_unfound:
            self.fdbs = the_unfound
            if not hasattr(self, 'records_s'):
                self._create_records()
            else:
                self.create()

    def execute(self):
        """An over-writing execute method that calls self"""
        return self()


class TmArp(TmNetActionBase):
    """Creates a TmArp TmNetAction object for manipulating Arp objects

    This object is used to interact with the bigip.net.arps.arp objects for
    basic CRUD operations ONLY and performs no tracking.

    There should be an object per action.
    """
    _possible_actions = ['load', 'modify', 'delete', 'create', 'exists']
    _collision_explanation = str(
        "IP Address collision with IP: {} for arp.  This is likely due to an"
        " FDB update from a loadbalancer's VIP being updated in the ARP and "
        "is not a concern.  Especially if the last octet is +1-3 of the"
        " subnet's allocation pool's starting point.  If it is higher than "
        "that, look to your member ip static allocation or DHCP agent.")

    @wrappers.add_logger
    def __init__(self, bigip, action, fdbs, partition):
        self.logger.debug(
            "Performing {} on Arp({})".format(action, fdbs))
        super(TmArp, self).__init__(bigip, action)
        self.fdbs = fdbs
        self.partition = partition

    def _set_tm(self, bigip):
        super(TmArp, self)._set_tm(bigip)
        self.tm = self.tm.arps.arp

    def load_payload(self, fdb):
        """Creates a 'load' payload for the TmArp action"""
        return dict(name=fdb.mac_address, partition=self.partition)

    def create_payload(self, fdb):
        """Creates a dict of the correct payload for the fdb given

        It is important to note that v3.0.8 of the sdk requires a name
        argument.  It may be in future releases that name, like in pervious,
        is not required, and, in fact, cause bugs.
        """
        return dict(ipAddress=fdb.ip_address, partition=self.partition,
                    macAddress=fdb.mac_address, name=fdb.mac_address)

    def create(self):
        """Attempts to perform a create on the provided list of fdb target"""
        errors = list()
        created = list()
        fdbs = [self.fdbs] if not isinstance(self.fdbs, list) else self.fdbs
        for fdb in fdbs:
            try:
                payload = self.create_payload(fdb)
                created.append(self._execute(action='create', payload=payload))
            except HTTPError as error:
                status_code = int(error.response.status_code)
                msg = str(error)
                if status_code is 409:
                    continue  # already exists
                elif status_code is 400 and "Invalid IP address" in msg:
                    self.logger.error(self._collision_explanation.format(
                        fdb.ip_address))
                elif status_code is 409:
                    self.logger.debug("ARP already exists for {}".format(
                        fdb.mac_address))
                elif "'name'" in str(error):
                    try:
                        # some versions of SDK does not support 'name' field
                        payload.pop('name')
                        created.append(self._execute(
                            action='create', payload=payload))
                    except HTTPError as error:
                        status_code = int(error.response.status_code)
                        msg = str(error)
                        if status_code is 409:
                            continue  # already exists
                        elif status_code is 400 and \
                                "Invalid IP address" in msg:
                            self.logger.error(
                                self._collision_explanation.format(
                                    fdb.ip_address))
                        elif status_code is 409:
                            self.logger.debug(
                                "ARP already exists for {}".format(
                                    fdb.mac_address))
                        else:
                            errors.append(error)
                    except Exception as error:
                        errors.append(error)
                else:
                    errors.append(error)
            except Exception as error:
                errors.append(error)
        if errors:
            raise Exception(
                "{}\n{}".format(fdbs, ', '.join([str(x) for x in errors])))
        return created

    def load(self):
        """Performs a load on a TmArp object"""
        loaded = []
        fdbs = [self.fdbs] if not isinstance(self.fdbs, list) else self.fdbs
        for fdb in fdbs:
            try:
                payload = self.load_payload(fdb)
                loaded.append(self._execute(action='load', payload=payload))
            except Exception as error:
                self.logger.warning(str(error))
        return loaded

    def delete(self):
        """Performs a delete on a TmArp object"""
        old_tm = self.tm
        fdbs = [self.fdbs] if not isinstance(self.fdbs, list) else self.fdbs
        for fdb in fdbs:
            try:
                payload = self.load_payload(fdb)
                self.tm = self._execute(action='load', payload=payload)
                self._execute(action='delete')
            except HTTPError as error:
                if int(error.response.status_code) in [404, 400]:
                    self.logger.debug(
                        "Could not find Arp({}) to delete it".format(payload))
                else:
                    self.logger.warning(str(error))
            except Exception as error:
                self.logger.warning(str(error))
            finally:
                self.tm = old_tm

    def modify(self):
        """Performs a modify on the TmArp object or creates non-existant

        This is a DC action as there is no simple U for an arp object in
        the SDK or on the BIG-IP.

        If the arp is not found in load to D phase, it will store it and later
        try a C on it.
        """
        old_tm = self.tm
        fdbs = [self.fdbs] if not isinstance(self.fdbs, list) else self.fdbs
        not_found = list()
        for fdb in fdbs:
            try:
                payload = self.create_payload(fdb)
                self.tm = self.tm.load(**payload)
                self.tm.delete()
                old_tm.create(**payload)
            except HTTPError as error:
                msg = str(error)
                status_code = int(error.response.status_code)
                if status_code in [404, 400]:
                    not_found.append(fdb)
                elif status_code is 400 and "Invalid IP address" in msg:
                    self.logger.error(self._collision_explanation.format(
                        fdb.ip_address))
            finally:
                self.tm = old_tm
        if not_found:
            self.fdbs = not_found
            self.create()

    def exists(self):
        """Performs an exists check on TmArp object"""
        fdbs = [self.fdbs] if not isinstance(self.fdbs, list) else self.fdbs
        exists = []
        for fdb in fdbs:
            payload = self.load_payload(fdb)
            exists.append(self.tm.exists(**payload))
        return exists


class TmArps(TmNetActionBase):
    """Creates an action for TmArps and allows user to execute it"""
    _possible_actions = ['get_collection']

    def __init__(self, bigip, action, tunnel):
        super(TmArps, self).__init__(bigip, action)
        self.tunnel = tunnel

    def _set_tm(self, bigip):
        super(TmArps, self)._set_tm(bigip)
        self.tm = self.tm.arps

    def get_collection_payload(self):
        """Specifies a payload of a filter for partition for get_collection"""
        payload = {}
        filter_params = {}
        partition = getattr(self.tunnel, 'partition', None)
        if partition and isinstance(partition, (str, type(u''))):
            filter_params = {'$filter': 'partition eq {}'.format(partition)}
            payload = dict(requests_params=filter_params)
        return payload
