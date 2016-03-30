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


class ResourceType(Enum):
    """Defines supported BIG-IP® resource types"""
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


class BigIPResourceHelper(object):
    """Helper class for creating, updating and deleting BIG-IP® resources.

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
        self.resource_type = resource_type

    def create(self, bigip, model):
        """Create/update resource (e.g., pool) on a BIG-IP® system.

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
            resource = self.update(bigip, model)
        else:
            resource.create(**model)

        return resource

    def delete(self, bigip, name=None, partition=None):
        """Delete a resource on a BIG-IP® system.

        Checks if resource exists and deletes it. Returns without error
        if resource does not exist.

        :param bigip: BigIP instance to use for creating resource.
        :param name: Name of resource to delete.
        :param partition: Partition name for resou
        """
        resource = self._resource(bigip)
        if resource.exists(name=name, partition=partition):
            resource.load(name=name, partition=partition)
            resource.delete()

    def load(self, bigip, name=None, partition=None):
        """Retrieves a BIG-IP® resource from a BIG-IP®.

        Populates a resource object with attributes for instance on a
        BIG-IP® system.

        :param bigip: BigIP instance to use for creating resource.
        :param name: Name of resource to load.
        :param partition: Partition name for resource.
        :returns: created or updated resource object.
        """
        resource = self._resource(bigip)
        resource.load(name=name, partition=partition)

        return resource

    def update(self, bigip, model):
        """Updates a resource (e.g., pool) on a BIG-IP® system.

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
        resource.update(**model)

        return resource

    def _resource(self, bigip):
        return {
            ResourceType.nat: lambda bigip: bigip.ltm.nats.nat,
            ResourceType.pool: lambda bigip: bigip.ltm.pools.pool,
            ResourceType.sys: lambda bigip: bigip.sys,
            ResourceType.virtual: lambda bigip: bigip.ltm.virtuals.virtual,
            ResourceType.member: lambda bigip: bigip.ltm.pools.pool.member,
            ResourceType.folder: lambda bigip: bigip.sys.folders.folder,
            ResourceType.http_monitor:
                lambda bigip: bigip.ltm.monitor.https.http,
            ResourceType.https_monitor:
                lambda bigip: bigip.ltm.monitor.https_s.https,
            ResourceType.tcp_monitor:
                lambda bigip: bigip.ltm.monitor.tcps.tcp,
            ResourceType.ping_monitor:
                lambda bigip: bigip.ltm.monitor.gateway_icmps.gateway_icmp,
            ResourceType.node: lambda bigip: bigip.ltm.nodes.node,
            ResourceType.snat: lambda bigip: bigip.ltm.snats.snat,
            ResourceType.snatpool:
                lambda bigip: bigip.ltm.snatpools.snatpool,
            ResourceType.snat_translation:
                lambda bigip: bigip.ltm.snat_translations.snat_translation
        }[self.resource_type](bigip)
