"""A module that hosts the logic to hold, handle, and update the Network Cache

This module hosts the singleton object-class NetworkCacheHandler.  This
object, as singletone would imply, should only exist in one instance per agent
instance and be held within the AgentManager singleton object.

This library simply hosts this cache handler.
"""
# Copyright (c) 2018, F5 Networks, Inc.
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

from oslo_log import log as logging

import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.cache as cache
import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.decorators as \
    decorators
# import f5_openstack_agent.lbaasv2.drivers.bigip.network_helper

LOG = logging.getLogger(__name__)


class NetworkCacheHandler(cache.CacheBase):
    """Handler for the Network Cache

    This singleton object handles the Network Cache.  As such, the general
    use-case is to simply call one of the methods it offers for the
    updating of such information or, as such, orchestration.
    """
    @decorators.add_logger
    def __init__(self):
        self.__network_cache = {}
        super(NetworkCacheHandler, self).__init__()

    def __nonzero__(self):
        return len(self.__network_cache) > 0

    def __iter__(self):
        tunnels = [
            cached
            for net_id in self.__network_cache
            for seg_id in self.__network_cache[net_id]
            for cached in self.__network_cache[net_id][seg_id]]
        self.logger.debug("Iter returned {}".format(tunnels))
        return iter(tunnels)

    def _add_to_network_cache(self, tunnel):
        # Locks and finally stores the new tunnel within the __network_cache.
        # this being the crux of this design, has to be as solid as possible
        network_id, segment_id = tunnel.network_id, tunnel.segment_id
        network = self.__network_cache.get(network_id, dict())
        segment = network.get(segment_id, set())
        segment.add(tunnel)
        network[segment_id] = segment  # a re-reference is cheap
        self.__network_cache[network_id] = network
        self.logger.debug(
            "added {} making {}".format(
                tunnel, self.__network_cache))

    def _get_network_cache(self):
        # A placeholder get method
        raise NotImplementedError("Not currently set up to return the cache")

    def tunnel_sync(self, to_remove):
        """The only way that tunnels can be removed from the cache for standby

        This method will take a list of tunnels that are no longer viable and
        will remove them from the __network_cache.  This will still leave
        the primitive levels (dict/key/value pairs of net/segment present),
        but will remove the Tunnel object instances themselves.

        Args:
            to_remove - [Tunnel] objects to be removed
        Returns:
            None
        """
        for tunnel in to_remove:
            self.purge_tunnel(tunnel)

    def remove_tunnel(self, bigip_host, tunnel=None, name=None,
                      partition=None):
        """Begins prep to start tunnel's removal

        This method will simply return the provided tunnel based upon provided
        parameters.

        It will not delete the tunnel from the cache or perform any actions
        of that nature against the tunnel
        """
        self.logger.debug("Searching for Tunnel({}, {} ,{}, {}) in {}".format(
            bigip_host, tunnel, name, partition, self.__network_cache))
        retval = None
        if tunnel:
            segment = tunnel.segment_id
            network = tunnel.network_id
            net = self.__network_cache.get(network, dict())
            seg = net.get(segment, set())
            for itunnel in seg:
                if tunnel == itunnel:
                    retval = itunnel
                    break
        elif name and partition:
            tunnels = iter(self)
            found = \
                filter(lambda t: t.tunnel_name == name and
                       t.bigip_host == bigip_host and t.partition == partition,
                       tunnels)
            if found:
                retval = found[0]
        else:
            raise ValueError(
                "Cannot operate without name & partition or tunnel, "
                "(host: {}, tunnel: {}, name: {}, partition: {}".format(
                    bigip_host, tunnel, name, partition))
        if not retval:
            self.logger.error(
                "Could not return proper tunnel match with given args!"
                "(bigip_host={}, tunnel={}, name={}, partition={})".format(
                    bigip_host, tunnel, name, partition))
        return retval

    def purge(self, partition=None):
        """This method will iterate through all Tunnels and purge

        If a partition is yielded, then only the Tunnels with the same
        partition will be destroyed.

        Args:
            None
        KWArgs:
            partition - string representing the partiiton's name
        Returns:
            None
        """
        tunnels = iter(self)
        for tunnel in tunnels:
            if partition and tunnel.partition != partition:
                continue
            self.purge_tunnel(tunnel)

    def purge_tunnel(self, tunnel):
        """This method will destory the tunnel perminently from the cache

        This method is NOT a means to destroy the tunnel on the BIG-IP.
        Instead, it will destory the tunnel locally here on the cached
        instance on NCH, if it exists.  If it does not exist, then it will
        handle the set().remove's thrown KeyError and file a debug message.

        Args:
            tunnel - the Tunnel object ot be purged
        Returns:
            None
        Exceptions:
            None planned.
        """
        segment_id = tunnel.segment_id
        network_id = tunnel.network_id
        tunnel_stmt = \
            str("Tunnel(name: {t.tunnel_name}, net: {}, host: "
                "{t.bigip_host})").format(network_id, t=tunnel)
        self.logger.debug("Removing {} from Cache".format(tunnel_stmt))
        net = self.__network_cache.get(network_id, {})
        seg = net.get(segment_id, set())
        try:
            seg.remove(tunnel)
        except KeyError:
            self.logger.debug(
                "Removal failed due to unfound {}".format(tunnel_stmt))

    def __check_network_segment(self, network, seg_id, segment, cnt):
        tunnel = segment[cnt]
        return (tunnel.bigip_host, tunnel.partition, tunnel)

    def check_fdb_entries_networks(self, fdbs):
        """Wraps any relevant Fdb object given with its associated tunnel data

        This method will loop through the list of fdbs and provide them with
        their relevant hosts and partitions.

        Any found to not have a host or partition will be dropped.
        """
        hosts = dict()
        for fdb in fdbs:
            segment = fdb.segment_id
            network = fdb.network_id
            try:
                self._get_tunnels_by_designation(
                    network, segment, hosts=hosts, fdb=fdb)
            except KeyError:
                continue
        return hosts

    def get_tunnels_by_designation(self, network_id, segment):
        """Retrieves a {bigip_host:[Tunnel]} for network_id and segment given

        This will return the described dict structure for a given network and
        segment as constructed by objects in the cache.
        """
        try:
            hosts = self._get_tunnels_by_designation(network_id, segment)
        except KeyError:
            return dict()
        return hosts

    def _get_tunnels_by_designation(self, network_id, segment, hosts=dict(),
                                    fdb=None):
        segment = str(segment)
        tunnels = self.__network_cache.get(network_id, {}).get(segment, [])
        for tunnel in tunnels:
            tunnel.tunnel_name
            if fdb and tunnel.local_address == fdb.vtep_ip:
                return
            host = tunnel.bigip_host
            if fdb:
                level = hosts.get(host, [[], []])
                level[0].append(tunnel)
                level[1].append(fdb)
                hosts[host] = level
            else:
                level = hosts.get(host, [])
                level.append(tunnel)
                hosts[host] = level
        return hosts

    network_cache = property(_get_network_cache, _add_to_network_cache)
