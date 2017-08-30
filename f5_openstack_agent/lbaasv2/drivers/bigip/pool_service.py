# coding=utf-8
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

from oslo_log import log as logging

from requests import HTTPError
import urllib

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

LOG = logging.getLogger(__name__)


class PoolServiceBuilder(object):
    """Create LBaaS v2 pools and related objects on BIG-IPs.

    Handles requests to create, update, delete LBaaS v2 pools,
    health monitors, and members on one or more BIG-IP systems.
    """

    def __init__(self, service_adapter):
        self.service_adapter = service_adapter
        self.http_mon_helper = BigIPResourceHelper(ResourceType.http_monitor)
        self.https_mon_helper = BigIPResourceHelper(ResourceType.https_monitor)
        self.tcp_mon_helper = BigIPResourceHelper(ResourceType.tcp_monitor)
        self.ping_mon_helper = BigIPResourceHelper(ResourceType.ping_monitor)
        self.pool_helper = BigIPResourceHelper(ResourceType.pool)
        self.node_helper = BigIPResourceHelper(ResourceType.node)

    def create_pool(self, service, bigips):
        """Create a pool on set of BIG-IPs.

        Creates a BIG-IP pool to represent an LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create pool.
        """
        pool = self.service_adapter.get_pool(service)
        for bigip in bigips:
            self.pool_helper.create(bigip, pool)

    def delete_pool(self, service, bigips):
        """Delete a pool on set of BIG-IPs.

        Deletes a BIG-IP pool defined by LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete pool.
        """
        pool = self.service_adapter.get_pool(service)

        for bigip in bigips:
            self.pool_helper.delete(bigip,
                                    name=pool["name"],
                                    partition=pool["partition"])

    def update_pool(self, service, bigips):
        """Update BIG-IP pool.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create pool.
        """
        pool = self.service_adapter.get_pool(service)
        for bigip in bigips:
            self.pool_helper.update(bigip, pool)

    def create_healthmonitor(self, service, bigips):
        # create member
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)
        pool = self.service_adapter.get_pool(service)

        for bigip in bigips:
            hm_helper.create(bigip, hm)

            # update pool with new health monitor
            self.pool_helper.update(bigip, pool)

    def delete_healthmonitor(self, service, bigips):
        # delete health monitor
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)

        # update pool
        pool = self.service_adapter.get_pool(service)
        pool["monitor"] = ""

        for bigip in bigips:
            # need to first remove monitor reference from pool
            self.pool_helper.update(bigip, pool)

            # after updating pool, delete monitor
            hm_helper.delete(bigip,
                             name=hm["name"],
                             partition=hm["partition"])

    def update_healthmonitor(self, service, bigips):
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)
        pool = self.service_adapter.get_pool(service)

        for bigip in bigips:
            hm_helper.update(bigip, hm)

            # update pool with new health monitor
            self.pool_helper.update(bigip, pool)

    # Note: can't use BigIPResourceHelper class because members
    # are created within pool objects. Following member methods
    # use the F5 SDK directly.
    def create_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        for bigip in bigips:
            part = pool["partition"]
            p = self.pool_helper.load(bigip,
                                      name=pool["name"],
                                      partition=part)
            m = p.members_s.members
            m.create(**member)

    def delete_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        part = pool["partition"]
        for bigip in bigips:
            p = self.pool_helper.load(bigip,
                                      name=pool["name"],
                                      partition=part)

            m = p.members_s.members
            member_exists = m.exists(name=urllib.quote(member["name"]),
                                     partition=part)
            if member_exists:
                m = m.load(name=urllib.quote(member["name"]),
                           partition=part)

                m.delete()
                try:
                    node = self.service_adapter.get_member_node(service)
                    self.node_helper.delete(bigip,
                                            name=urllib.quote(node["name"]),
                                            partition=node["partition"])
                except HTTPError as err:
                    # Possilbe error if node is shared with another member.
                    # If so, ignore the error.
                    if err.response.status_code == 400:
                        LOG.debug(err.message)
                    else:
                        raise

    def update_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)

        part = pool["partition"]
        for bigip in bigips:
            p = self.pool_helper.load(bigip,
                                      name=pool["name"],
                                      partition=part)

            m = p.members_s.members
            if m.exists(name=urllib.quote(member["name"]), partition=part):
                m = m.load(name=urllib.quote(member["name"]),
                           partition=part)
                member.pop("address", None)
                m.modify(**member)

    def _get_monitor_helper(self, service):
        monitor_type = self.service_adapter.get_monitor_type(service)
        if monitor_type == "HTTPS":
            hm = self.https_mon_helper
        elif monitor_type == "TCP":
            hm = self.tcp_mon_helper
        elif monitor_type == "PING":
            hm = self.ping_mon_helper
        else:
            hm = self.http_mon_helper
        return hm

    def get_member_status(self, service, bigip, status_keys):
        """Return status values for a single pool.

        Status keys to collect are defined as an array of strings in input
        status_keys.

        :param service: Has pool and member name/partition
        :param bigip: BIG-IP to get member status from.
        :param status_keys: Array of strings that define which status keys to
        collect.
        :return: A dict with key/value pairs for each status defined in
        input status_keys.
        """
        member_status = {}
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        part = pool["partition"]
        try:
            p = self.pool_helper.load(bigip,
                                      name=pool["name"],
                                      partition=part)

            m = p.members_s.members
            if m.exists(name=urllib.quote(member["name"]), partition=part):
                m = m.load(name=urllib.quote(member["name"]), partition=part)
                member_status = self.pool_helper.collect_stats(
                    m, stat_keys=status_keys)
            else:
                LOG.error("Unable to get member status. "
                          "Member %s does not exist.", member["name"])

        except Exception as e:
            # log error but continue on
            LOG.error("Error getting member status: %s", e.message)

        return member_status
