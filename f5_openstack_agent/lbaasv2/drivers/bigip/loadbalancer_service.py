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

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter \
    import ServiceModelAdapter

LOG = logging.getLogger(__name__)


class LoadBalancerServiceBuilder(object):
    """Create loadbalancer related objects on BIG-IP®s

    Handles requests to create and delete LBaaS v2 tenant partition
    folders on one or more BIG-IP® systems.
    """
    def __init__(self):
        self.folder_helper = BigIPResourceHelper(ResourceType.folder)

    def create_partition(self, service, bigips):
        """Create tenant partition on set of BIG-IP®s.

        Creates a partition if it is not named "Common".

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create Listener.
        """
        folder = ServiceModelAdapter.get_partition(service)
        if folder != "Common":
            for bigip in bigips:
                self.folder_helper.create(bigip, folder)

    def delete_partition(self, service, bigips):
        """Deletes partition from a set of BIG-IP® systems.

        Deletes partition if it is not named "Common".

        :param service: Dictionary which contains a load balancer definition.
        :param bigips: Array of BigIP class instances to delete partition.
        """
        folder = ServiceModelAdapter.get_partition(service)
        if folder != "Common":
            for bigip in bigips:
                self.folder_helper.delete(bigip, name=folder["name"])

    def prep_service(self, service, bigips):
        """Prepares for LBaaS service request by creating partition.

        Creates partition, if not Common, and sets partition name on
        service loadbalancer.

        :param service: service object for request.
        :param bigips: Array of BigIP class instances to delete partition.
        """

        # create partition if not Common
        self.create_partition(service, bigips)

        # set partition name on loadbalancer object
        ServiceModelAdapter.set_partition(service)
