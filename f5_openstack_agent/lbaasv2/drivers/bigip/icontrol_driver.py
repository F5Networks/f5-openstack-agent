# coding=utf-8
#
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

import datetime
import hashlib
import json
import logging as std_logging
import os
import urllib2

from eventlet import greenthread
from time import strftime
from time import time

from neutron.common.exceptions import InvalidConfigurationOption
from neutron.common.exceptions import NeutronException
from neutron.plugins.common import constants as plugin_const
from neutron_lbaas.services.loadbalancer import constants as lb_const

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import importutils

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import \
    ClusterManager
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as f5const
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5ex
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_builder import \
    LBaaSBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_driver import \
    LBaaSBaseDriver
from f5_openstack_agent.lbaasv2.drivers.bigip import network_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.network_service import \
    NetworkServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip import ssl_profile
from f5_openstack_agent.lbaasv2.drivers.bigip import stat_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import \
    SystemHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.tenants import \
    BigipTenantManager
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import serialized
from f5_openstack_agent.lbaasv2.drivers.bigip.virtual_address import \
    VirtualAddress

LOG = logging.getLogger(__name__)

NS_PREFIX = 'qlbaas-'
__VERSION__ = '0.1.1'

# configuration objects specific to iControl driver
# XXX see /etc/neutron/services/f5/f5-openstack-agent.ini
OPTS = [  # XXX maybe we should make this a dictionary
    cfg.StrOpt(
        'bigiq_hostname',
        help='The hostname (name or IP address) to use for the BIG-IQ host'
    ),
    cfg.StrOpt(
        'bigiq_admin_username',
        default='admin',
        help='The admin username to use for BIG-IQ authentication',
    ),
    cfg.StrOpt(
        'bigiq_admin_password',
        default='[Provide password in config file]',
        secret=True,
        help='The admin password to use for BIG-IQ authentication'
    ),
    cfg.StrOpt(
        'openstack_keystone_uri',
        default='http://192.0.2.248:5000/',
        help='The admin password to use for BIG-IQ authentication'
    ),
    cfg.StrOpt(
        'openstack_admin_username',
        default='admin',
        help='The admin username to use for authentication '
             'with the Keystone service'
    ),
    cfg.StrOpt(
        'openstack_admin_password',
        default='[Provide password in config file]',
        secret=True,
        help='The admin password to use for authentication'
             ' with the Keystone service'
    ),
    cfg.StrOpt(
        'bigip_management_username',
        default='admin',
        help='The admin username that the BIG-IQ will use to manage '
             'discovered BIG-IPs'
    ),
    cfg.StrOpt(
        'bigip_management_password',
        default='[Provide password in config file]',
        secret=True,
        help='The admin password that the BIG-IQ will use to manage '
             'discovered BIG-IPs'
    ),
    cfg.StrOpt(
        'f5_device_type', default='external',
        help='What type of device onboarding'
    ),
    cfg.StrOpt(
        'f5_ha_type', default='pair',
        help='Are we standalone, pair(active/standby), or scalen'
    ),
    cfg.ListOpt(
        'f5_external_physical_mappings', default=['default:1.1:True'],
        help='Mapping between Neutron physical_network to interfaces'
    ),
    cfg.StrOpt(
        'f5_vtep_folder', default='Common',
        help='Folder for the VTEP SelfIP'
    ),
    cfg.StrOpt(
        'f5_vtep_selfip_name', default=None,
        help='Name of the VTEP SelfIP'
    ),
    cfg.ListOpt(
        'advertised_tunnel_types', default=['gre', 'vxlan'],
        help='tunnel types which are advertised to other VTEPs'
    ),
    cfg.BoolOpt(
        'f5_populate_static_arp', default=False,
        help='create static arp entries based on service entries'
    ),
    cfg.StrOpt(
        'vlan_binding_driver',
        default=None,
        help='driver class for binding vlans to device ports'
    ),
    cfg.StrOpt(
        'interface_port_static_mappings',
        default=None,
        help='JSON encoded static mapping of'
             'devices to list of '
             'interface and port_id'
    ),
    cfg.StrOpt(
        'l3_binding_driver',
        default=None,
        help='driver class for binding l3 address to l2 ports'
    ),
    cfg.StrOpt(
        'l3_binding_static_mappings', default=None,
        help='JSON encoded static mapping of'
             'subnet_id to list of '
             'port_id, device_id list.'
    ),
    cfg.BoolOpt(
        'f5_route_domain_strictness', default=False,
        help='Strict route domain isolation'
    ),
    cfg.BoolOpt(
        'f5_common_external_networks', default=True,
        help='Treat external networks as common'
    ),
    cfg.StrOpt(
        'icontrol_vcmp_hostname',
        help='The hostname (name or IP address) to use for vCMP Host '
             'iControl access'
    ),
    cfg.StrOpt(
        'icontrol_hostname',
        default="10.190.5.7",
        help='The hostname (name or IP address) to use for iControl access'
    ),
    cfg.StrOpt(
        'icontrol_username', default='admin',
        help='The username to use for iControl access'
    ),
    cfg.StrOpt(
        'icontrol_password', default='admin', secret=True,
        help='The password to use for iControl access'
    ),
    cfg.IntOpt(
        'icontrol_connection_timeout', default=30,
        help='How many seconds to timeout a connection to BIG-IP'
    ),
    cfg.IntOpt(
        'icontrol_connection_retry_interval', default=10,
        help='How many seconds to wait between retry connection attempts'
    ),
    cfg.DictOpt(
        'common_network_ids', default={},
        help='network uuid to existing Common networks mapping'
    ),
    cfg.StrOpt(
        'icontrol_config_mode', default='objects',
        help='Whether to use iapp or objects for bigip configuration'
    ),
    cfg.IntOpt(
        'max_namespaces_per_tenant', default=1,
        help='How many routing tables the BIG-IP will allocate per tenant'
             ' in order to accommodate overlapping IP subnets'
    ),
    cfg.StrOpt(
        'cert_manager',
        default=None,
        help='Class name of the certificate mangager used for retrieving '
             'certificates and keys.'
    ),
    cfg.StrOpt(
        'auth_version',
        default=None,
        help='Keystone authentication version (v2 or v3) for Barbican client.'
    ),
    cfg.StrOpt(
        'os_project_id',
        default='service',
        help='OpenStack project ID.'
    ),
    cfg.StrOpt(
        'os_auth_url',
        default=None,
        help='OpenStack authentication URL.'
    ),
    cfg.StrOpt(
        'os_username',
        default=None,
        help='OpenStack user name for Keystone authentication.'
    ),
    cfg.StrOpt(
        'os_user_domain_name',
        default=None,
        help='OpenStack user domain name for Keystone authentication.'
    ),
    cfg.StrOpt(
        'os_project_name',
        default=None,
        help='OpenStack project name for Keystone authentication.'
    ),
    cfg.StrOpt(
        'os_project_domain_name',
        default=None,
        help='OpenStack domain name for Keystone authentication.'
    ),
    cfg.StrOpt(
        'os_password',
        default=None,
        help='OpenStack user password for Keystone authentication.'
    ),
    cfg.StrOpt(
        'f5_network_segment_physical_network', default=None,
        help='Name of physical network to use for discovery of segment ID'
    ),
    cfg.IntOpt(
        'f5_network_segment_polling_interval', default=10,
        help='Seconds between periodic scans for disconnected virtual servers'
    ),
    cfg.IntOpt(
        'f5_network_segment_gross_timeout', default=300,
        help='Seconds to wait for a virtual server to become connected'
    ),
    cfg.StrOpt(
        'f5_parent_ssl_profile',
        default='clientssl',
        help='Parent profile used when creating client SSL profiles '
        'for listeners with TERMINATED_HTTPS protocols.'
    ),
    cfg.StrOpt(
        'os_tenant_name',
        default=None,
        help='OpenStack tenant name for Keystone authentication (v2 only).'
    ),
    cfg.BoolOpt(
        'trace_service_requests',
        default=False,
        help='Log service object.'
    )
]


