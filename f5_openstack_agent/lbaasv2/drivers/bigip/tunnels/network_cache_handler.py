"""A module that hosts the logic to hold, handle, and update the Network Cache

This module hosts the singleton object-class NetworkCacheHandler.  This
object, as singletone would imply, should only exist in one instance per agent
instance and be held within the AgentManager singleton object.

This library simply hosts this cache handler.
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

import weakref

from oslo_log import log as logging

import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.cache as cache
# import f5_openstack_agent.lbaasv2.drivers.bigip.network_helper

LOG = logging.getLogger(__name__)


def handle_weakref(method):
    def wrapper(instance, network, seg_id, segmentation, cnt):
        try:
            return method(instance, network, seg_id, segmentation, cnt)
        except weakref.ReferenceError:
            segmentation.pop(cnt)
            LOG.debug("Network: '{}', Segment: '{}' being cleared from "
                      "cache".format(network, seg_id))
            return None
    return wrapper


class NetworkCacheHandler(cache.CacheBase):
    """Handler for the Network Cache

    This singleton object handles the Network Cache.  As such, the general
    use-case is to simply call one of the methods it offers for the
    updating of such information or, as such, orchestration.
    """
    def __init__(self):
        self.__existing_tunnels = []
        self.__network_cache = {}
        super(NetworkCacheHandler, self).__init__()

    @cache.lock
    def _add_to_network_cache(self, tunnel):
        # Locks and finally stores the new tunnel within the __network_cache.
        # this being the crux of this design, has to be as solid as possible
        tunnel_proxy = weakref.proxy(tunnel)
        network_id, segment_id = tunnel.network_id, tunnel.segment_id
        network = self.__network_cache.get(network_id, dict())
        segment = network.get(segment_id, list())
        segment.append(tunnel_proxy)
        network[segment_id] = segment  # a re-reference is cheap
        self.__network_cache[network_id] = network
        self.__existing_tunnels.append(tunnel)

    def _get_network_cache(self):
        # A placeholder get method
        raise NotImplementedError("Not currently set up to return the cache")

    @cache.lock
    def remove_tunnel(self, bigip_host, tunnel=None, name=None,
                      partition=None):
        """Removes a Tunnel object instance from the cache

        This method will take a Tunnel object and remove it from the list
        __existing_tunnels.

        As this is the hard reference to the tunnel object, it will leave the
        __network_cache's instance pointing to None.  This will be handled in
        check_fdbs appropriately enough to not fail, and remove them to no
        longer cause issues.
        """
        retval = None
        if tunnel:
            try:
                self.__existing_tunnels.remove(tunnel)
                retval = tunnel
            except ValueError:
                pass
        elif name and partition:
            for cnt, tunnel in enumerate(self.__existing_tunnels):
                if tunnel.tunnel_name == name and \
                        partition == tunnel.partition:
                    retval = self.__existing_tunnels.pop(cnt)
                    break
        else:
            raise ValueError("Cannot operate without name & partition or "
                             "tunnel")
        return retval

    @handle_weakref
    def __check_network_segment(self, network, seg_id, segment, cnt):
        tunnel = segment[cnt]
        return (tunnel.bigip_host, tunnel.partition, tunnel)

    @cache.lock
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
                tunnels = self.__network_cache[network][segment]
            except KeyError:
                continue
            for tunnel in tunnels:
                if tunnel.local_address == fdb.vtep_ip:
                    continue
                host = tunnel.bigip_host
                level = hosts.get(host, [[], []])
                level[0].append(tunnel)
                level[1].append(fdb)
                hosts[host] = level
        return hosts

    network_cache = property(_get_network_cache, _add_to_network_cache)
