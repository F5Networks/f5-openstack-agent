# coding=utf-8
# Copyright (c) 2014-2018, F5 Networks, Inc.
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

from requests import HTTPError
import urllib

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper


LOG = logging.getLogger(__name__)


class PoolServiceBuilder(object):
    """Create LBaaS v2 pools and related objects on BIG-IPs.

    Handles requests to create, update, delete LBaaS v2 pools,
    health monitors, and members on one or more BIG-IP systems.
    """

    def __init__(self, service_adapter):
        self.service_adapter = service_adapter
        self.http_mon_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.http_monitor)
        self.https_mon_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.https_monitor)
        self.tcp_mon_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.tcp_monitor)
        self.ping_mon_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.ping_monitor)
        self.pool_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)
        self.node_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.node)

    def create_pool(self, service, bigips):
        """Create a pool on set of BIG-IPs.

        Creates a BIG-IP pool to represent an LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create pool.
        """
        pool = self.service_adapter.get_pool(service)

        error = None

        for bigip in bigips:
            try:
                if self.pool_helper.exists(bigip,
                                           name=pool['name'],
                                           partition=pool['partition']):
                    LOG.debug("Pool already exists...updating")
                    self.pool_helper.update(bigip, pool)
                else:
                    LOG.debug("Pool does not exist...creating")
                    self.pool_helper.create(bigip, pool)
            except Exception as err:
                error = f5_ex.PoolCreationException(err.message)
                LOG.error("Failed to assure pool %s on %s: %s",
                          pool['name'], bigip, error.message)

        return error

    def delete_pool(self, service, bigips):
        """Delete a pool on set of BIG-IPs.

        Deletes a BIG-IP pool defined by LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete pool.
        """
        loadbalancer = service.get('loadbalancer')
        pool = self.service_adapter.get_pool(service)
        members = service.get('members', list())

        error = None
        for bigip in bigips:
            try:
                self.pool_helper.delete(bigip, name=pool["name"],
                                        partition=pool["partition"])
            except HTTPError as err:
                if err.response.status_code != 404:
                    error = f5_ex.PoolDeleteException(err.message)
                    LOG.error("Failed to remove pool %s from %s: %s",
                              pool['name'], bigip, error.message)
            except Exception as err:
                error = f5_ex.PoolDeleteException(err.message)
                LOG.error("Failed to remove pool %s from %s: %s",
                          pool['name'], bigip, error.message)

            for member in members:
                self._delete_member_node(loadbalancer, member, bigip)

        return error

    def update_pool(self, service, bigips):
        """Update BIG-IP pool.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create pool.
        """
        error = None

        pool = self.service_adapter.get_pool(service)
        for bigip in bigips:
            try:
                self.pool_helper.update(bigip, pool)
            except Exception as err:
                error = f5_ex.PoolUpdateException(err.message)
                LOG.error("Failed to update pool %s from %s: %s",
                          pool['name'], bigip, error.message)

        return error

    def create_healthmonitor(self, service, bigips):
        # create member
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)
        error = None

        for bigip in bigips:
            try:
                if hm_helper.exists(bigip,
                                    name=hm['name'],
                                    partition=hm['partition']):
                    LOG.debug("Health monitor already exists...updating")
                    hm_helper.update(bigip, hm)
                else:
                    LOG.debug("Health monitor does not exist...creating")
                    hm_helper.create(bigip, hm)
            except Exception as err:
                error = f5_ex.MonitorCreationException(err.message)
                LOG.error("Failed to create monitor %s on %s: %s",
                          hm['name'], bigip, error.message)

        return error

    def delete_healthmonitor(self, service, bigips):
        # delete health monitor
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)
        error = None

        for bigip in bigips:
            # after updating pool, delete monitor
            try:
                hm_helper.delete(
                    bigip, name=hm["name"], partition=hm["partition"])
            except HTTPError as err:
                if err.response.status_code != 404:
                    error = f5_ex.MonitorDeleteException(err.message)
                    LOG.error("Failed to remove monitor %s from %s: %s",
                              hm['name'], bigip, error.message)
            except Exception as err:
                error = f5_ex.MonitorDeleteException(err.message)
                LOG.error("Failed to remove monitor %s from %s: %s",
                          hm['name'], bigip, error.message)

        return error

    def _delete_member_node(self, loadbalancer, member, bigip):
        error = None
        svc = {'loadbalancer': loadbalancer,
               'member': member}

        node = self.service_adapter.get_member_node(svc)
        try:
            self.node_helper.delete(bigip,
                                    name=urllib.quote(node['name']),
                                    partition=node['partition'])
        except HTTPError as err:
            # Possilbe error if node is shared with another member.
            # If so, ignore the error.
            if err.response.status_code == 400:
                LOG.debug(str(err))
            elif err.response.status_code == 404:
                LOG.debug(str(err))
            else:
                LOG.error("Unexpected node deletion error: %s",
                          urllib.quote(node['name']))
                error = f5_ex.NodeDeleteException(
                    "Unable to delete node {}".format(
                        urllib.quote(node['name'])))

        return error

    def assure_pool_members(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        partition = pool["partition"]
        loadbalancer = service.get('loadbalancer')

        for bigip in bigips:
            pool_loaded = True
            try:
                p = self.pool_helper.load(bigip,
                                          name=pool["name"],
                                          partition=partition)
                m = p.members_s.members
            except HTTPError as err:
                LOG.error("Unabled to load pool %s: %s",
                          pool["name"], err.message)
                pool_loaded = False

            for member in service.get('members', list()):
                svc = {'loadbalancer': loadbalancer,
                       'member': member}

                if member.get('provisioning_status') == "PENDING_DELETE":
                    self._delete_member_node(loadbalancer, member, bigip)
                    continue

                bigip_member = self.service_adapter.get_member(svc)

                member_exists = pool_loaded and m.exists(
                    name=urllib.quote(bigip_member["name"]),
                    partition=partition)

                if not member_exists:
                    member['missing'] = True

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
                LOG.error("Unable to get member status. "
                          "Member %s does not exist.", member["name"])

        except Exception as e:
            # log error but continue on
            LOG.error("Error getting member status: %s", e.message)

        return member_status
