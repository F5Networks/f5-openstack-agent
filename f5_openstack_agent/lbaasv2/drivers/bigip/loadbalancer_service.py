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

LOG = logging.getLogger(__name__)


class LoadBalancerServiceBuilder(object):
    """Create loadbalancer related objects on BIG-IPs

    Handles requests to create and delete LBaaS v2 tenant partition
    folders on one or more BIG-IP systems.
    """
    def __init__(self, plugin_const, plugin_rpc):
        self.plugin_const = plugin_const
        self.plugin_rpc = plugin_rpc
        self.folder_helper = BigIPResourceHelper(ResourceType.folder)
