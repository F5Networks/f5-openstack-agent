"""F5 LBaaSv2 constants for agent."""
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

# Service resync interval
RESYNC_INTERVAL = 300
UPDATE_OPERATING_STATUS_INTERVAL = 30


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

DEFAULT_PARTITION = 'Common'
DEFAULT_ROUTE_DOMAIN_ID = 0

# RPC channel names
TOPIC_PROCESS_ON_HOST_V2 = 'f5-lbaasv2-process-on-controller'
TOPIC_LOADBALANCER_AGENT_V2 = 'f5-lbaasv2-process-on-agent'

RPC_API_VERSION = '1.0'
# RPC_API_NAMESPACE = ""

FDB_POPULATE_STATIC_ARP = True
# for test only
MIN_EXTRA_MB = 0
# MIN_EXTRA_MB = 500

MIN_TMOS_MAJOR_VERSION = 11
MIN_TMOS_MINOR_VERSION = 0

DEVICE_DEFAULT_DOMAIN = ".local"
DEVICE_HEALTH_SCORE_CPU_WEIGHT = 1
DEVICE_HEALTH_SCORE_MEM_WEIGHT = 1
DEVICE_HEALTH_SCORE_CPS_WEIGHT = 1
DEVICE_HEALTH_SCORE_CPS_PERIOD = 5
DEVICE_HEALTH_SCORE_CPS_MAX = 100

DEVICE_CONNECTION_TIMEOUT = 5

# Neutron-lbaas and Neutron constants
F5_AGENT_TYPE_LOADBALANCERV2 = 'Loadbalancerv2 agent'
F5_STATS_IN_BYTES = 'bytes_in'
F5_STATS_OUT_BYTES = 'bytes_out'
F5_STATS_ACTIVE_CONNECTIONS = 'active_connections'
F5_STATS_TOTAL_CONNECTIONS = 'total_connections'
F5_OFFLINE = 'OFFLINE'
F5_ONLINE = 'ONLINE'
F5_DISABLED = 'DISABLED'
F5_NO_MONITOR = 'NO_MONITOR'

F5_ACTIVE = 'ACTIVE'
F5_PENDING_CREATE = "PENDING_CREATE"
F5_PENDING_UPDATE = "PENDING_UPDATE"
F5_PENDING_DELETE = "PENDING_DELETE"
F5_ERROR = "ERROR"

ACTIVE = 'ACTIVE'
PENDING_CREATE = "PENDING_CREATE"
PENDING_UPDATE = "PENDING_UPDATE"
PENDING_DELETE = "PENDING_DELETE"
ERROR = "ERROR"

F5_FLOODING_ENTRY = ('00:00:00:00:00:00', '0.0.0.0')

PLUGIN = 'q-plugin'
UPDATE = 'update'
L2POPULATION = 'l2population'
AGENT = 'q-agent-notifier'
