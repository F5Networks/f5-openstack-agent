# coding=utf-8
# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from enum import Enum
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import get_filter

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class ResourceType(Enum):
    u"""Defines supported BIG-IP® resource types."""

    nat = 1
    pool = 2
    sys = 3
    virtual = 4
    member = 5
    folder = 6
    http_monitor = 7
    https_monitor = 8
    tcp_monitor = 9
    ping_monitor = 10
    node = 11
    snat = 12
    snatpool = 13
    snat_translation = 14
    selfip = 15
    rule = 16
    vlan = 17
    arp = 18
    route_domain = 19
    tunnel = 20


class BigIPResourceHelper(object):
    u"""Helper class for creating, updating and deleting BIG-IP® resources.

    Reduces some of the boilerplate that surrounds using the F5® SDK.
    Example usage:
        bigip = BigIP("10.1.1.1", "admin", "admin")
        pool = {"name": "pool1",
                "partition": "Common",
                "description": "Default pool",
                "loadBalancingMode": "round-robin"}
        pool_helper = BigIPResourceHelper(ResourceType.pool)
        p = pool_helper.create(bigip, pool)
    """

    def __init__(self, resource_type):
        """Initialize a resource helper."""
        self.resource_type = resource_type

    def create(self, bigip, model):
        u"""Create/update resource (e.g., pool) on a BIG-IP® system.

        First checks to see if resource has been created and creates
        it if not. If the resource is already created, updates resource
        with model attributes.

        :param bigip: BigIP instance to use for creating resource.
        :param model: Dictionary of BIG-IP® attributes to add resource. Must
        include name and partition.
        :returns: created or updated resource object.
        """
        resource = self._resource(bigip)
        partition = None
        if "partition" in model:
            partition = model["partition"]
        if resource.exists(name=model["name"], partition=partition):
            obj = self.update(bigip, model)
        else:
            obj = resource.create(**model)

        return obj

    def exists(self, bigip, name=None, partition=None):
        """Test for the existence of a resource."""
        resource = self._resource(bigip)
        return resource.exists(name=name, partition=partition)

    def delete(self, bigip, name=None, partition=None):
        u"""Delete a resource on a BIG-IP® system.

        Checks if resource exists and deletes it. Returns without error
        if resource does not exist.

        :param bigip: BigIP instance to use for creating resource.
        :param name: Name of resource to delete.
        :param partition: Partition name for resou
        """
        resource = self._resource(bigip)
        if resource.exists(name=name, partition=partition):
            obj = resource.load(name=name, partition=partition)
            obj.delete()

    def load(self, bigip, name=None, partition=None):
        u"""Retrieve a BIG-IP® resource from a BIG-IP®.

        Populates a resource object with attributes for instance on a
        BIG-IP® system.

        :param bigip: BigIP instance to use for creating resource.
        :param name: Name of resource to load.
        :param partition: Partition name for resource.
        :returns: created or updated resource object.
        """
        resource = self._resource(bigip)
        return resource.load(name=name, partition=partition)

    def update(self, bigip, model):
        u"""Update a resource (e.g., pool) on a BIG-IP® system.

        Modifies a resource on a BIG-IP® system using attributes
        defined in the model object.

        :param bigip: BigIP instance to use for creating resource.
        :param model: Dictionary of BIG-IP® attributes to update resource.
        Must include name and partition in order to identify resource.
        """
        partition = None
        if "partition" in model:
            partition = model["partition"]
        resource = self.load(bigip, name=model["name"], partition=partition)
        resource.modify(**model)

        return resource

    def get_resources(self, bigip, partition=None):
        u"""Retrieve a collection BIG-IP® of resources from a BIG-IP®.

        Generates a list of resources objects on a BIG-IP® system.

        :param bigip: BigIP instance to use for creating resource.
        :param name: Name of resource to load.
        :param partition: Partition name for resource.
        :returns: list of created or updated resource objects.
        """
        resources = []
        try:
            collection = self._collection(bigip)
        except KeyError as err:
            LOG.exception(err.message)
            raise err

        if collection:
            if partition:
                params = {
                    'params': get_filter(bigip, 'partition', 'eq', partition)
                }
                resources = collection.get_collection(requests_params=params)
            else:
                resources = collection.get_collection()

        return resources

    def _resource(self, bigip):
        return {
            ResourceType.nat: lambda bigip: bigip.tm.ltm.nats.nat,
            ResourceType.pool: lambda bigip: bigip.tm.ltm.pools.pool,
            ResourceType.sys: lambda bigip: bigip.tm.sys,
            ResourceType.virtual: lambda bigip: bigip.tm.ltm.virtuals.virtual,
            ResourceType.member: lambda bigip: bigip.tm.ltm.pools.pool.member,
            ResourceType.folder: lambda bigip: bigip.tm.sys.folders.folder,
            ResourceType.http_monitor:
                lambda bigip: bigip.tm.ltm.monitor.https.http,
            ResourceType.https_monitor:
                lambda bigip: bigip.tm.ltm.monitor.https_s.https,
            ResourceType.tcp_monitor:
                lambda bigip: bigip.tm.ltm.monitor.tcps.tcp,
            ResourceType.ping_monitor:
                lambda bigip: bigip.tm.ltm.monitor.gateway_icmps.gateway_icmp,
            ResourceType.node: lambda bigip: bigip.tm.ltm.nodes.node,
            ResourceType.snat: lambda bigip: bigip.tm.ltm.snats.snat,
            ResourceType.snatpool:
                lambda bigip: bigip.tm.ltm.snatpools.snatpool,
            ResourceType.snat_translation:
                lambda bigip: bigip.tm.ltm.snat_translations.snat_translation,
            ResourceType.selfip:
                lambda bigip: bigip.tm.net.selfips.selfip,
            ResourceType.rule:
                lambda bigip: bigip.tm.ltm.rules.rule,
            ResourceType.vlan:
                lambda bigip: bigip.tm.net.vlans.vlan,
            ResourceType.arp:
                lambda bigip: bigip.tm.net.arps.arp,
            ResourceType.route_domain:
                lambda bigip: bigip.tm.net.route_domains.route_domain,
            ResourceType.tunnel:
                lambda bigip: bigip.tm.net.tunnels.tunnels.tunnel
        }[self.resource_type](bigip)

    def _collection(self, bigip):
        collection_map = {
            ResourceType.nat: lambda bigip: bigip.tm.ltm.nats,
            ResourceType.pool: lambda bigip: bigip.tm.ltm.pools,
            ResourceType.sys: lambda bigip: bigip.tm.sys,
            ResourceType.virtual: lambda bigip: bigip.tm.ltm.virtuals,
            ResourceType.member: lambda bigip: bigip.tm.ltm.pools.pool.member,
            ResourceType.folder: lambda bigip: bigip.tm.sys.folders,
            ResourceType.http_monitor:
                lambda bigip: bigip.tm.ltm.monitor.https,
            ResourceType.https_monitor:
                lambda bigip: bigip.tm.ltm.monitor.https_s,
            ResourceType.tcp_monitor:
                lambda bigip: bigip.tm.ltm.monitor.tcps,
            ResourceType.ping_monitor:
                lambda bigip: bigip.tm.ltm.monitor.gateway_icmps,
            ResourceType.node: lambda bigip: bigip.tm.ltm.nodes,
            ResourceType.snat: lambda bigip: bigip.tm.ltm.snats,
            ResourceType.snatpool:
                lambda bigip: bigip.tm.ltm.snatpools,
            ResourceType.snat_translation:
                lambda bigip: bigip.tm.ltm.snat_translations,
            ResourceType.selfip:
                lambda bigip: bigip.tm.net.selfips,
            ResourceType.rule:
                lambda bigip: bigip.tm.ltm.rules,
            ResourceType.route_domain:
                lambda bigip: bigip.tm.net.route_domains,
            ResourceType.vlan:
                lambda bigip: bigip.tm.net.vlans,
            ResourceType.arp:
                lambda bigip: bigip.tm.net.arps,
            ResourceType.tunnel:
                lambda bigip: bigip.tm.net.tunnels.tunnels,
        }

        if self.resource_type in collection_map:
            return collection_map[self.resource_type](bigip)
        else:
            LOG.error("Error attempting to get collection for "
                      "resource %s", self.resource_type)
            raise KeyError("No collection available for %s" %
                           (self.resource_type))
