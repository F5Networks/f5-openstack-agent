"""Agent manager to handle plugin to agent RPC and periodic tasks."""
# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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

from neutron.common import config as common_config
from oslo_config import cfg
from oslo_log import log as logging

try:
    from neutron.conf.agent import common as config
except Exception:
    from neutron.agent.common import config

try:
    # q version
    from neutron.conf.agent.common import INTERFACE_OPTS
except Exception:
    # m/n/o/p version
    from neutron.agent.linux.interface import OPTS as INTERFACE_OPTS
import sys

LOG = logging.getLogger(__name__)

# XXX OPTS is used in (at least) agent.py Maybe move/rename to agent.py
OPTS = [
    cfg.StrOpt(
        'f5_agent_mode',
        default='normal',
        help='Select agent mode between normal and lite'
    ),
    cfg.IntOpt(
        'periodic_interval',
        default=600,
        help='Seconds between periodic task runs'
    ),
    cfg.IntOpt(
        'resync_interval',
        default=-1,
        help='Seconds interval for resync task'
    ),
    cfg.IntOpt(
        'config_save_interval',
        default=60,
        help='Seconds interval for config save'
    ),
    cfg.IntOpt(
        'scrub_interval',
        default=-1,
        help='Seconds interval for resync task'
    ),
    cfg.BoolOpt(
        'start_agent_admin_state_up',
        default=True,
        help='Should the agent force its admin_state_up to True on boot'
    ),
    cfg.StrOpt(  # XXX should we use this with internal classes?
        'f5_bigip_lbaas_device_driver',  # XXX maybe remove "device" and "f5"?
        default=('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
                 'iControlDriver'),
        help=('The driver used to provision BigIPs')
    ),
    cfg.BoolOpt(
        'l2_population',
        default=False,
        help=('Use L2 Populate service for fdb entries on the BIG-IP')
    ),
    cfg.BoolOpt(
        'f5_global_routed_mode',
        default=True,
        help=('Disable all L2 and L3 integration in favor of global routing')
    ),
    cfg.BoolOpt(
        'use_namespaces',
        default=True,
        help=('Allow overlapping IP addresses for tenants')
    ),
    cfg.BoolOpt(
        'f5_snat_mode',
        default=True,
        help=('use SNATs, not direct routed mode')
    ),
    cfg.IntOpt(
        'f5_snat_addresses_per_subnet',
        default=1,
        help=('Interface and VLAN for the VTEP overlay network')
    ),
    cfg.StrOpt(
        'provider_name',
        default=None,
        help=('provider_name for snat pool addresses')
    ),
    cfg.StrOpt(
        'availability_zone',
        default=None,
        help=('availability_zone for agent reporting')
    ),
    cfg.StrOpt(
        'vtep_ip',
        default=None,
        help=('vtep ip with service leaf')
    ),
    cfg.StrOpt(
        'agent_id',
        default=None,
        help=('static agent ID to use with Neutron')
    ),
    cfg.StrOpt(
        'static_agent_configuration_data',
        default=None,
        help=('static name:value entries to add to the agent configurations')
    ),
    cfg.IntOpt(
        'service_resync_interval',
        default=86400,
        help=('Number of seconds between service refresh checks')
    ),
    cfg.IntOpt(
        'member_update_interval',
        default=300,
        help=('Number of seconds between member status update')
    ),
    cfg.IntOpt(
        'member_update_mode',
        default=2,
        help=('Mode of the member status update')
    ),
    cfg.IntOpt(
        'member_update_number',
        default=-1,
        help=('number of members in one batch send to neutron'
              ' negative means send all members in on batch')
    ),
    cfg.IntOpt(
        'member_update_agent_number',
        default=1,
        help=('Total number of the agents for thie project')
    ),
    cfg.IntOpt(
        'member_update_agent_order',
        default=0,
        help=('Order of this agent for thie project')
    ),
    cfg.StrOpt(
        'environment_prefix',
        default='Project',
        help=('The object name prefix for this environment')
    ),
    cfg.BoolOpt(
        'environment_specific_plugin',
        default=True,
        help=('Use environment specific plugin topic')
    ),
    cfg.IntOpt(
        'environment_group_number',
        default=1,
        help=('Agent group number for the environment')
    ),
    cfg.DictOpt(
        'capacity_policy',
        default={},
        help=('Metrics to measure capacity and their limits')
    ),
    cfg.IntOpt(
        'f5_pending_services_timeout',
        default=60,
        help=(
            'Amount of time to wait for a pending service to become active')
    ),
    cfg.IntOpt(
        'f5_errored_services_timeout',
        default=60,
        help=(
            'Amount of time to wait for a errored service to become active')
    ),
    cfg.BoolOpt(
        'password_cipher_mode',
        default=False,
        help='The flag indicating the password is plain text or not.'
    ),
    cfg.BoolOpt(
        'esd_auto_refresh',
        default=False,
        help='Enable ESD file periodic refresh'
    ),
    cfg.StrOpt(
        'f5_extended_profile',
        default='',
        help=('The file name of extended profiles definition of a listener')
    ),
    cfg.StrOpt(
        'f5_cipher_policy',
        default='',
        help=('The file name of TLS cipher suites policy definition')
    ),
    cfg.IntOpt(
        'f5_bandwidth_default',
        default=200,
        help=('Default MBtyes value of bandwidth')
    ),
    cfg.IntOpt(
        'f5_bandwidth_max',
        default=10000,
        help=('Maximum MBtyes value of bandwidth')
    ),
    cfg.StrOpt(
        'snat_subnetpool_v4',
        default='',
        help=('Reserved SNAT IPv4 subnetpool id')
    ),
    cfg.StrOpt(
        'snat_subnetpool_v6',
        default='',
        help=('Reserved SNAT IPv6 subnetpool id')
    ),
    cfg.StrOpt(
        'f5_request_logging_profile',
        default='/Common/request-log',
        help=('The request logging profile path on bigip')
    ),
]


def register_f5_opts():
    cfg.CONF.register_opts(OPTS)
    cfg.CONF.register_opts(INTERFACE_OPTS)
    config.register_agent_state_opts_helper(cfg.CONF)
    config.register_root_helper(cfg.CONF)
    common_config.init(sys.argv[1:])
    config.setup_logging()
