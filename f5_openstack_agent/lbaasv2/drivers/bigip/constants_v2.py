"""F5 LBaaSv2 constants for agent."""
# Copyright 2014 F5 Networks Inc.
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

# Service resync interval
RESYNC_INTERVAL = 300

# Topic for tunnel notifications between the plugin and agent
TUNNEL = 'tunnel'

# Values for network_type
TYPE_FLAT = 'flat'
TYPE_VLAN = 'vlan'
TYPE_GRE = 'gre'
TYPE_LOCAL = 'local'
TYPE_VXLAN = 'vxlan'
VXLAN_UDP_PORT = 4789
VTEP_SELFIP_NAME = 'vtep'

AGENT_BINARY_NAME = 'f5-oslbaasv2-agent'

# RPC channel names
TOPIC_PROCESS_ON_HOST_V2 = 'f5-lbaasv2-process-on-controller'
TOPIC_LOADBALANCER_AGENT_V2 = 'f5-lbaasv2-process-on-agent'

RPC_API_VERSION = '1.0'
