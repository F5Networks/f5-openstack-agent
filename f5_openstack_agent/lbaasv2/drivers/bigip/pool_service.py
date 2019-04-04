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

    def __init__(self, service_adapter, f5_parent_https_monitor=None):
        self.service_adapter = service_adapter
        self.http_mon_helper = BigIPResourceHelper(ResourceType.http_monitor)
        self.https_mon_helper = BigIPResourceHelper(ResourceType.https_monitor)
        self.tcp_mon_helper = BigIPResourceHelper(ResourceType.tcp_monitor)
        self.ping_mon_helper = BigIPResourceHelper(ResourceType.ping_monitor)
        self.pool_helper = BigIPResourceHelper(ResourceType.pool)
        self.node_helper = BigIPResourceHelper(ResourceType.node)
        self.f5_parent_https_monitor = f5_parent_https_monitor

    def create_pool(self, service, bigips):
        """Create a pool on set of BIG-IPs.

        Creates a BIG-IP pool to represent an LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create pool.
        """
        pool = self.service_adapter.get_pool(service)
        ex = None
        for bigip in bigips:
            try:
                self.pool_helper.create(bigip, pool)
                LOG.info("Pool created: %s", pool['name'])
            except HTTPError as err:
                if err.response.status_code == 409:
                    LOG.info("Pool already exists...updating")
                    try:
                        self.pool_helper.update(bigip, pool)
                        LOG.info("Pool updated: %s", pool['name'])
                    except Exception as err:
                        ex = err
                        LOG.error("Pool creation/update FAILED for pool %s on %s: %s",
                                  pool['name'], bigip, err.message)
                else:
                    ex = err
                    LOG.error("Pool creation FAILED for pool %s on %s: %s",
                              pool['name'], bigip, err.message)

        if ex:
            raise ex


    def delete_pool(self, service, bigips):
        """Delete a pool on set of BIG-IPs.

        Deletes a BIG-IP pool defined by LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete pool.
        """
        pool = self.service_adapter.get_pool(service)
        ex = None
        for bigip in bigips:
            try:
                self.pool_helper.delete(bigip,
                                        name=pool["name"],
                                        partition=pool["partition"])
                LOG.info("Pool deleted: %s", pool['name'])
            except HTTPError as err:
                LOG.info("Pool deletion FAILED: %s", pool['name'])
                ex = err
        if ex:
            raise ex


    def update_pool(self, service, bigips):
        """Update BIG-IP pool.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create pool.
        """
        pool = self.service_adapter.get_pool(service)
        ex = None
        for bigip in bigips:
            try:
                self.pool_helper.update(bigip, pool)
                LOG.info("Pool updated FAILED: %s", pool['name'])
            except HTTPError as err:
                LOG.info("Pool update FAILED: %s", pool['name'])
                ex = err
        if ex:
            raise ex


    def create_healthmonitor(self, service, bigips):
        # create member
        hm = self.service_adapter.get_healthmonitor(service)
        #ccloud: set additional attributes like parent monitor in case of creation, might be ignored for update
        self._set_monitor_attributes(service, hm)
        hm_helper = self._get_monitor_helper(service)
        pool = self.service_adapter.get_pool(service)

        ex = None
        for bigip in bigips:
            try:
                hm_helper.create(bigip, hm)
                # update pool with new health monitor
                self.pool_helper.update(bigip, pool)
                LOG.info("Health Monitor created: %s", hm['name'])
            except HTTPError as err:
                if err.response.status_code == 409:
                    try:
                        hm_helper.update(bigip, hm)
                        LOG.info("Health Monitor upserted: %s", hm['name'])
                    except Exception as err:
                        ex = err
                        LOG.error("Failed to upsert monitor %s on %s: %s",
                                  hm['name'], bigip, err.message)
                else:
                    ex = err
                    LOG.error("Failed to upsert monitor %s on %s: %s",
                              hm['name'], bigip, err.message)
        if ex:
            raise ex


    def delete_healthmonitor(self, service, bigips):
        # delete health monitor
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)

        # update pool
        pool = self.service_adapter.get_pool(service)
        pool["monitor"] = ""

        ex = None
        for bigip in bigips:
            try:
                # need to first remove monitor reference from pool
                self.pool_helper.update(bigip, pool)
                # after updating pool, delete monitor
                hm_helper.delete(bigip,
                                 name=hm["name"],
                                 partition=hm["partition"])
                LOG.info("Health Monitor deleted: %s", hm['name'])
            except HTTPError as err:
                LOG.info("Health Monitor deletion FAILED: %s", hm['name'])
                ex = err
        if ex:
            raise ex

    def update_healthmonitor(self, service, bigips):
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)
        pool = self.service_adapter.get_pool(service)

        ex = None
        for bigip in bigips:
            try:
                hm_helper.update(bigip, hm)
                # update pool with new health monitor
                self.pool_helper.update(bigip, pool)
                LOG.info("Health Monitor updated: %s", hm['name'])
            except HTTPError as err:
                LOG.info("Health Monitor update FAILED: %s", hm['name'])
                ex = err
        if ex:
            raise ex

    # Note: can't use BigIPResourceHelper class because members
    # are created within pool objects. Following member methods
    # use the F5 SDK directly.
    def create_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        if '%' not in member['address'] or '%0' in member['address']:
            LOG.error("ccloud: POOL-RDCHECK1 - trying to create member with address: %s", member['address'])

        ex = None
        for bigip in bigips:
            try:
                part = pool["partition"]
                p = self.pool_helper.load(bigip,
                                          name=pool["name"],
                                          partition=part)
                m = p.members_s.members
                m.create(**member)
                LOG.info("Member created: %s", member['address'])
            except HTTPError as err:
                LOG.info("Member creation FAILED: %s", member['address'])
                ex = err
        if ex:
            raise ex

    def delete_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        if '%' not in member['address'] or '%0' in member['address']:
            LOG.error("ccloud: POOL-RDCHECK2 - trying to create member with address: %s", member['address'])
        part = pool["partition"]

        ex = None
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

                try:
                    m.delete()
                    LOG.info("Member deleted: %s", member['address'])

                    node = self.service_adapter.get_member_node(service)
                    self.node_helper.delete(bigip,
                                            name=urllib.quote(node["name"]),
                                            partition=node["partition"])
                    LOG.info("Node deleted: %s", node["name"])
                except HTTPError as err:
                    # Possilbe error if node is shared with another member.
                    # If so, ignore the error.
                    if err.response.status_code == 400:
                        LOG.debug(err.message)
                    else:
                        LOG.info("Member or Node deletion FAILED: %s", member['address'])
                        ex = err
        if ex:
            raise ex

    def update_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        if '%' not in member['address'] or '%0' in member['address']:
            LOG.error("ccloud: POOL-RDCHECK3 - trying to create member with address: %s", member['address'])
        part = pool["partition"]

        ex = None
        for bigip in bigips:
            try:
                p = self.pool_helper.load(bigip,
                                          name=pool["name"],
                                          partition=part)

                m = p.members_s.members
                if m.exists(name=urllib.quote(member["name"]), partition=part):
                    m = m.load(name=urllib.quote(member["name"]),
                               partition=part)
                    member.pop("address", None)
                    m.modify(**member)
                    #LOG.info("Member updated: %s", member['address'])
            except HTTPError as err:
                #LOG.info("Member update FAILED: %s", member['address'])
                ex = err
        if ex:
            raise ex

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

    def _set_monitor_attributes(self, service, monitor):
        monitor_type = self.service_adapter.get_monitor_type(service)
        if monitor_type == "HTTPS":
            if self.f5_parent_https_monitor:
                monitor['defaultsFrom'] = self.f5_parent_https_monitor

    def member_exists(self, service, bigip):
        """Return True if a member exists in a pool.

        :param service: Has pool and member name/partition
        :param bigip: BIG-IP to get member status from.
        :return: Boolean
        """
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        part = pool["partition"]
        try:
            p = self.pool_helper.load(bigip,
                                      name=pool["name"],
                                      partition=part)

            m = p.members_s.members
            if m.exists(name=urllib.quote(member["name"]), partition=part):
                return True
        except Exception as e:
            # log error but continue on
            LOG.error("Error checking member exists: %s", e.message)
        return False

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
                LOG.warning("Unable to get member status. Member %s does not exist.", member["name"])

        except Exception as e:
            # log error but continue on
            LOG.error("Error getting member status: %s", e.message)

        return member_status