def is_connected(method):
    # Decorator to check we are connected before provisioning.
    def wrapper(*args, **kwargs):
        instance = args[0]
        if instance.connected:
            try:
                return method(*args, **kwargs)
            except IOError as ioe:
                LOG.error('IO Error detected: %s' % method.__name__)
                instance.connect_bigips()  # what's this do?
                raise ioe
        else:
            LOG.error('Cannot execute %s. Not connected. Connecting.'
                      % method.__name__)
            instance.connect_bigips()
    return wrapper


class iControlDriver(LBaaSBaseDriver):
    '''gets rpc plugin from manager (which instantiates, via importutils'''

    def __init__(self, conf, registerOpts=True):
        # The registerOpts parameter allows a test to
        # turn off config option handling so that it can
        # set the options manually instead. """
        super(iControlDriver, self).__init__(conf)
        self.conf = conf
        if registerOpts:
            self.conf.register_opts(OPTS)
        self.initialized = False
        self.hostnames = None
        self.device_type = conf.f5_device_type
        self.plugin_rpc = None  # overrides base, same value
        self.__last_connect_attempt = None
        self.connected = False  # overrides base, same value
        self.driver_name = 'f5-lbaasv2-icontrol'

        # BIG-IP containers
        self.__bigips = {}
        self.__traffic_groups = []
        self.agent_configurations = {}  # overrides base, same value
        self.tenant_manager = None
        self.cluster_manager = None
        self.system_helper = None
        self.lbaas_builder = None
        self.service_adapter = None
        self.vlan_binding = None
        self.l3_binding = None
        self.cert_manager = None  # overrides register_OPTS
        self.stat_helper = stat_helper.StatHelper()
        self.network_helper = network_helper.NetworkHelper()

        self.vs_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.pool_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)

        if self.conf.trace_service_requests:
            path = '/var/log/neutron/service/'
            if not os.path.exists(path):
                os.makedirs(path)
            self.file_name = path + strftime("%H%M%S-%m%d%Y") + '.json'
            with open(self.file_name, 'w') as fp:
                fp.write('[{}] ')

        if self.conf.f5_global_routed_mode:
            LOG.info('WARNING - f5_global_routed_mode enabled.'
                     ' There will be no L2 or L3 orchestration'
                     ' or tenant isolation provisioned. All vips'
                     ' and pool members must be routable through'
                     ' pre-provisioned SelfIPs.')
            self.conf.use_namespaces = False
            self.conf.f5_snat_mode = True
            self.conf.f5_snat_addresses_per_subnet = 0
            self.agent_configurations['tunnel_types'] = []
            self.agent_configurations['bridge_mappings'] = {}
        else:
            self.agent_configurations['tunnel_types'] = \
                self.conf.advertised_tunnel_types
            for net_id in self.conf.common_network_ids:
                LOG.debug('network %s will be mapped to /Common/%s'
                          % (net_id, self.conf.common_network_ids[net_id]))

            self.agent_configurations['common_networks'] = \
                self.conf.common_network_ids
            LOG.debug('Setting static ARP population to %s'
                      % self.conf.f5_populate_static_arp)
            self.agent_configurations['f5_common_external_networks'] = \
                self.conf.f5_common_external_networks
            f5const.FDB_POPULATE_STATIC_ARP = self.conf.f5_populate_static_arp

        self.agent_configurations['device_drivers'] = [self.driver_name]
        self._init_bigip_hostnames()
        self._init_bigip_managers()
        self.connect_bigips()

        # After we have a connection to the BIG-IPs, initialize vCMP
        if self.network_builder:
            self.network_builder.initialize_vcmp()

        self.agent_configurations['network_segment_physical_network'] = \
            self.conf.f5_network_segment_physical_network

        LOG.info('iControlDriver initialized to %d bigips with username:%s'
                 % (len(self.__bigips), self.conf.icontrol_username))
        LOG.info('iControlDriver dynamic agent configurations:%s'
                 % self.agent_configurations)
        self.initialized = True

    def connect_bigips(self):
        self._init_bigips()
        if self.conf.f5_global_routed_mode:
            local_ips = []
        else:
            try:
                local_ips = self.network_builder.initialize_tunneling()
            except Exception:
                LOG.error("Error creating BigIP VTEPs in connect_bigips")
                raise

        self._init_agent_config(local_ips)

    def post_init(self):
        # run any post initialized tasks, now that the agent
        # is fully connected
        if self.vlan_binding:
            LOG.debug(
                'Getting BIG-IP device interface for VLAN Binding')
            self.vlan_binding.register_bigip_interfaces()

        if self.l3_binding:
            LOG.debug('Getting BIG-IP MAC Address for L3 Binding')
            self.l3_binding.register_bigip_mac_addresses()

        if self.network_builder:
            self.network_builder.post_init()

    def _init_bigip_managers(self):

        if self.conf.vlan_binding_driver:
            try:
                self.vlan_binding = importutils.import_object(
                    self.conf.vlan_binding_driver, self.conf, self)
            except ImportError:
                LOG.error('Failed to import VLAN binding driver: %s'
                          % self.conf.vlan_binding_driver)

        if self.conf.l3_binding_driver:
            print('self.conf.l3_binding_driver')
            try:
                self.l3_binding = importutils.import_object(
                    self.conf.l3_binding_driver, self.conf, self)
            except ImportError:
                LOG.error('Failed to import L3 binding driver: %s'
                          % self.conf.l3_binding_driver)
        else:
            LOG.debug('No L3 binding driver configured.'
                      ' No L3 binding will be done.')

        if self.conf.cert_manager:
            try:
                self.cert_manager = importutils.import_object(
                    self.conf.cert_manager, self.conf)
            except ImportError as import_err:
                LOG.error('Failed to import CertManager: %s.' %
                          import_err.message)
                raise
            except Exception as err:
                LOG.error('Failed to initialize CertManager. %s' % err.message)
                # re-raise as ImportError to cause agent exit
                raise ImportError(err.message)

        self.service_adapter = ServiceModelAdapter(self.conf)
        self.tenant_manager = BigipTenantManager(self.conf, self)
        self.cluster_manager = ClusterManager()
        self.system_helper = SystemHelper()
        self.lbaas_builder = LBaaSBuilder(self.conf, self)

        if self.conf.f5_global_routed_mode:
            self.network_builder = None
        else:
            self.network_builder = NetworkServiceBuilder(
                self.conf.f5_global_routed_mode,
                self.conf,
                self,
                self.l3_binding)

    def _init_bigip_hostnames(self):
        # Validate and parse bigip credentials
        if not self.conf.icontrol_hostname:
            raise InvalidConfigurationOption(
                opt_name='icontrol_hostname',
                opt_value='valid hostname or IP address'
            )
        if not self.conf.icontrol_username:
            raise InvalidConfigurationOption(
                opt_name='icontrol_username',
                opt_value='valid username'
            )
        if not self.conf.icontrol_password:
            raise InvalidConfigurationOption(
                opt_name='icontrol_password',
                opt_value='valid password'
            )

        self.hostnames = self.conf.icontrol_hostname.split(',')
        self.hostnames = [item.strip() for item in self.hostnames]
        self.hostnames = sorted(self.hostnames)

    def _init_bigips(self):
        # Connect to all BIG-IPs
        if self.connected:
            return
        try:
            if not self.conf.debug:
                sudslog = std_logging.getLogger('suds.client')
                sudslog.setLevel(std_logging.FATAL)
                requests_log = std_logging.getLogger(
                    "requests.packages.urllib3")
                requests_log.setLevel(std_logging.ERROR)
                requests_log.propagate = False

            else:
                requests_log = std_logging.getLogger(
                    "requests.packages.urllib3")
                requests_log.setLevel(std_logging.DEBUG)
                requests_log.propagate = True

            self.__last_connect_attempt = datetime.datetime.now()

            first_bigip = self._open_bigip(self.hostnames[0])
            self._init_bigip(first_bigip, self.hostnames[0], None)
            self.__bigips[self.hostnames[0]] = first_bigip

            device_group_name = self._validate_ha(first_bigip)
            self._init_traffic_groups(first_bigip)

            # connect to the rest of the devices
            for hostname in self.hostnames[1:]:
                bigip = self._open_bigip(hostname)
                self._init_bigip(bigip, hostname, device_group_name)
                self.__bigips[hostname] = bigip

            self.connected = True

        except NeutronException as exc:
            LOG.error('Could not communicate with all ' +
                      'iControl devices: %s' % exc.msg)
            greenthread.sleep(5)  # this should probably go away
            raise
        except Exception as exc:
            LOG.error('Could not communicate with all ' +
                      'iControl devices: %s' % exc.message)
            greenthread.sleep(5)  # this should probably go away
            raise

    def _open_bigip(self, hostname):
        # Open bigip connection """
        LOG.info('Opening iControl connection to %s @ %s' %
                 (self.conf.icontrol_username, hostname))

        return ManagementRoot(hostname,
                              self.conf.icontrol_username,
                              self.conf.icontrol_password)

    def _init_bigip(self, bigip, hostname, check_group_name=None):
        # Prepare a bigip for usage

        major_version, minor_version = self._validate_bigip_version(
            bigip, hostname)

        device_group_name = None
        extramb = self.system_helper.get_provision_extramb(bigip)
        if int(extramb) < f5const.MIN_EXTRA_MB:
            raise f5ex.ProvisioningExtraMBValidateFailed(
                'Device %s BIG-IP not provisioned for '
                'management LARGE.' % hostname)

        if self.conf.f5_ha_type == 'pair' and \
                self.cluster_manager.get_sync_status(bigip) == 'Standalone':
            raise f5ex.BigIPClusterInvalidHA(
                'HA mode is pair and bigip %s in standalone mode'
                % hostname)

        if self.conf.f5_ha_type == 'scalen' and \
                self.cluster_manager.get_sync_status(bigip) == 'Standalone':
            raise f5ex.BigIPClusterInvalidHA(
                'HA mode is scalen and bigip %s in standalone mode'
                % hostname)

        if self.conf.f5_ha_type != 'standalone':
            device_group_name = self.cluster_manager.get_device_group(bigip)
            if not device_group_name:
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is %s and no sync failover '
                    'device group found for device %s.'
                    % (self.conf.f5_ha_type, hostname))
            if check_group_name and device_group_name != check_group_name:
                raise f5ex.BigIPClusterInvalidHA(
                    'Invalid HA. Device %s is in device group'
                    ' %s but should be in %s.'
                    % (hostname, device_group_name, check_group_name))
            bigip.device_group_name = device_group_name

        if self.network_builder:
            for network in self.conf.common_network_ids.values():
                if not self.network_builder.vlan_exists(bigip,
                                                        network,
                                                        folder='Common'):
                    raise f5ex.MissingNetwork(
                        'Common network %s on %s does not exist'
                        % (network, bigip.hostname))

        bigip.device_name = self.cluster_manager.get_device_name(bigip)
        bigip.mac_addresses = self.system_helper.get_mac_addresses(bigip)
        LOG.debug("Initialized BIG-IP %s with MAC addresses %s" %
                  (bigip.device_name, ', '.join(bigip.mac_addresses)))
        bigip.device_interfaces = \
            self.system_helper.get_interface_macaddresses_dict(bigip)
        bigip.assured_networks = {}
        bigip.assured_tenant_snat_subnets = {}
        bigip.assured_gateway_subnets = []

        if self.conf.f5_ha_type != 'standalone':
            self.cluster_manager.disable_auto_sync(device_group_name, bigip)

        # Turn off tunnel syncing... our VTEPs are local SelfIPs
        if self.system_helper.get_tunnel_sync(bigip) == 'enable':
            self.system_helper.set_tunnel_sync(bigip, enabled=False)

        LOG.debug('Connected to iControl %s @ %s ver %s.%s'
                  % (self.conf.icontrol_username, hostname,
                     major_version, minor_version))
        return bigip

    def _validate_ha(self, first_bigip):
        # if there was only one address supplied and
        # this is not a standalone device, get the
        # devices trusted by this device. """
        device_group_name = None
        if self.conf.f5_ha_type == 'standalone':
            if len(self.hostnames) != 1:
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is standalone and %d hosts found.'
                    % len(self.hostnames))
        elif self.conf.f5_ha_type == 'pair':
            device_group_name = self.cluster_manager.\
                get_device_group(first_bigip)
            if len(self.hostnames) != 2:
                mgmt_addrs = []
                devices = self.cluster_manager.devices(first_bigip,
                                                       device_group_name)
                for device in devices:
                    mgmt_addrs.append(
                        self.cluster_manager.get_mgmt_addr_by_device(device))
                self.hostnames = mgmt_addrs
            if len(self.hostnames) != 2:
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is pair and %d hosts found.'
                    % len(self.hostnames))
        elif self.conf.f5_ha_type == 'scalen':
            device_group_name = self.cluster_manager.\
                get_device_group(first_bigip)
            if len(self.hostnames) < 2:
                mgmt_addrs = []
                devices = self.cluster_manager.devices(first_bigip,
                                                       device_group_name)
                for device in devices:
                    mgmt_addrs.append(
                        self.cluster_manager.get_mgmt_addr_by_device(
                            first_bigip, device))
                self.hostnames = mgmt_addrs
        return device_group_name

    def _init_agent_config(self, local_ips):
        # Init agent config
        icontrol_endpoints = {}
        for host in self.__bigips:
            hostbigip = self.__bigips[host]
            ic_host = {}
            ic_host['version'] = self.system_helper.get_version(hostbigip)
            ic_host['device_name'] = hostbigip.device_name
            ic_host['platform'] = self.system_helper.get_platform(hostbigip)
            ic_host['serial_number'] = self.system_helper.get_serial_number(
                hostbigip)
            icontrol_endpoints[host] = ic_host

        self.agent_configurations['tunneling_ips'] = local_ips
        self.agent_configurations['icontrol_endpoints'] = icontrol_endpoints

        if self.network_builder:
            self.agent_configurations['bridge_mappings'] = \
                self.network_builder.interface_mapping

    def generate_capacity_score(self, capacity_policy=None):
        """Generate the capacity score of connected devices """
        if capacity_policy:
            highest_metric = 0.0
            highest_metric_name = None
            my_methods = dir(self)
            bigips = self.get_all_bigips()
            for metric in capacity_policy:
                func_name = 'get_' + metric
                if func_name in my_methods:
                    max_capacity = int(capacity_policy[metric])
                    metric_func = getattr(self, func_name)
                    metric_value = 0
                    for bigip in bigips:
                        global_stats = \
                            self.stat_helper.get_global_statistics(bigip)
                        value = int(
                            metric_func(bigip=bigip,
                                        global_statistics=global_stats)
                        )
                        LOG.debug('calling capacity %s on %s returned: %s'
                                  % (func_name, bigip.hostname, value))
                        if value > metric_value:
                            metric_value = value
                    metric_capacity = float(metric_value) / float(max_capacity)
                    if metric_capacity > highest_metric:
                        highest_metric = metric_capacity
                        highest_metric_name = metric
                else:
                    LOG.warn('capacity policy has method '
                             '%s which is not implemented in this driver'
                             % metric)
            LOG.debug('capacity score: %s based on %s'
                      % (highest_metric, highest_metric_name))
            return highest_metric
        return 0

    def set_context(self, context):
        # Context to keep for database access
        if self.network_builder:
            self.network_builder.set_context(context)

    def set_plugin_rpc(self, plugin_rpc):
        # Provide Plugin RPC access
        self.plugin_rpc = plugin_rpc

    def set_tunnel_rpc(self, tunnel_rpc):
        # Provide FDB Connector with ML2 RPC access
        if self.network_builder:
            self.network_builder.set_tunnel_rpc(tunnel_rpc)

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access
        if self.network_builder:
            self.network_builder.set_l2pop_rpc(l2pop_rpc)

    def service_exists(self, service):
        return self._service_exists(service)

    def flush_cache(self):
        # Remove cached objects so they can be created if necessary
        for bigip in self.get_all_bigips():
            bigip.assured_networks = {}
            bigip.assured_tenant_snat_subnets = {}
            bigip.assured_gateway_subnets = []

    @serialized('create_loadbalancer')
    @is_connected
    def create_loadbalancer(self, loadbalancer, service):
        """Create virtual server"""
        return self._common_service_handler(service)

    @serialized('update_loadbalancer')
    @is_connected
    def update_loadbalancer(self, old_loadbalancer, loadbalancer, service):
        """Update virtual server"""
        # anti-pattern three args unused.
        return self._common_service_handler(service)

    @serialized('delete_loadbalancer')
    @is_connected
    def delete_loadbalancer(self, loadbalancer, service):
        """Delete loadbalancer"""
        LOG.debug("Deleting loadbalancer")
        return self._common_service_handler(
            service,
            delete_partition=True,
            delete_event=True)

    @serialized('create_listener')
    @is_connected
    def create_listener(self, listener, service):
        """Create virtual server"""
        LOG.debug("Creating listener")
        return self._common_service_handler(service)

    @serialized('update_listener')
    @is_connected
    def update_listener(self, old_listener, listener, service):
        """Update virtual server"""
        LOG.debug("Updating listener")
        service['old_listener'] = old_listener
        return self._common_service_handler(service)

    @serialized('delete_listener')
    @is_connected
    def delete_listener(self, listener, service):
        """Delete virtual server"""
        LOG.debug("Deleting listener")
        return self._common_service_handler(service)

    @serialized('create_pool')
    @is_connected
    def create_pool(self, pool, service):
        """Create lb pool"""
        LOG.debug("Creating pool")
        return self._common_service_handler(service)

    @serialized('update_pool')
    @is_connected
    def update_pool(self, old_pool, pool, service):
        """Update lb pool"""
        LOG.debug("Updating pool")
        return self._common_service_handler(service)

    @serialized('delete_pool')
    @is_connected
    def delete_pool(self, pool, service):
        """Delete lb pool"""
        LOG.debug("Deleting pool")
        return self._common_service_handler(service)

    @serialized('create_member')
    @is_connected
    def create_member(self, member, service):
        """Create pool member"""
        LOG.debug("Creating member")
        return self._common_service_handler(service)

    @serialized('update_member')
    @is_connected
    def update_member(self, old_member, member, service):
        """Update pool member"""
        LOG.debug("Updating member")
        return self._common_service_handler(service)

    @serialized('delete_member')
    @is_connected
    def delete_member(self, member, service):
        """Delete pool member"""
        LOG.debug("Deleting member")
        return self._common_service_handler(service, delete_event=True)

    @serialized('create_health_monitor')
    @is_connected
    def create_health_monitor(self, health_monitor, service):
        """Create pool health monitor"""
        LOG.debug("Creating health monitor")
        return self._common_service_handler(service)

    @serialized('update_health_monitor')
    @is_connected
    def update_health_monitor(self, old_health_monitor,
                              health_monitor, service):
        """Update pool health monitor"""
        LOG.debug("Updating health monitor")
        return self._common_service_handler(service)

    @serialized('delete_health_monitor')
    @is_connected
    def delete_health_monitor(self, health_monitor, service):
        """Delete pool health monitor"""
        LOG.debug("Deleting health monitor")
        return self._common_service_handler(service)

    @is_connected
    def get_stats(self, service):
        lb_stats = {}
        stats = ['clientside.bitsIn',
                 'clientside.bitsOut',
                 'clientside.curConns',
                 'clientside.totConns']
        loadbalancer = service['loadbalancer']

        try:
            # sum virtual server stats for all BIG-IPs
            vs_stats = self.lbaas_builder.get_listener_stats(service, stats)

            # convert to bytes
            lb_stats[lb_const.STATS_IN_BYTES] = \
                vs_stats['clientside.bitsIn']/8
            lb_stats[lb_const.STATS_OUT_BYTES] = \
                vs_stats['clientside.bitsOut']/8
            lb_stats[lb_const.STATS_ACTIVE_CONNECTIONS] = \
                vs_stats['clientside.curConns']
            lb_stats[lb_const.STATS_TOTAL_CONNECTIONS] = \
                vs_stats['clientside.totConns']

            # update Neutron
            self.plugin_rpc.update_loadbalancer_stats(
                loadbalancer['id'], lb_stats)
        except Exception as e:
            LOG.error("Error getting loadbalancer stats: %s", e.message)

        finally:
            return lb_stats

    @serialized('remove_orphans')
    def remove_orphans(self, all_loadbalancers):
        """Remove out-of-date configuration on big-ips """
        existing_tenants = []
        existing_lbs = []
        for loadbalancer in all_loadbalancers:
            existing_tenants.append(loadbalancer['tenant_id'])
            existing_lbs.append(loadbalancer['lb_id'])

        for bigip in self.get_all_bigips():
            bigip.pool.purge_orphaned_pools(existing_lbs)
        for bigip in self.get_all_bigips():
            bigip.system.purge_orphaned_folders_contents(existing_tenants)

        for bigip in self.get_all_bigips():
            bigip.system.purge_orphaned_folders(existing_tenants)

    def fdb_add(self, fdb):
        # Add (L2toL3) forwarding database entries
        self.remove_ips_from_fdb_update(fdb)
        for bigip in self.get_all_bigips():
            self.network_builder.add_bigip_fdb(bigip, fdb)

    def fdb_remove(self, fdb):
        # Remove (L2toL3) forwarding database entries
        self.remove_ips_from_fdb_update(fdb)
        for bigip in self.get_all_bigips():
            self.network_builder.remove_bigip_fdb(bigip, fdb)

    def fdb_update(self, fdb):
        # Update (L2toL3) forwarding database entries
        self.remove_ips_from_fdb_update(fdb)
        for bigip in self.get_all_bigips():
            self.network_builder.update_bigip_fdb(bigip, fdb)

    # remove ips from fdb update so we do not try to
    # add static arps for them because we do not have
    # enough information to determine the route domain
    def remove_ips_from_fdb_update(self, fdb):
        for network_id in fdb:
            network = fdb[network_id]
            mac_ips_by_vtep = network['ports']
            for vtep in mac_ips_by_vtep:
                mac_ips = mac_ips_by_vtep[vtep]
                for mac_ip in mac_ips:
                    mac_ip[1] = None

    def tunnel_update(self, **kwargs):
        # Tunnel Update from Neutron Core RPC
        pass

    def tunnel_sync(self):
        # Only sync when supported types are present
        if not [i for i in self.agent_configurations['tunnel_types']
                if i in ['gre', 'vxlan']]:
            return False

        tunnel_ips = []
        for bigip in self.get_all_bigips():
            if bigip.local_ip:
                tunnel_ips.append(bigip.local_ip)

        self.network_builder.tunnel_sync(tunnel_ips)

        # Tunnel sync sent.
        return False

    @serialized('sync')
    @is_connected
    def sync(self, service):
        """Sync service defintion to device"""
        # plugin_rpc may not be set when unit testing
        if self.plugin_rpc:
            # Get the latest service. It may have changed.
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                service['loadbalancer']['id']
            )
        if service['loadbalancer']:
            return self._common_service_handler(service)
        else:
            LOG.debug("Attempted sync of deleted pool")

    @serialized('backup_configuration')
    @is_connected
    def backup_configuration(self):
        # Save Configuration on Devices
        for bigip in self.get_all_bigips():
            LOG.debug('_backup_configuration: saving device %s.'
                      % bigip.hostname)
            self.cluster_manager.save_config(bigip)

    def _get_monitor_endpoint(self, bigip, service):
        monitor_type = self.service_adapter.get_monitor_type(service)
        if not monitor_type:
            monitor_type = ""

        if monitor_type == "HTTPS":
            hm = bigip.tm.ltm.monitor.https_s.https
        elif monitor_type == "TCP":
            hm = bigip.tm.ltm.monitor.tcps.tcp
        elif monitor_type == "PING":
            hm = bigip.tm.ltm.monitor.gateway_icmps.gateway_icmp
        else:
            hm = bigip.tm.ltm.monitor.https.http

        return hm

    def service_rename_required(self, service):
        rename_required = False

        # Returns whether the bigip has a pool for the service
        if not service['loadbalancer']:
            return False

        bigips = self.get_config_bigips()
        loadbalancer = service['loadbalancer']

        # Does the correctly named virtual address exist?
        for bigip in bigips:
            virtual_address = VirtualAddress(self.service_adapter,
                                             loadbalancer)
            if not virtual_address.exists(bigip):
                rename_required = True
                break

        return rename_required

    def service_object_teardown(self, service):

        # Returns whether the bigip has a pool for the service
        if not service['loadbalancer']:
            return False

        bigips = self.get_config_bigips()
        loadbalancer = service['loadbalancer']
        folder_name = self.service_adapter.get_folder_name(
            loadbalancer['tenant_id']
        )

        # Change to bigips
        for bigip in bigips:

            # Delete all virtuals
            v = bigip.tm.ltm.virtuals.virtual
            for listener in service['listeners']:
                l_name = listener.get("name", "")
                if not l_name:
                    svc = {"loadbalancer": loadbalancer,
                           "listener": listener}
                    vip = self.service_adapter.get_virtual(svc)
                    l_name = vip['name']
                if v.exists(name=l_name, partition=folder_name):
                    # Found a virtual that is named by the OS object,
                    # delete it.
                    l_obj = v.load(name=l_name, partition=folder_name)
                    LOG.warn("Deleting listener: /%s/%s" %
                             (folder_name, l_name))
                    l_obj.delete(name=l_name, partition=folder_name)

            # Delete all pools
            p = bigip.tm.ltm.pools.pool
            for os_pool in service['pools']:
                p_name = os_pool.get('name', "")
                if not p_name:
                    svc = {"loadbalancer": loadbalancer,
                           "pool": os_pool}
                    pool = self.service_adapter.get_pool(svc)
                    p_name = pool['name']

                if p.exists(name=p_name, partition=folder_name):
                    p_obj = p.load(name=p_name, partition=folder_name)
                    LOG.warn("Deleting pool: /%s/%s" % (folder_name, p_name))
                    p_obj.delete(name=p_name, partition=folder_name)

            # Delete all healthmonitors
            for healthmonitor in service['healthmonitors']:
                svc = {'loadbalancer': loadbalancer,
                       'healthmonitor': healthmonitor}
                monitor_ep = self._get_monitor_endpoint(bigip, svc)

                m_name = healthmonitor.get('name', "")
                if not m_name:
                    hm = self.service_adapter.get_healthmonitor(svc)
                    m_name = hm['name']

                if monitor_ep.exists(name=m_name, partition=folder_name):
                    m_obj = monitor_ep.load(name=m_name, partition=folder_name)
                    LOG.warn("Deleting monitor: /%s/%s" % (
                        folder_name, m_name))
                    m_obj.delete()

    def _service_exists(self, service):
        # Returns whether the bigip has a pool for the service
        if not service['loadbalancer']:
            return False
        loadbalancer = service['loadbalancer']

        folder_name = self.service_adapter.get_folder_name(
            loadbalancer['tenant_id']
        )

        # Foreach bigip in the cluster:
        for bigip in self.get_config_bigips():
            # Does the tenant folder exist?
            if not self.system_helper.folder_exists(bigip, folder_name):
                LOG.error("Folder %s does not exists on bigip: %s" %
                          (folder_name, bigip.hostname))
                return False

            # Get the virtual address
            virtual_address = VirtualAddress(self.service_adapter,
                                             loadbalancer)
            if not virtual_address.exists(bigip):
                LOG.error("Virtual address %s(%s) does not "
                          "exists on bigip: %s" % (virtual_address.name,
                                                   virtual_address.address,
                                                   bigip.hostname))
                return False

            # Ensure that each virtual service exists.
            for listener in service['listeners']:

                svc = {"loadbalancer": loadbalancer,
                       "listener": listener}
                virtual_server = self.service_adapter.get_virtual_name(svc)
                if not self.vs_manager.exists(bigip,
                                              name=virtual_server['name'],
                                              partition=folder_name):
                    LOG.error("Virtual /%s/%s not found on bigip: %s" %
                              (virtual_server['name'], folder_name,
                               bigip.hostname))
                    return False

            # Ensure that each virtual service exists.
            for pool in service['pools']:
                svc = {"loadbalancer": loadbalancer,
                       "pool": pool}
                bigip_pool = self.service_adapter.get_pool(svc)
                if not self.pool_manager.exists(
                        bigip,
                        name=bigip_pool['name'],
                        partition=folder_name):
                    LOG.error("Pool /%s/%s not found on bigip: %s" %
                              (bigip_pool['name'], folder_name,
                               bigip.hostname))
                    return False

            for healthmonitor in service['healthmonitors']:
                svc = {"loadbalancer": loadbalancer,
                       "healthmonitor": healthmonitor}
                monitor = self.service_adapter.get_healthmonitor(svc)
                monitor_ep = self._get_monitor_endpoint(bigip, svc)
                if not monitor_ep.exists(name=monitor['name'],
                                         partition=folder_name):
                    LOG.error("Monitor /%s/%s not found on bigip: %s" %
                              (monitor['name'], folder_name, bigip.hostname))
                    return False

        return True

    def get_loadbalancers_in_tenant(self, tenant_id):
        loadbalancers = self.plugin_rpc.get_all_loadbalancers()

        return [lb['lb_id'] for lb in loadbalancers
                if lb['tenant_id'] == tenant_id]

    def _common_service_handler(self, service,
                                delete_partition=False,
                                delete_event=False):

        # Assure that the service is configured on bigip(s)
        start_time = time()

        lb_pending = True
        do_service_update = True

        if self.conf.trace_service_requests:
            self.trace_service_requests(service)

        loadbalancer = service.get("loadbalancer", None)
        if not loadbalancer:
            LOG.error("_common_service_handler: Service loadbalancer is None")
            return lb_pending

        lb_provisioning_status = loadbalancer.get("provisioning_status",
                                                  plugin_const.ERROR)
        try:
            try:
                self.tenant_manager.assure_tenant_created(service)
            except Exception as e:
                LOG.error("Tenant folder creation exception: %s",
                          e.message)
                if lb_provisioning_status != plugin_const.PENDING_DELETE:
                    loadbalancer['provisioning_status'] = \
                        plugin_const.ERROR
                raise e

            LOG.debug("    _assure_tenant_created took %.5f secs" %
                      (time() - start_time))

            traffic_group = self.service_to_traffic_group(service)
            loadbalancer['traffic_group'] = traffic_group

            if self.network_builder:
                start_time = time()
                try:
                    self.network_builder.prep_service_networking(
                        service, traffic_group)
                except f5ex.NetworkNotReady as error:
                    LOG.debug("Network creation deferred until network "
                              "definition is completed: %s",
                              error.message)
                    if not delete_event:
                        do_service_update = False
                        raise error
                except Exception as error:
                    LOG.error("Prep-network exception: icontrol_driver: %s",
                              error.message)
                    if lb_provisioning_status != plugin_const.PENDING_DELETE:
                        loadbalancer['provisioning_status'] = \
                            plugin_const.ERROR
                    if not delete_event:
                        raise error
                finally:
                    if time() - start_time > .001:
                        LOG.debug("    _prep_service_networking "
                                  "took %.5f secs" % (time() - start_time))

            all_subnet_hints = {}
            for bigip in self.get_config_bigips():
                # check_for_delete_subnets:
                #     keep track of which subnets we should check to delete
                #     for a deleted vip or member
                # do_not_delete_subnets:
                #     If we add an IP to a subnet we must not delete the subnet
                all_subnet_hints[bigip.device_name] = \
                    {'check_for_delete_subnets': {},
                     'do_not_delete_subnets': []}

            LOG.debug("XXXXXXXXX: Pre assure service")
            # pdb.set_trace()
            self.lbaas_builder.assure_service(service,
                                              traffic_group,
                                              all_subnet_hints)
            LOG.debug("XXXXXXXXX: Post assure service")

            if self.network_builder:
                start_time = time()
                try:
                    self.network_builder.post_service_networking(
                        service, all_subnet_hints)
                except Exception as error:
                    LOG.error("Post-network exception: icontrol_driver: %s",
                              error.message)

                    if lb_provisioning_status != plugin_const.PENDING_DELETE:
                        loadbalancer['provisioning_status'] = \
                            plugin_const.ERROR
                        raise error

                if time() - start_time > .001:
                    LOG.debug("    _post_service_networking "
                              "took %.5f secs" % (time() - start_time))

        except f5ex.NetworkNotReady as error:
            pass
        except Exception as err:
            LOG.exception(err)
        finally:
            # only delete partition if loadbalancer is being deleted
            if lb_provisioning_status == plugin_const.PENDING_DELETE:
                self.tenant_manager.assure_tenant_cleanup(service,
                                                          all_subnet_hints)

            if do_service_update:
                self.update_service_status(service)

            lb_provisioning_status = loadbalancer.get("provisioning_status",
                                                      plugin_const.ERROR)
            lb_pending = \
                (lb_provisioning_status == plugin_const.PENDING_CREATE or
                 lb_provisioning_status == plugin_const.PENDING_UPDATE)

        return lb_pending

    def update_service_status(self, service, timed_out=False):
        """Update status of objects in OpenStack """
        if not self.plugin_rpc:
            LOG.error("Cannot update status in Neutron without "
                      "RPC handler.")
            return

        if 'members' in service:
            # Call update_members_status
            self._update_member_status(service['members'], timed_out)
        if 'healthmonitors' in service:
            # Call update_monitor_status
            self._update_health_monitor_status(
                service['healthmonitors']
            )
        if 'pools' in service:
            # Call update_pool_status
            self._update_pool_status(
                service['pools']
            )
        if 'listeners' in service:
            # Call update_listener_status
            self._update_listener_status(service)

        self._update_loadbalancer_status(service, timed_out)

    def _update_member_status(self, members, timed_out):
        """Update member status in OpenStack """
        for member in members:
            if 'provisioning_status' in member:
                provisioning_status = member['provisioning_status']

                if (provisioning_status == plugin_const.PENDING_CREATE or
                        provisioning_status == plugin_const.PENDING_UPDATE):

                    if timed_out:
                        member['provisioning_status'] = plugin_const.ERROR
                        operating_status = lb_const.OFFLINE
                    else:
                        member['provisioning_status'] = plugin_const.ACTIVE
                        operating_status = lb_const.ONLINE

                    self.plugin_rpc.update_member_status(
                        member['id'],
                        member['provisioning_status'],
                        operating_status
                    )
                elif provisioning_status == plugin_const.PENDING_DELETE:
                    self.plugin_rpc.member_destroyed(
                        member['id'])
                elif provisioning_status == plugin_const.ERROR:
                    self.plugin_rpc.update_member_status(
                        member['id'],
                        plugin_const.ERROR,
                        lb_const.OFFLINE)

    def _update_health_monitor_status(self, health_monitors):
        """Update pool monitor status in OpenStack """
        for health_monitor in health_monitors:
            if 'provisioning_status' in health_monitor:
                provisioning_status = health_monitor['provisioning_status']
                if (provisioning_status == plugin_const.PENDING_CREATE or
                        provisioning_status == plugin_const.PENDING_UPDATE):
                        self.plugin_rpc.update_health_monitor_status(
                            health_monitor['id'],
                            plugin_const.ACTIVE,
                            lb_const.ONLINE
                        )
                        health_monitor['provisioning_status'] = \
                            plugin_const.ACTIVE
                elif provisioning_status == plugin_const.PENDING_DELETE:
                    self.plugin_rpc.health_monitor_destroyed(
                        health_monitor['id'])
                elif provisioning_status == plugin_const.ERROR:
                    self.plugin_rpc.update_health_monitor_status(
                        health_monitor['id'])

    @log_helpers.log_method_call
    def _update_pool_status(self, pools):
        """Update pool status in OpenStack """
        for pool in pools:
            if 'provisioning_status' in pool:
                provisioning_status = pool['provisioning_status']
                if (provisioning_status == plugin_const.PENDING_CREATE or
                        provisioning_status == plugin_const.PENDING_UPDATE):
                        self.plugin_rpc.update_pool_status(
                            pool['id'],
                            plugin_const.ACTIVE,
                            lb_const.ONLINE
                        )
                        pool['provisioning_status'] = plugin_const.ACTIVE
                elif provisioning_status == plugin_const.PENDING_DELETE:
                    self.plugin_rpc.pool_destroyed(
                        pool['id'])
                elif provisioning_status == plugin_const.ERROR:
                    self.plugin_rpc.update_pool_status(pool['id'])

    @log_helpers.log_method_call
    def _update_listener_status(self, service):
        """Update listener status in OpenStack """
        listeners = service['listeners']
        for listener in listeners:
            if 'provisioning_status' in listener:
                provisioning_status = listener['provisioning_status']
                if (provisioning_status == plugin_const.PENDING_CREATE or
                        provisioning_status == plugin_const.PENDING_UPDATE):
                        self.plugin_rpc.update_listener_status(
                            listener['id'],
                            plugin_const.ACTIVE,
                            listener['operating_status']
                        )
                        listener['provisioning_status'] = \
                            plugin_const.ACTIVE
                elif provisioning_status == plugin_const.PENDING_DELETE:
                    self.plugin_rpc.listener_destroyed(
                        listener['id'])
                elif provisioning_status == plugin_const.ERROR:
                    self.plugin_rpc.update_listener_status(
                        listener['id'],
                        provisioning_status,
                        lb_const.OFFLINE)

    @log_helpers.log_method_call
    def _update_loadbalancer_status(self, service, timed_out=False):
        """Update loadbalancer status in OpenStack """
        loadbalancer = service.get('loadbalancer', {})
        provisioning_status = loadbalancer.get('provisioning_status',
                                               plugin_const.ERROR)

        if (provisioning_status == plugin_const.PENDING_CREATE or
                provisioning_status == plugin_const.PENDING_UPDATE):
            if timed_out:
                operating_status = (lb_const.OFFLINE)
                if provisioning_status == plugin_const.PENDING_CREATE:
                    loadbalancer['provisioning_status'] = \
                        plugin_const.ERROR
                else:
                    loadbalancer['provisioning_status'] = \
                        plugin_const.ACTIVE
            else:
                operating_status = (lb_const.ONLINE)
                loadbalancer['provisioning_status'] = \
                    plugin_const.ACTIVE

            self.plugin_rpc.update_loadbalancer_status(
                loadbalancer['id'],
                loadbalancer['provisioning_status'],
                operating_status)

        elif provisioning_status == plugin_const.PENDING_DELETE:
            self.plugin_rpc.loadbalancer_destroyed(
                loadbalancer['id'])
        elif provisioning_status == plugin_const.ERROR:
            self.plugin_rpc.update_loadbalancer_status(
                loadbalancer['id'],
                provisioning_status,
                lb_const.OFFLINE)
        elif provisioning_status == plugin_const.ACTIVE:
            LOG.debug('Loadbalancer provisioning status is active')
        else:
            LOG.error('Loadbalancer provisioning status is invalid')

    @is_connected
    def update_operating_status(self, service):
        if 'members' in service:
            if self.network_builder:
                # append route domain to member address
                self.network_builder._annotate_service_route_domains(service)

            # get currrent member status
            self.lbaas_builder.update_operating_status(service)

            # udpate Neutron
            for member in service['members']:
                if member['provisioning_status'] == plugin_const.ACTIVE:
                    operating_status = member.get('operating_status', None)
                    self.plugin_rpc.update_member_status(
                        member['id'],
                        provisioning_status=None,
                        operating_status=operating_status)

    def get_active_bigip(self):
        bigips = self.get_all_bigips()

        if len(bigips) == 1:
            return bigips[0]

        for bigip in bigips:
            if self.cluster_manager.is_device_active(bigip):
                return bigip

        # if can't determine active, default to first one
        return bigips[0]

    def service_to_traffic_group(self, service):
        # Hash service tenant id to index of traffic group
        # return which iControlDriver.__traffic_group that tenant is "in?"
        return self.tenant_to_traffic_group(
            service['loadbalancer']['tenant_id'])

    def tenant_to_traffic_group(self, tenant_id):
        # Hash tenant id to index of traffic group
        hexhash = hashlib.md5(tenant_id).hexdigest()
        tg_index = int(hexhash, 16) % len(self.__traffic_groups)
        return self.__traffic_groups[tg_index]

    def get_bigip(self):
        # Get one consistent big-ip
        # As implemented I think this always returns the "first" bigip
        # without any HTTP traffic? CONFIRMED: __bigips are mgmt_rts
        hostnames = sorted(self.__bigips)
        for i in range(len(hostnames)):  # C-style make Pythonic.
            try:
                bigip = self.__bigips[hostnames[i]]  # Calling devices?!
                return bigip
            except urllib2.URLError:
                pass
        raise urllib2.URLError('cannot communicate to any bigips')

    def get_bigip_hosts(self):
        # Get all big-ips hostnames under management
        return self.__bigips

    def get_all_bigips(self):
        # Get all big-ips under management
        return self.__bigips.values()

    def get_config_bigips(self):
        # Return a list of big-ips that need to be configured.
        return self.get_all_bigips()

    def get_inbound_throughput(self, bigip, global_statistics=None):
        return self.stat_helper.get_inbound_throughput(
            bigip, global_stats=global_statistics)

    def get_outbound_throughput(self, bigip, global_statistics=None):
        return self.stat_helper.get_outbound_throughput(
            bigip, global_stats=global_statistics)

    def get_throughput(self, bigip=None, global_statistics=None):
        return self.stat_helper.get_throughput(
            bigip, global_stats=global_statistics)

    def get_active_connections(self, bigip=None, global_statistics=None):
        return self.stat_helper.get_active_connection_count(
            bigip, global_stats=global_statistics)

    def get_ssltps(self, bigip=None, global_statistics=None):
        return self.stat_helper.get_active_SSL_TPS(
            bigip, global_stats=global_statistics)

    def get_node_count(self, bigip=None, global_statistics=None):
        return len(bigip.tm.ltm.nodes.get_collection())

    def get_clientssl_profile_count(self, bigip=None, global_statistics=None):
        return ssl_profile.SSLProfileHelper.get_client_ssl_profile_count(bigip)

    def get_tenant_count(self, bigip=None, global_statistics=None):
        return self.system_helper.get_tenant_folder_count(bigip)

    def get_tunnel_count(self, bigip=None, global_statistics=None):
        return self.network_helper.get_tunnel_count(bigip)

    def get_vlan_count(self, bigip=None, global_statistics=None):
        return self.network_helper.get_vlan_count(bigip)

    def get_route_domain_count(self, bigip=None, global_statistics=None):
        return self.network_helper.get_route_domain_count(bigip)

    def _init_traffic_groups(self, bigip):
        self.__traffic_groups = self.cluster_manager.get_traffic_groups(bigip)
        if 'traffic-group-local-only' in self.__traffic_groups:
            self.__traffic_groups.remove('traffic-group-local-only')
        self.__traffic_groups.sort()

    def _validate_bigip_version(self, bigip, hostname):
        # Ensure the BIG-IP has sufficient version
        major_version = self.system_helper.get_major_version(bigip)
        if major_version < f5const.MIN_TMOS_MAJOR_VERSION:
            raise f5ex.MajorVersionValidateFailed(
                'Device %s must be at least TMOS %s.%s'
                % (hostname, f5const.MIN_TMOS_MAJOR_VERSION,
                   f5const.MIN_TMOS_MINOR_VERSION))
        minor_version = self.system_helper.get_minor_version(bigip)
        if minor_version < f5const.MIN_TMOS_MINOR_VERSION:
            raise f5ex.MinorVersionValidateFailed(
                'Device %s must be at least TMOS %s.%s'
                % (hostname, f5const.MIN_TMOS_MAJOR_VERSION,
                   f5const.MIN_TMOS_MINOR_VERSION))
        return major_version, minor_version

    def trace_service_requests(self, service):
        with open(self.file_name, 'r+') as fp:
            fp.seek(-1, 2)
            fp.write(',')
            json.dump(service, fp, sort_keys=True, indent=2)
            fp.write(']')
