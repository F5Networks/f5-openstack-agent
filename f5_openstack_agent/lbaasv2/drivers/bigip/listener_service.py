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

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper

LOG = logging.getLogger(__name__)


class ListenerServiceBuilder(object):
    """Create LBaaS v2 Listener on BIG-IP®s.

    Handles requests to create, update, delete LBaaS v2 listener
    objects on one or more BIG-IP® systems. Maps LBaaS listener
    defined in service object to a BIG-IP® virtual server.
    """

    def __init__(self, service_adapter):
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.service_adapter = service_adapter

    def create_listener(self, service, bigips):
        """Create listener on set of BIG-IP®s.

        Creates a BIG-IP® virtual server to represent an LBaaS
        Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create Listener.
        """
        vip = self.service_adapter.get_virtual(service)

        for bigip in bigips:
            try:
                self.vs_helper.create(bigip, vip)
            except HTTPError as err:
                LOG.error("Error creating virtual server for listener %s "
                          "on BIG-IP %s. Repsponse status code: %s. Response "
                          "message: %s." % (vip["name"],
                                            bigip.device_name,
                                            err.response.status_code,
                                            err.message))

        # Traffic group is added after create in order to take adavantage
        # of BIG-IP® defaults.
        traffic_group = self.service_adapter.get_traffic_group(service)
        if traffic_group:
            for bigip in bigips:
                try:
                    self.vs_helper.update(bigip, traffic_group)
                except HTTPError as err:
                    LOG.error(
                        "Error updating virtual server for listener %s "
                        "on BIG-IP %s. Repsponse status code: %s. Response "
                        "message: %s." % (vip["name"],
                                          bigip.device_name,
                                          err.response.status_code,
                                          err.message))

    def get_listener(self, service, bigip):
        """Retrieve BIG-IP® virtual from a single BIG-IP® system.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigip: Array of BigIP class instances to create Listener.
        """
        obj = None
        vip = self.service_adapter.get_virtual_name(service)
        try:
            obj = self.vs_helper.load(bigip=bigip,
                                      name=vip["name"],
                                      partition=vip["partition"])
        except HTTPError as err:
            LOG.error("Error loading virtual server for listener %s "
                      "on BIG-IP %s. Repsponse status code: %s. Response "
                      "message: %s." % (vip["name"],
                                        bigip.device_name,
                                        err.response.status_code,
                                        err.message))
        return obj

    def delete_listener(self, service, bigips):
        """Delete Listener from a set of BIG-IP® systems.

        Deletes virtual server that represents a Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete Listener.
        """
        vip = self.service_adapter.get_virtual_name(service)
        for bigip in bigips:
            try:
                self.vs_helper.delete(bigip,
                                      name=vip["name"],
                                      partition=vip["partition"])
            except HTTPError as err:
                LOG.error(
                    "Error deleting virtual server for listener %s "
                    "on BIG-IP %s. Repsponse status code: %s. Response "
                    "message: %s." % (vip["name"],
                                      bigip.device_name,
                                      err.response.status_code,
                                      err.message))

    def update_listener(self, service, bigips):
        """Update Listener from a single BIG-IP® system.

        Updates virtual servers that represents a Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to update.
        """
        vip = self.service_adapter.get_virtual(service)

        for bigip in bigips:
            try:
                self.vs_helper.update(bigip, vip)
            except HTTPError as err:
                LOG.error(
                    "Error updating virtual server for listener %s "
                    "on BIG-IP %s. Repsponse status code: %s. Response "
                    "message: %s." % (vip["name"],
                                      bigip.device_name,
                                      err.response.status_code,
                                      err.message))
