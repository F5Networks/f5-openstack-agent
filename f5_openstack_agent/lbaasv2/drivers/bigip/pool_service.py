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
from requests.exceptions import HTTPError
import urllib

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType

LOG = logging.getLogger(__name__)


class PoolServiceBuilder(object):
    """Create LBaaS v2 pools and related objects on BIG-IP®s.

    Handles requests to create, update, delete LBaaS v2 pools,
    health monitors, and members on one or more BIG-IP® systems.
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
        """Create a pool on set of BIG-IP®s.

        Creates a BIG-IP® pool to represent an LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create Listener.
        """
        pool = self.service_adapter.get_pool(service)
        for bigip in bigips:
            try:
                self.pool_helper.create(bigip, pool)
            except HTTPError as err:
                LOG.error("Error creating pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

    def delete_pool(self, service, bigips):
        """Delete a pool on set of BIG-IP®s.

        Deletes a BIG-IP® pool defined by LBaaS pool object.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete pool.
        """
        pool = self.service_adapter.get_pool(service)

        for bigip in bigips:
            try:
                self.pool_helper.delete(bigip,
                                        name=pool["name"],
                                        partition=pool["partition"])
            except HTTPError as err:
                LOG.error("Error deleting pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

    def update_pool(self, service, bigips):
        """Update BIG-IP® pool.

        :param service: Dictionary which contains a both a pool
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create Listener.
        """
        pool = self.service_adapter.get_pool(service)
        for bigip in bigips:
            try:
                self.pool_helper.update(bigip, pool)
            except HTTPError as err:
                LOG.error("Error updating pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

    def create_healthmonitor(self, service, bigips):
        # create member
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)

        for bigip in bigips:
            try:
                hm_helper.create(bigip, hm)
            except HTTPError as err:
                LOG.error("Error creating health monitor %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (hm["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

        # update pool with new health monitor
        pool = self.service_adapter.get_pool(service)
        for bigip in bigips:
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
            try:
                self.pool_helper.update(bigip, pool)
            except HTTPError as err:
                LOG.error("Error updating pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
            try:
                hm_helper.delete(bigip,
                                 name=hm["name"],
                                 partition=hm["partition"])
            except HTTPError as err:
                LOG.error("Error deleting health monitor %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (hm["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

    def update_healthmonitor(self, service, bigips):
        hm = self.service_adapter.get_healthmonitor(service)
        hm_helper = self._get_monitor_helper(service)
        for bigip in bigips:
            try:
                hm_helper.update(bigip, hm)
            except HTTPError as err:
                LOG.error("Error updating health monitor %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (hm["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

    # Note: can't use BigIPResourceHelper class because members
    # are created within pool objects. Following member methods
    # use the F5® SDK directly.
    def create_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        for bigip in bigips:
            part = pool["partition"]
            try:
                p = self.pool_helper.load(bigip,
                                          name=pool["name"],
                                          partition=part)
            except HTTPError as err:
                LOG.error("Error loading pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
                continue

            m = p.members_s.members
            try:
                member_exists = m.exists(name=urllib.quote(member["name"]),
                                         partition=part)
            except HTTPError as err:
                LOG.error("Error checking if member %s exists on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (member["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
                continue

            if not member_exists:
                try:
                    m.create(**member)
                except HTTPError as err:
                    LOG.error("Error creating member %s on BIG-IP %s. "
                              "Repsponse status code: %s. Response "
                              "message: %s." % (member["name"],
                                                bigip.device_name,
                                                err.response.status_code,
                                                err.message))

    def delete_member(self, service, bigips):
        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        part = pool["partition"]
        for bigip in bigips:
            try:
                p = self.pool_helper.load(bigip,
                                          name=pool["name"],
                                          partition=part)
            except HTTPError as err:
                LOG.error("Error loading pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
                continue

            m = p.members_s.members
            try:
                member_exists = m.exists(name=urllib.quote(member["name"]),
                                         partition=part)
            except HTTPError as err:
                LOG.error("Error checking if member %s exists on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (member["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
                continue

            if member_exists:
                try:
                    m = m.load(name=urllib.quote(member["name"]),
                               partition=part)
                except HTTPError as err:
                    LOG.error("Error loading member %s on BIG-IP %s. "
                              "Repsponse status code: %s. Response "
                              "message: %s." % (member["name"],
                                                bigip.device_name,
                                                err.response.status_code,
                                                err.message))
                    continue
                try:
                    m.delete()
                    node = self.service_adapter.get_member_node(service)
                    self.node_helper.delete(bigip,
                                            name=urllib.quote(node["name"]),
                                            partition=node["partition"])
                except HTTPError as err:
                    LOG.error("Error deleting member %s on BIG-IP %s. "
                              "Repsponse status code: %s. Response "
                              "message: %s." % (member["name"],
                                                bigip.device_name,
                                                err.response.status_code,
                                                err.message))

    def update_member(self, service, bigips):
        # TODO(jl) handle state -- SDK enforces at least state=None

        pool = self.service_adapter.get_pool(service)
        member = self.service_adapter.get_member(service)
        part = pool["partition"]
        for bigip in bigips:
            try:
                p = self.pool_helper.load(bigip,
                                          name=pool["name"],
                                          partition=part)
            except HTTPError as err:
                LOG.error("Error loading pool %s on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (pool["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
                continue

            m = p.members_s.members
            try:
                member_exists = m.exists(name=urllib.quote(member["name"]),
                                         partition=part)
            except HTTPError as err:
                LOG.error("Error checking if member %s exists on BIG-IP %s. "
                          "Repsponse status code: %s. Response "
                          "message: %s." % (member["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))
                continue

            if member_exists:
                try:
                    m = m.load(name=urllib.quote(member["name"]),
                               partition=part)
                except HTTPError as err:
                    LOG.error("Error loading member %s on BIG-IP %s. "
                              "Repsponse status code: %s. Response "
                              "message: %s." % (member["name"],
                                                bigip.device_name,
                                                err.response.status_code,
                                                err.message))
                    continue
                try:
                    m.update(**member)
                except HTTPError as err:
                    LOG.error("Error updating member %s on BIG-IP %s. "
                              "Repsponse status code: %s. Response "
                              "message: %s." % (member["name"],
                                                bigip.device_name,
                                                err.response.status_code,
                                                err.message))

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
