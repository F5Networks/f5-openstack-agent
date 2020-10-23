# coding=utf-8#
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

import datetime
import hashlib
import json
import logging as std_logging
import os
import urllib

from eventlet import greenthread
from time import strftime
from time import time

from requests import HTTPError

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import importutils

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import \
    ClusterManager
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as f5const
from f5_openstack_agent.lbaasv2.drivers.bigip.esd_filehandler import \
    EsdTagProcessor
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
        'advertised_tunnel_types', default=['vxlan'],
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
        'f5_common_networks', default=False,
        help='All networks defined under Common partition'
    ),
    cfg.BoolOpt(
        'f5_common_external_networks', default=True,
        help='Treat external networks as common'
    ),
    cfg.BoolOpt(
        'external_gateway_mode', default=False,
        help='All subnets have an external l3 route on gateway'
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
    cfg.StrOpt(
        'unlegacy_setting_placeholder', default=None,
        help='use this setting to separate legacy with hw/etc on agent side'
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
    ),
    cfg.BoolOpt(
        'report_esd_names_in_agent',
        default=False,
        help='whether or not to add valid esd names during report.'
    )
]


def is_operational(method):
    # Decorator to check we are operational before provisioning.
    def wrapper(*args, **kwargs):
        instance = args[0]
        if instance.operational:
            try:
                return method(*args, **kwargs)
            except IOError as ioe:
                LOG.error('IO Error detected: %s' % method.__name__)
                LOG.error(str(ioe))
                raise ioe
        else:
            LOG.error('Cannot execute %s. Not operational. Re-initializing.'
                      % method.__name__)
            instance._init_bigips()
    return wrapper


class iControlDriver(LBaaSBaseDriver):
    """Control service deployment."""

    positive_plugin_const_state = \
        tuple([f5const.F5_ACTIVE, f5const.F5_PENDING_CREATE,
               f5const.F5_PENDING_UPDATE])

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
        self.agent_report_state = None  # overrides base, same value
        self.operational = False  # overrides base, same value
        self.driver_name = 'f5-lbaasv2-icontrol'

        #
        # BIG-IP containers
        #

        # BIG-IPs which currectly active
        self.__bigips = {}
        self.__last_connect_attempt = None

        # HA and traffic group validation
        self.ha_validated = False
        self.tg_initialized = False
        # traffic groups discovered from BIG-IPs for service placement
        self.__traffic_groups = []

        # base configurations to report to Neutron agent state reports
        self.agent_configurations = {}  # overrides base, same value
        self.agent_configurations['device_drivers'] = [self.driver_name]
        self.agent_configurations['icontrol_endpoints'] = {}

        # to store the verified esd names
        self.esd_names = []

        # service component managers
        self.tenant_manager = None
        self.cluster_manager = None
        self.system_helper = None
        self.lbaas_builder = None
        self.service_adapter = None
        self.vlan_binding = None
        self.l3_binding = None
        self.cert_manager = None  # overrides register_OPTS

        # server helpers
        self.stat_helper = stat_helper.StatHelper()
        self.network_helper = network_helper.NetworkHelper()

        # f5-sdk helpers
        self.vs_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.pool_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)

        try:

            # debug logging of service requests recieved by driver
            if self.conf.trace_service_requests:
                path = '/var/log/neutron/service/'
                if not os.path.exists(path):
                    os.makedirs(path)
                self.file_name = path + strftime("%H%M%S-%m%d%Y") + '.json'
                with open(self.file_name, 'w') as fp:
                    fp.write('[{}] ')

            # driver mode settings - GRM vs L2 adjacent
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
                f5const.FDB_POPULATE_STATIC_ARP = \
                    self.conf.f5_populate_static_arp

            # parse the icontrol_hostname setting
            self._init_bigip_hostnames()
            # instantiate the managers
            self._init_bigip_managers()

            self.initialized = True
            LOG.debug('iControlDriver loaded successfully')
        except Exception as exc:
            LOG.error("exception in intializing driver %s" % str(exc))
            self._set_agent_status(False)

    def connect(self):
        # initialize communications wiht BIG-IP via iControl
        try:
            self._init_bigips()
        except Exception as exc:
            LOG.error("exception in intializing communications to BIG-IPs %s"
                      % str(exc))
            self._set_agent_status(False)

    def get_valid_esd_names(self):
        LOG.debug("verified esd names in get_valid_esd_names():")
        LOG.debug(self.esd_names)
        return self.esd_names

    def _init_bigip_managers(self):

        if self.conf.vlan_binding_driver:
            try:
                self.vlan_binding = importutils.import_object(
                    self.conf.vlan_binding_driver, self.conf, self)
            except ImportError:
                LOG.error('Failed to import VLAN binding driver: %s'
                          % self.conf.vlan_binding_driver)

        if self.conf.l3_binding_driver:
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
            raise f5ex.F5InvalidConfigurationOption(
                opt_name='icontrol_hostname',
                opt_value='valid hostname or IP address'
            )
        if not self.conf.icontrol_username:
            raise f5ex.F5InvalidConfigurationOption(
                opt_name='icontrol_username',
                opt_value='valid username'
            )
        if not self.conf.icontrol_password:
            raise f5ex.F5InvalidConfigurationOption(
                opt_name='icontrol_password',
                opt_value='valid password'
            )

        self.hostnames = self.conf.icontrol_hostname.split(',')
        self.hostnames = [item.strip() for item in self.hostnames]
        self.hostnames = sorted(self.hostnames)

        # initialize per host agent_configurations
        for hostname in self.hostnames:
            self.__bigips[hostname] = bigip = type('', (), {})()
            bigip.hostname = hostname
            bigip.status = 'creating'
            bigip.status_message = 'creating BIG-IP from iControl hostnames'
            bigip.device_interfaces = dict()
            self.agent_configurations[
                'icontrol_endpoints'][hostname] = {}
            self.agent_configurations[
                'icontrol_endpoints'][hostname]['failover_state'] = \
                'undiscovered'
            self.agent_configurations[
                'icontrol_endpoints'][hostname]['status'] = 'unknown'
            self.agent_configurations[
                'icontrol_endpoints'][hostname]['status_message'] = ''

    def _init_bigips(self):
        # Connect to all BIG-IPs
        if self.operational:
            LOG.debug('iControl driver reports connection is operational')
            return
        LOG.debug('initializing communications to BIG-IPs')
        try:
            # setup logging options
            if not self.conf.debug:
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

            for hostname in self.hostnames:
                # connect to each BIG-IP and set it status
                bigip = self._open_bigip(hostname)
                if bigip.status == 'connected':
                    # set the status down until we assure initialized
                    bigip.status = 'initializing'
                    bigip.status_message = 'initializing HA viability'
                    LOG.debug('initializing HA viability %s' % hostname)
                    device_group_name = None
                    if not self.ha_validated:
                        device_group_name = self._validate_ha(bigip)
                        LOG.debug('HA validated from %s with DSG %s' %
                                  (hostname, device_group_name))
                        self.ha_validated = True
                    if not self.tg_initialized:
                        self._init_traffic_groups(bigip)
                        LOG.debug('learned traffic groups from %s as %s' %
                                  (hostname, self.__traffic_groups))
                        self.tg_initialized = True
                    LOG.debug('initializing bigip %s' % hostname)
                    self._init_bigip(bigip, hostname, device_group_name)
                    LOG.debug('initializing agent configurations %s'
                              % hostname)
                    self._init_agent_config(bigip)
                    # Assure basic BIG-IP HA is operational
                    LOG.debug('validating HA state for %s' % hostname)
                    bigip.status = 'validating_HA'
                    bigip.status_message = 'validating the current HA state'
                    if self._validate_ha_operational(bigip):
                        LOG.debug('setting status to active for %s' % hostname)
                        bigip.status = 'active'
                        bigip.status_message = 'BIG-IP ready for provisioning'
                        self._post_init()
                    else:
                        LOG.debug('setting status to error for %s' % hostname)
                        bigip.status = 'error'
                        bigip.status_message = 'BIG-IP is not operational'
                        self._set_agent_status(False)
                else:
                    LOG.error('error opening BIG-IP %s - %s:%s'
                              % (hostname, bigip.status, bigip.status_message))
                    self._set_agent_status(False)
        except Exception as exc:
            LOG.error('Invalid agent configuration: %s' % exc.message)
            raise
        self._set_agent_status(force_resync=True)

    def _init_errored_bigips(self):
        try:
            errored_bigips = self.get_errored_bigips_hostnames()
            if errored_bigips:
                LOG.debug('attempting to recover %s BIG-IPs' %
                          len(errored_bigips))
                for hostname in errored_bigips:
                    # try to connect and set status
                    bigip = self._open_bigip(hostname)
                    if bigip.status == 'connected':
                        # set the status down until we assure initialized
                        bigip.status = 'initializing'
                        bigip.status_message = 'initializing HA viability'
                        LOG.debug('initializing HA viability %s' % hostname)
                        LOG.debug('proceeding to initialize %s' % hostname)
                        device_group_name = None
                        if not self.ha_validated:
                            device_group_name = self._validate_ha(bigip)
                            LOG.debug('HA validated from %s with DSG %s' %
                                      (hostname, device_group_name))
                            self.ha_validated = True
                        if not self.tg_initialized:
                            self._init_traffic_groups(bigip)
                            LOG.debug('known traffic groups initialized',
                                      ' from %s as %s' %
                                      (hostname, self.__traffic_groups))
                            self.tg_initialized = True
                        LOG.debug('initializing bigip %s' % hostname)
                        self._init_bigip(bigip, hostname, device_group_name)
                        LOG.debug('initializing agent configurations %s'
                                  % hostname)
                        self._init_agent_config(bigip)

                        # Assure basic BIG-IP HA is operational
                        LOG.debug('validating HA state for %s' % hostname)
                        bigip.status = 'validating_HA'
                        bigip.status_message = \
                            'validating the current HA state'
                        if self._validate_ha_operational(bigip):
                            LOG.debug('setting status to active for %s'
                                      % hostname)
                            bigip.status = 'active'
                            bigip.status_message = \
                                'BIG-IP ready for provisioning'
                            self._post_init()
                            self._set_agent_status(True)
                        else:
                            LOG.debug('setting status to error for %s'
                                      % hostname)
                            bigip.status = 'error'
                            bigip.status_message = 'BIG-IP is not operational'
                            self._set_agent_status(False)
            else:
                LOG.debug('there are no BIG-IPs with error status')
        except Exception as exc:
            LOG.error('Invalid agent configuration: %s' % exc.message)
            raise

    def _open_bigip(self, hostname):
        # Open bigip connection """
        try:
            bigip = self.__bigips[hostname]
            if bigip.status not in ['creating', 'error']:
                LOG.debug('BIG-IP %s status invalid %s to open a connection'
                          % (hostname, bigip.status))
                return bigip
            bigip.status = 'connecting'
            bigip.status_message = 'requesting iControl endpoint'
            LOG.info('opening iControl connection to %s @ %s' %
                     (self.conf.icontrol_username, hostname))
            bigip = ManagementRoot(hostname,
                                   self.conf.icontrol_username,
                                   self.conf.icontrol_password,
                                   timeout=f5const.DEVICE_CONNECTION_TIMEOUT,
                                   debug=self.conf.debug)
            bigip.status = 'connected'
            bigip.status_message = 'connected to BIG-IP'
            self.__bigips[hostname] = bigip
            return bigip
        except Exception as exc:
            LOG.error('could not communicate with ' +
                      'iControl device: %s' % hostname)
            # since no bigip object was created, create a dummy object
            # so we can store the status and status_message attributes
            errbigip = type('', (), {})()
            errbigip.hostname = hostname
            errbigip.status = 'error'
            errbigip.status_message = str(exc)[:80]
            self.__bigips[hostname] = errbigip
            return errbigip

    def _init_bigip(self, bigip, hostname, check_group_name=None):
        # Prepare a bigip for usage
        try:
            major_version, minor_version = self._validate_bigip_version(
                bigip, hostname)

            device_group_name = None
            extramb = self.system_helper.get_provision_extramb(bigip)
            if int(extramb) < f5const.MIN_EXTRA_MB:
                raise f5ex.ProvisioningExtraMBValidateFailed(
                    'Device %s BIG-IP not provisioned for '
                    'management LARGE.' % hostname)

            if self.conf.f5_ha_type == 'pair' and \
                    self.cluster_manager.get_sync_status(bigip) == \
                    'Standalone':
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is pair and bigip %s in standalone mode'
                    % hostname)

            if self.conf.f5_ha_type == 'scalen' and \
                    self.cluster_manager.get_sync_status(bigip) == \
                    'Standalone':
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is scalen and bigip %s in standalone mode'
                    % hostname)

            if self.conf.f5_ha_type != 'standalone':
                device_group_name = \
                    self.cluster_manager.get_device_group(bigip)
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
                self.cluster_manager.disable_auto_sync(
                    device_group_name, bigip)

            # validate VTEP SelfIPs
            if not self.conf.f5_global_routed_mode:
                self.network_builder.initialize_tunneling(bigip)

            # Turn off tunnel syncing between BIG-IP
            # as our VTEPs properly use only local SelfIPs
            if self.system_helper.get_tunnel_sync(bigip) == 'enable':
                self.system_helper.set_tunnel_sync(bigip, enabled=False)

            LOG.debug('connected to iControl %s @ %s ver %s.%s'
                      % (self.conf.icontrol_username, hostname,
                         major_version, minor_version))
        except Exception as exc:
            bigip.status = 'error'
            bigip.status_message = str(exc)[:80]
            raise
        return bigip

    def _post_init(self):
        # After we have a connection to the BIG-IPs, initialize vCMP
        # on all connected BIG-IPs
        if self.network_builder:
            self.network_builder.initialize_vcmp()

        self.agent_configurations['network_segment_physical_network'] = \
            self.conf.f5_network_segment_physical_network

        LOG.info('iControlDriver initialized to %d bigips with username:%s'
                 % (len(self.get_active_bigips()),
                    self.conf.icontrol_username))
        LOG.info('iControlDriver dynamic agent configurations:%s'
                 % self.agent_configurations)

        if self.vlan_binding:
            LOG.debug(
                'getting BIG-IP device interface for VLAN Binding')
            self.vlan_binding.register_bigip_interfaces()

        if self.l3_binding:
            LOG.debug('getting BIG-IP MAC Address for L3 Binding')
            self.l3_binding.register_bigip_mac_addresses()

        # endpoints = self.agent_configurations['icontrol_endpoints']
        # for ic_host in endpoints.keys():
        for hostbigip in self.get_all_bigips():

            # hostbigip = self.__bigips[ic_host]
            mac_addrs = [mac_addr for interface, mac_addr in
                         hostbigip.device_interfaces.items()
                         if interface != "mgmt"]
            ports = self.plugin_rpc.get_ports_for_mac_addresses(
                mac_addresses=mac_addrs)
            if ports:
                self.agent_configurations['nova_managed'] = True
            else:
                self.agent_configurations['nova_managed'] = False

        if self.network_builder:
            self.network_builder.post_init()

        # read enhanced services definitions
        esd_dir = os.path.join(self.get_config_dir(), 'esd')
        esd = EsdTagProcessor(esd_dir)
        try:
            esd.process_esd(self.get_all_bigips())
            self.lbaas_builder.init_esd(esd)
            self.service_adapter.init_esd(esd)

            LOG.debug('esd details here after process_esd(): ')
            LOG.debug(esd)
            self.esd_names = esd.esd_dict.keys() or []
            LOG.debug('##### self.esd_names obtainded here:')
            LOG.debug(self.esd_names)
        except f5ex.esdJSONFileInvalidException as err:
            LOG.error("unable to initialize ESD. Error: %s.", err.message)
        self._set_agent_status(False)

    def _validate_ha(self, bigip):
        # if there was only one address supplied and
        # this is not a standalone device, get the
        # devices trusted by this device. """
        device_group_name = None
        if self.conf.f5_ha_type == 'standalone':
            if len(self.hostnames) != 1:
                bigip.status = 'error'
                bigip.status_message = \
                    'HA mode is standalone and %d hosts found.'\
                    % len(self.hostnames)
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is standalone and %d hosts found.'
                    % len(self.hostnames))
            device_group_name = 'standalone'
        elif self.conf.f5_ha_type == 'pair':
            device_group_name = self.cluster_manager.\
                get_device_group(bigip)
            if len(self.hostnames) != 2:
                mgmt_addrs = []
                devices = self.cluster_manager.devices(bigip)
                for device in devices:
                    mgmt_addrs.append(
                        self.cluster_manager.get_mgmt_addr_by_device(
                            bigip, device))
                self.hostnames = mgmt_addrs
            if len(self.hostnames) != 2:
                bigip.status = 'error'
                bigip.status_message = 'HA mode is pair and %d hosts found.' \
                    % len(self.hostnames)
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is pair and %d hosts found.'
                    % len(self.hostnames))
        elif self.conf.f5_ha_type == 'scalen':
            device_group_name = self.cluster_manager.\
                get_device_group(bigip)
            if len(self.hostnames) < 2:
                mgmt_addrs = []
                devices = self.cluster_manager.devices(bigip)
                for device in devices:
                    mgmt_addrs.append(
                        self.cluster_manager.get_mgmt_addr_by_device(
                            bigip, device)
                    )
                self.hostnames = mgmt_addrs
            if len(self.hostnames) < 2:
                bigip.status = 'error'
                bigip.status_message = 'HA mode is scale and 1 hosts found.'
                raise f5ex.BigIPClusterInvalidHA(
                    'HA mode is pair and 1 hosts found.')
        return device_group_name

    def _validate_ha_operational(self, bigip):
        if self.conf.f5_ha_type == 'standalone':
            return True
        else:
            # how many active BIG-IPs are there?
            active_bigips = self.get_active_bigips()
            if active_bigips:
                sync_status = self.cluster_manager.get_sync_status(bigip)
                if sync_status in ['Disconnected', 'Sync Failure']:
                    if len(active_bigips) > 1:
                        # the device should not be in the disconnected state
                        return False
                if len(active_bigips) > 1:
                    # it should be in the same sync-failover group
                    # as the rest of the active bigips
                    device_group_name = \
                        self.cluster_manager.get_device_group(bigip)
                    for active_bigip in active_bigips:
                        adgn = self.cluster_manager.get_device_group(
                            active_bigip)
                        if not adgn == device_group_name:
                            return False
                return True
            else:
                return True

    def _init_agent_config(self, bigip):
        # Init agent config
        ic_host = {}
        ic_host['version'] = self.system_helper.get_version(bigip)
        ic_host['device_name'] = bigip.device_name
        ic_host['platform'] = self.system_helper.get_platform(bigip)
        ic_host['serial_number'] = self.system_helper.get_serial_number(bigip)
        ic_host['status'] = bigip.status
        ic_host['status_message'] = bigip.status_message
        ic_host['failover_state'] = self.get_failover_state(bigip)
        if hasattr(bigip, 'local_ip') and bigip.local_ip:
            ic_host['local_ip'] = bigip.local_ip
        else:
            ic_host['local_ip'] = 'VTEP disabled'
            self.agent_configurations['tunnel_types'] = list()
        self.agent_configurations['icontrol_endpoints'][bigip.hostname] = \
            ic_host
        if self.network_builder:
            self.agent_configurations['bridge_mappings'] = \
                self.network_builder.interface_mapping

    def _set_agent_status(self, force_resync=False):
        for hostname in self.__bigips:
            bigip = self.__bigips[hostname]
            self.agent_configurations[
                'icontrol_endpoints'][bigip.hostname][
                    'status'] = bigip.status
            self.agent_configurations[
                'icontrol_endpoints'][bigip.hostname][
                    'status_message'] = bigip.status_message

            if self.conf.report_esd_names_in_agent:
                LOG.debug('adding names to report:')
                self.agent_configurations['esd_name'] = \
                    self.get_valid_esd_names()
        # Policy - if any BIG-IP are active we're operational
        if self.get_active_bigips():
            self.operational = True
        else:
            self.operational = False
        if self.agent_report_state:
            self.agent_report_state(force_resync=force_resync)

    def get_failover_state(self, bigip):
        try:
            if hasattr(bigip, 'tm'):
                fs = bigip.tm.sys.dbs.db.load(name='failover.state')
                bigip.failover_state = fs.value
                return bigip.failover_state
            else:
                return 'error'
        except Exception as exc:
            LOG.exception('Error getting %s failover state' % bigip.hostname)
            bigip.status = 'error'
            bigip.status_message = str(exc)[:80]
            self._set_agent_status(False)
            return 'error'

    def get_agent_configurations(self):
        for hostname in self.__bigips:
            bigip = self.__bigips[hostname]
            if bigip.status == 'active':
                failover_state = self.get_failover_state(bigip)
                self.agent_configurations[
                    'icontrol_endpoints'][bigip.hostname][
                        'failover_state'] = failover_state
            else:
                self.agent_configurations[
                    'icontrol_endpoints'][bigip.hostname][
                        'failover_state'] = 'unknown'
            self.agent_configurations['icontrol_endpoints'][
                bigip.hostname]['status'] = bigip.status
            self.agent_configurations['icontrol_endpoints'][
                bigip.hostname]['status_message'] = bigip.status_message
            self.agent_configurations['operational'] = \
                self.operational
        LOG.debug('agent configurations are: %s' % self.agent_configurations)
        return dict(self.agent_configurations)

    def recover_errored_devices(self):
        # trigger a retry on errored BIG-IPs
        try:
            self._init_errored_bigips()
        except Exception as exc:
            LOG.error('Could not recover devices: %s' % exc.message)

    def backend_integrity(self):
        if self.operational:
            return True
        return False

    def generate_capacity_score(self, capacity_policy=None):
        """Generate the capacity score of connected devices."""
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
                        if bigip.status == 'active':
                            global_stats = \
                                self.stat_helper.get_global_statistics(bigip)
                            value = int(
                                metric_func(bigip=bigip,
                                            global_statistics=global_stats)
                            )
                            LOG.debug('calling capacity %s on %s returned: %s'
                                      % (func_name, bigip.hostname, value))
                        else:
                            value = 0
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

    def set_agent_report_state(self, report_state_callback):
        """Set Agent Report State."""
        self.agent_report_state = report_state_callback

    def service_exists(self, service):
        return self._service_exists(service)

    def flush_cache(self):
        # Remove cached objects so they can be created if necessary
        for bigip in self.get_all_bigips():
            bigip.assured_networks = {}
            bigip.assured_tenant_snat_subnets = {}
            bigip.assured_gateway_subnets = []

    @serialized('get_all_deployed_loadbalancers')
    @is_operational
    def get_all_deployed_loadbalancers(self, purge_orphaned_folders=False):
        LOG.debug('getting all deployed loadbalancers on BIG-IPs')
        deployed_lb_dict = {}
        for bigip in self.get_all_bigips():
            folders = self.system_helper.get_folders(bigip)
            for folder in folders:
                tenant_id = folder[len(self.service_adapter.prefix):]
                if str(folder).startswith(self.service_adapter.prefix):
                    resource = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.virtual_address)
                    deployed_lbs = resource.get_resources(bigip, folder)
                    if deployed_lbs:
                        for lb in deployed_lbs:
                            lb_id = lb.name[len(self.service_adapter.prefix):]
                            if lb_id in deployed_lb_dict:
                                deployed_lb_dict[lb_id][
                                    'hostnames'].append(bigip.hostname)
                            else:
                                deployed_lb_dict[lb_id] = {
                                    'id': lb_id,
                                    'tenant_id': tenant_id,
                                    'hostnames': [bigip.hostname]
                                }
                    else:
                        # delay to assure we are not in the tenant creation
                        # process before a virtual address is created.
                        greenthread.sleep(40)
                        deployed_lbs = resource.get_resources(bigip, folder)
                        if deployed_lbs:
                            for lb in deployed_lbs:
                                lb_id = lb.name[
                                    len(self.service_adapter.prefix):]
                                deployed_lb_dict[lb_id] = \
                                    {'id': lb_id, 'tenant_id': tenant_id}
                        else:
                            # Orphaned folder!
                            if purge_orphaned_folders:
                                try:
                                    self.system_helper.purge_folder_contents(
                                        bigip, folder)
                                    self.system_helper.purge_folder(
                                        bigip, folder)
                                    LOG.debug('orphaned folder %s on %s' %
                                              (folder, bigip.hostname))
                                except Exception as exc:
                                    LOG.error('error purging folder %s: %s' %
                                              (folder, str(exc)))
        return deployed_lb_dict

    @serialized('get_all_deployed_listeners')
    @is_operational
    def get_all_deployed_listeners(self, expand_subcollections=False):
        LOG.debug('getting all deployed listeners on BIG-IPs')
        deployed_virtual_dict = {}
        for bigip in self.get_all_bigips():
            folders = self.system_helper.get_folders(bigip)
            for folder in folders:
                tenant_id = folder[len(self.service_adapter.prefix):]
                if str(folder).startswith(self.service_adapter.prefix):
                    resource = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.virtual)
                    deployed_listeners = resource.get_resources(
                        bigip, folder, expand_subcollections)
                    if deployed_listeners:
                        for virtual in deployed_listeners:
                            virtual_id = \
                                virtual.name[len(self.service_adapter.prefix):]
                            l7_policy = ''
                            if hasattr(virtual, 'policiesReference') and \
                                    'items' in virtual.policiesReference:
                                l7_policy = \
                                    virtual.policiesReference['items'][0]
                                l7_policy = l7_policy['fullPath']
                            if virtual_id in deployed_virtual_dict:
                                deployed_virtual_dict[virtual_id][
                                    'hostnames'].append(bigip.hostname)
                            else:
                                deployed_virtual_dict[virtual_id] = {
                                    'id': virtual_id,
                                    'tenant_id': tenant_id,
                                    'hostnames': [bigip.hostname],
                                    'l7_policy': l7_policy
                                }
        return deployed_virtual_dict

    @serialized('purge_orphaned_nodes')
    @is_operational
    @log_helpers.log_method_call
    def purge_orphaned_nodes(self, tenant_members):
        node_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.node)
        node_dict = dict()
        for bigip in self.get_all_bigips():
            for tenant_id, members in tenant_members.iteritems():
                partition = self.service_adapter.prefix + tenant_id
                nodes = node_helper.get_resources(bigip, partition=partition)
                for n in nodes:
                    node_dict[n.name] = n

                for member in members:
                    rd = self.network_builder.find_subnet_route_domain(
                        tenant_id, member.get('subnet_id', None))
                    node_name = "{}%{}".format(member['address'], rd)
                    node_dict.pop(node_name, None)

                for node_name, node in node_dict.iteritems():
                    try:
                        node_helper.delete(bigip, name=urllib.quote(node_name),
                                           partition=partition)
                    except HTTPError as error:
                        if error.response.status_code == 400:
                            LOG.error(error.response)

    @serialized('get_all_deployed_pools')
    @is_operational
    def get_all_deployed_pools(self):
        LOG.debug('getting all deployed pools on BIG-IPs')
        deployed_pool_dict = {}
        for bigip in self.get_all_bigips():
            folders = self.system_helper.get_folders(bigip)
            for folder in folders:
                tenant_id = folder[len(self.service_adapter.prefix):]
                if str(folder).startswith(self.service_adapter.prefix):
                    resource = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.pool)
                    deployed_pools = resource.get_resources(bigip, folder)
                    if deployed_pools:
                        for pool in deployed_pools:
                            pool_id = \
                                pool.name[len(self.service_adapter.prefix):]
                            monitor_id = ''
                            if hasattr(pool, 'monitor'):
                                monitor = pool.monitor.split('/')[2].strip()
                                monitor_id = \
                                    monitor[len(self.service_adapter.prefix):]
                                LOG.debug(
                                    'pool {} has monitor {}'.format(
                                        pool.name, monitor))
                            else:
                                LOG.debug(
                                    'pool {} has no healthmonitors'.format(
                                        pool.name))
                            if pool_id in deployed_pool_dict:
                                deployed_pool_dict[pool_id][
                                    'hostnames'].append(bigip.hostname)
                            else:
                                deployed_pool_dict[pool_id] = {
                                    'id': pool_id,
                                    'tenant_id': tenant_id,
                                    'hostnames': [bigip.hostname],
                                    'monitors': monitor_id
                                }
        return deployed_pool_dict

    @serialized('purge_orphaned_pool')
    @is_operational
    @log_helpers.log_method_call
    def purge_orphaned_pool(self, tenant_id=None, pool_id=None,
                            hostnames=list()):
        node_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.node)
        for bigip in self.get_all_bigips():
            if bigip.hostname in hostnames:
                try:
                    pool_name = self.service_adapter.prefix + pool_id
                    partition = self.service_adapter.prefix + tenant_id
                    pool = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.pool).load(
                            bigip, pool_name, partition)
                    members = pool.members_s.get_collection()
                    pool.delete()
                    for member in members:
                        node_name = member.address
                        try:
                            node_helper.delete(bigip,
                                               name=urllib.quote(node_name),
                                               partition=partition)
                        except HTTPError as e:
                            if e.response.status_code == 404:
                                pass
                            if e.response.status_code == 400:
                                LOG.warn("Failed to delete node -- in use")
                            else:
                                LOG.exception("Failed to delete node")
                except HTTPError as err:
                    if err.response.status_code == 404:
                        LOG.debug('pool %s not on BIG-IP %s.'
                                  % (pool_id, bigip.hostname))
                except Exception as exc:
                    LOG.exception('Exception purging pool %s' % str(exc))

    @serialized('get_all_deployed_monitors')
    @is_operational
    def get_all_deployed_health_monitors(self):
        """Retrieve a list of all Health Monitors deployed"""
        LOG.debug('getting all deployed monitors on BIG-IP\'s')
        monitor_types = ['http_monitor', 'https_monitor', 'tcp_monitor',
                         'ping_monitor']
        deployed_monitor_dict = {}
        adapter_prefix = self.service_adapter.prefix
        for bigip in self.get_all_bigips():
            folders = self.system_helper.get_folders(bigip)
            for folder in folders:
                tenant_id = folder[len(adapter_prefix):]
                if str(folder).startswith(adapter_prefix):
                    resources = map(
                        lambda x: resource_helper.BigIPResourceHelper(
                            getattr(resource_helper.ResourceType, x)),
                        monitor_types)
                    for resource in resources:
                        deployed_monitors = resource.get_resources(
                            bigip, folder)
                        if deployed_monitors:
                            for monitor in deployed_monitors:
                                monitor_id = monitor.name[len(adapter_prefix):]
                                if monitor_id in deployed_monitor_dict:
                                    deployed_monitor_dict[monitor_id][
                                        'hostnames'].append(bigip.hostname)
                                else:
                                    deployed_monitor_dict[monitor_id] = {
                                        'id': monitor_id,
                                        'tenant_id': tenant_id,
                                        'hostnames': [bigip.hostname]
                                    }
        return deployed_monitor_dict

    @serialized('purge_orphaned_health_monitor')
    @is_operational
    @log_helpers.log_method_call
    def purge_orphaned_health_monitor(self, tenant_id=None, monitor_id=None,
                                      hostnames=list()):
        """Purge all monitors that exist on the BIG-IP but not in Neutron"""
        resource_types = [
            resource_helper.BigIPResourceHelper(x) for x in [
                resource_helper.ResourceType.http_monitor,
                resource_helper.ResourceType.https_monitor,
                resource_helper.ResourceType.ping_monitor,
                resource_helper.ResourceType.tcp_monitor]]
        for bigip in self.get_all_bigips():
            if bigip.hostname in hostnames:
                try:
                    monitor_name = self.service_adapter.prefix + monitor_id
                    partition = self.service_adapter.prefix + tenant_id
                    monitor = None
                    for monitor_type in resource_types:
                        try:
                            monitor = monitor_type.load(bigip, monitor_name,
                                                        partition)
                            break
                        except HTTPError as err:
                            if err.response.status_code == 404:
                                continue
                    monitor.delete()
                except TypeError as err:
                    if 'NoneType' in err:
                        LOG.exception("Could not find monitor {}".format(
                                      monitor_name))
                except Exception as exc:
                    LOG.exception('Exception purging monitor %s' % str(exc))

    @serialized('get_all_deployed_l7_policys')
    @is_operational
    def get_all_deployed_l7_policys(self):
        """Retrieve a dict of all l7policies deployed

        The dict returned will have the following format:
            {policy_bigip_id_0: {'id': policy_id_0,
                                 'tenant_id': tenant_id,
                                 'hostnames': [hostnames_0]}
             ...
            }
        Where hostnames is the list of BIG-IP hostnames impacted, and the
        policy_id is the policy_bigip_id without 'wrapper_policy_'
        """
        LOG.debug('getting all deployed l7_policys on BIG-IP\'s')
        deployed_l7_policys_dict = {}
        for bigip in self.get_all_bigips():
            folders = self.system_helper.get_folders(bigip)
            for folder in folders:
                tenant_id = folder[len(self.service_adapter.prefix):]
                if str(folder).startswith(self.service_adapter.prefix):
                    resource = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.l7policy)
                    deployed_l7_policys = resource.get_resources(
                        bigip, folder)
                    if deployed_l7_policys:
                        for l7_policy in deployed_l7_policys:
                            l7_policy_id = l7_policy.name
                            if l7_policy_id in deployed_l7_policys_dict:
                                my_dict = \
                                    deployed_l7_policys_dict[l7_policy_id]
                                my_dict['hostnames'].append(bigip.hostname)
                            else:
                                po_id = l7_policy_id.replace(
                                    'wrapper_policy_', '')
                                deployed_l7_policys_dict[l7_policy_id] = {
                                    'id': po_id,
                                    'tenant_id': tenant_id,
                                    'hostnames': [bigip.hostname]
                                }
        return deployed_l7_policys_dict

    @serialized('purge_orphaned_l7_policy')
    @is_operational
    @log_helpers.log_method_call
    def purge_orphaned_l7_policy(self, tenant_id=None, l7_policy_id=None,
                                 hostnames=list(), listener_id=None):
        """Purge all l7_policys that exist on the BIG-IP but not in Neutron"""
        for bigip in self.get_all_bigips():
            if bigip.hostname in hostnames:
                error = None
                try:
                    l7_policy_name = l7_policy_id
                    partition = self.service_adapter.prefix + tenant_id
                    if listener_id and partition:
                        if self.service_adapter.prefix not in listener_id:
                            listener_id = \
                                self.service_adapter.prefix + listener_id
                        li_resource = resource_helper.BigIPResourceHelper(
                            resource_helper.ResourceType.virtual).load(
                                bigip, listener_id, partition)
                        li_resource.update(policies=[])
                    l7_policy = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.l7policy).load(
                            bigip, l7_policy_name, partition)
                    l7_policy.delete()
                except HTTPError as err:
                    if err.response.status_code == 404:
                        LOG.debug('l7_policy %s not on BIG-IP %s.'
                                  % (l7_policy_id, bigip.hostname))
                    else:
                        error = err
                except Exception as exc:
                    error = err
                if error:
                    kwargs = dict(
                        tenant_id=tenant_id, l7_policy_id=l7_policy_id,
                        hostname=bigip.hostname, listener_id=listener_id)
                    LOG.exception('Exception: purge_orphaned_l7_policy({}) '
                                  '"{}"'.format(kwargs, exc))

    @serialized('purge_orphaned_loadbalancer')
    @is_operational
    @log_helpers.log_method_call
    def purge_orphaned_loadbalancer(self, tenant_id=None,
                                    loadbalancer_id=None, hostnames=list()):
        for bigip in self.get_all_bigips():
            if bigip.hostname in hostnames:
                try:
                    va_name = self.service_adapter.prefix + loadbalancer_id
                    partition = self.service_adapter.prefix + tenant_id
                    va = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.virtual_address).load(
                            bigip, va_name, partition)
                    # get virtual services (listeners)
                    # referencing this virtual address
                    vses = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.virtual).get_resources(
                            bigip, partition)
                    vs_dest_compare = '/' + partition + '/' + va.name
                    for vs in vses:
                        if str(vs.destination).startswith(vs_dest_compare):
                            if hasattr(vs, 'pool'):
                                pool = resource_helper.BigIPResourceHelper(
                                    resource_helper.ResourceType.pool).load(
                                        bigip, os.path.basename(vs.pool),
                                        partition)
                                vs.delete()
                                pool.delete()
                            else:
                                vs.delete()
                    resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.virtual_address).delete(
                            bigip, va_name, partition)
                except HTTPError as err:
                    if err.response.status_code == 404:
                        LOG.debug('loadbalancer %s not on BIG-IP %s.'
                                  % (loadbalancer_id, bigip.hostname))
                except Exception as exc:
                    LOG.exception('Exception purging loadbalancer %s'
                                  % str(exc))

    @serialized('purge_orphaned_listener')
    @is_operational
    @log_helpers.log_method_call
    def purge_orphaned_listener(
            self, tenant_id=None, listener_id=None, hostnames=[]):
        for bigip in self.get_all_bigips():
            if bigip.hostname in hostnames:
                try:
                    listener_name = self.service_adapter.prefix + listener_id
                    partition = self.service_adapter.prefix + tenant_id
                    listener = resource_helper.BigIPResourceHelper(
                        resource_helper.ResourceType.virtual).load(
                            bigip, listener_name, partition)
                    listener.delete()
                except HTTPError as err:
                    if err.response.status_code == 404:
                        LOG.debug('listener %s not on BIG-IP %s.'
                                  % (listener_id, bigip.hostname))
                except Exception as exc:
                    LOG.exception('Exception purging listener %s' % str(exc))

    @serialized('create_loadbalancer')
    @is_operational
    def create_loadbalancer(self, loadbalancer, service):
        """Create virtual server."""
        return self._common_service_handler(service)

    @serialized('update_loadbalancer')
    @is_operational
    def update_loadbalancer(self, old_loadbalancer, loadbalancer, service):
        """Update virtual server."""
        # anti-pattern three args unused.
        return self._common_service_handler(service)

    @serialized('delete_loadbalancer')
    @is_operational
    def delete_loadbalancer(self, loadbalancer, service):
        """Delete loadbalancer."""
        LOG.debug("Deleting loadbalancer")
        return self._common_service_handler(
            service,
            delete_partition=True,
            delete_event=True)

    @serialized('create_listener')
    @is_operational
    def create_listener(self, listener, service):
        """Create virtual server."""
        LOG.debug("Creating listener")
        return self._common_service_handler(service)

    @serialized('update_listener')
    @is_operational
    def update_listener(self, old_listener, listener, service):
        """Update virtual server."""
        LOG.debug("Updating listener")
        service['old_listener'] = old_listener
        return self._common_service_handler(service)

    @serialized('delete_listener')
    @is_operational
    def delete_listener(self, listener, service):
        """Delete virtual server."""
        LOG.debug("Deleting listener")
        return self._common_service_handler(service)

    @serialized('create_pool')
    @is_operational
    def create_pool(self, pool, service):
        """Create lb pool."""
        LOG.debug("Creating pool")
        return self._common_service_handler(service)

    @serialized('update_pool')
    @is_operational
    def update_pool(self, old_pool, pool, service):
        """Update lb pool."""
        LOG.debug("Updating pool")
        return self._common_service_handler(service)

    @serialized('delete_pool')
    @is_operational
    def delete_pool(self, pool, service):
        """Delete lb pool."""
        LOG.debug("Deleting pool")
        return self._common_service_handler(service)

    @serialized('create_member')
    @is_operational
    def create_member(self, member, service):
        """Create pool member."""
        LOG.debug("Creating member")
        return self._common_service_handler(service)

    @serialized('update_member')
    @is_operational
    def update_member(self, old_member, member, service):
        """Update pool member."""
        LOG.debug("Updating member")
        return self._common_service_handler(service)

    @serialized('delete_member')
    @is_operational
    def delete_member(self, member, service):
        """Delete pool member."""
        LOG.debug("Deleting member")
        return self._common_service_handler(service, delete_event=True)

    @serialized('create_health_monitor')
    @is_operational
    def create_health_monitor(self, health_monitor, service):
        """Create pool health monitor."""
        LOG.debug("Creating health monitor")
        return self._common_service_handler(service)

    @serialized('update_health_monitor')
    @is_operational
    def update_health_monitor(self, old_health_monitor,
                              health_monitor, service):
        """Update pool health monitor."""
        LOG.debug("Updating health monitor")
        return self._common_service_handler(service)

    @serialized('delete_health_monitor')
    @is_operational
    def delete_health_monitor(self, health_monitor, service):
        """Delete pool health monitor."""
        LOG.debug("Deleting health monitor")
        return self._common_service_handler(service)

    @is_operational
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
            lb_stats[f5const.F5_STATS_IN_BYTES] = \
                vs_stats['clientside.bitsIn']/8
            lb_stats[f5const.F5_STATS_OUT_BYTES] = \
                vs_stats['clientside.bitsOut']/8
            lb_stats[f5const.F5_STATS_ACTIVE_CONNECTIONS] = \
                vs_stats['clientside.curConns']
            lb_stats[f5const.F5_STATS_TOTAL_CONNECTIONS] = \
                vs_stats['clientside.totConns']

            # update Neutron
            self.plugin_rpc.update_loadbalancer_stats(
                loadbalancer['id'], lb_stats)
        except Exception as e:
            LOG.error("Error getting loadbalancer stats: %s", e.message)

        finally:
            return lb_stats

    def fdb_add(self, fdb):
        # Add (L2toL3) forwarding database entries
        for bigip in self.get_all_bigips():
            self.network_builder.add_bigip_fdb(bigip, fdb)

    def fdb_remove(self, fdb):
        # Remove (L2toL3) forwarding database entries
        for bigip in self.get_all_bigips():
            self.network_builder.remove_bigip_fdb(bigip, fdb)

    def fdb_update(self, fdb):
        # Update (L2toL3) forwarding database entries
        for bigip in self.get_all_bigips():
            self.network_builder.update_bigip_fdb(bigip, fdb)

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
    @is_operational
    def sync(self, service):
        """Sync service defintion to device."""
        # loadbalancer and plugin_rpc may not be set
        lb_id = service.get('loadbalancer', dict()).get('id', '')
        if hasattr(self, 'plugin_rpc') and self.plugin_rpc and lb_id:
            # Get the latest service. It may have changed.
            service = self.plugin_rpc.get_service_by_loadbalancer_id(lb_id)
        if service.get('loadbalancer', None):
            return self._common_service_handler(service)
        else:
            LOG.debug("Attempted sync of deleted pool")

    @serialized('backup_configuration')
    @is_operational
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
        elif monitor_type == "UDP":
            hm = bigip.tm.ltm.monitor.udps.udp
        elif monitor_type == "SIP":
            hm = bigip.tm.ltm.monitor.sips.sip
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
        # Returns whether the bigip has the service defined
        if not service['loadbalancer']:
            return False
        loadbalancer = service['loadbalancer']

        folder_name = self.service_adapter.get_folder_name(
            loadbalancer['tenant_id']
        )

        if self.network_builder:
            # append route domain to member address
            self.network_builder._annotate_service_route_domains(service)

        # Foreach bigip in the cluster:
        for bigip in self.get_config_bigips():
            # Does the tenant folder exist?
            if not self.system_helper.folder_exists(bigip, folder_name):
                LOG.debug("Folder %s does not exist on bigip: %s" %
                          (folder_name, bigip.hostname))
                return False

            # Get the virtual address
            virtual_address = VirtualAddress(self.service_adapter,
                                             loadbalancer)
            if not virtual_address.exists(bigip):
                LOG.debug("Virtual address %s(%s) does not "
                          "exist on bigip: %s" % (virtual_address.name,
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
                    LOG.debug("Virtual /%s/%s not found on bigip: %s" %
                              (virtual_server['name'], folder_name,
                               bigip.hostname))
                    return False

            # Ensure that each pool exists.
            for pool in service['pools']:
                svc = {"loadbalancer": loadbalancer,
                       "pool": pool}
                bigip_pool = self.service_adapter.get_pool(svc)
                if not self.pool_manager.exists(
                        bigip,
                        name=bigip_pool['name'],
                        partition=folder_name):
                    LOG.debug("Pool /%s/%s not found on bigip: %s" %
                              (folder_name, bigip_pool['name'],
                               bigip.hostname))
                    return False
                else:
                    deployed_pool = self.pool_manager.load(
                        bigip,
                        name=bigip_pool['name'],
                        partition=folder_name)
                    deployed_members = \
                        deployed_pool.members_s.get_collection()

                    # First check that number of members deployed
                    # is equal to the number in the service.
                    if len(deployed_members) != len(pool['members']):
                        LOG.debug("Pool %s members member count mismatch "
                                  "match: deployed %d != service %d" %
                                  (bigip_pool['name'], len(deployed_members),
                                   len(pool['members'])))
                        return False

                    # Ensure each pool member exists
                    for member in service['members']:
                        if member['pool_id'] == pool['id']:
                            lb = self.lbaas_builder
                            pool = lb.get_pool_by_id(
                                service, member["pool_id"])
                            svc = {"loadbalancer": loadbalancer,
                                   "member": member,
                                   "pool": pool}
                            if not lb.pool_builder.member_exists(svc, bigip):
                                LOG.debug("Pool member not found: %s" %
                                          svc['member'])
                                return False

            # Ensure that each health monitor exists.
            for healthmonitor in service['healthmonitors']:
                svc = {"loadbalancer": loadbalancer,
                       "healthmonitor": healthmonitor}
                monitor = self.service_adapter.get_healthmonitor(svc)
                monitor_ep = self._get_monitor_endpoint(bigip, svc)
                if not monitor_ep.exists(name=monitor['name'],
                                         partition=folder_name):
                    LOG.debug("Monitor /%s/%s not found on bigip: %s" %
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
                                                  f5const.F5_ERROR)
        try:
            try:
                self.tenant_manager.assure_tenant_created(service)
            except Exception as e:
                LOG.error("Tenant folder creation exception: %s",
                          e.message)
                if lb_provisioning_status != f5const.F5_PENDING_DELETE:
                    loadbalancer['provisioning_status'] = \
                        f5const.F5_ERROR
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
                    if lb_provisioning_status != f5const.F5_PENDING_DELETE:
                        loadbalancer['provisioning_status'] = \
                            f5const.F5_ERROR
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

                    if lb_provisioning_status != f5const.F5_PENDING_DELETE:
                        loadbalancer['provisioning_status'] = \
                            f5const.F5_ERROR
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
            if lb_provisioning_status == f5const.F5_PENDING_DELETE:
                self.tenant_manager.assure_tenant_cleanup(service,
                                                          all_subnet_hints)

            if do_service_update:
                self.update_service_status(service)

            lb_provisioning_status = loadbalancer.get("provisioning_status",
                                                      f5const.F5_ERROR)
            lb_pending = \
                (lb_provisioning_status == f5const.F5_PENDING_CREATE or
                 lb_provisioning_status == f5const.F5_PENDING_UPDATE)

        return lb_pending

    def update_service_status(self, service, timed_out=False):
        """Update status of objects in controller."""
        LOG.debug("_update_service_status")

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
        if 'l7policy_rules' in service:
            self._update_l7rule_status(service['l7policy_rules'])
        if 'l7policies' in service:
            self._update_l7policy_status(service['l7policies'])

        self._update_loadbalancer_status(service, timed_out)

    def _update_member_status(self, members, timed_out):
        """Update member status in OpenStack."""
        for member in members:
            if 'provisioning_status' in member:
                provisioning_status = member['provisioning_status']

                if provisioning_status in self.positive_plugin_const_state:

                    if timed_out and \
                            provisioning_status != f5const.F5_ACTIVE:
                        member['provisioning_status'] = f5const.F5_ERROR
                        operating_status = f5const.F5_OFFLINE
                    else:
                        member['provisioning_status'] = f5const.F5_ACTIVE
                        operating_status = f5const.F5_ONLINE

                    self.plugin_rpc.update_member_status(
                        member['id'],
                        member['provisioning_status'],
                        operating_status
                    )
                elif provisioning_status == f5const.F5_PENDING_DELETE:
                    if not member.get('parent_pool_deleted', False):
                        self.plugin_rpc.member_destroyed(
                            member['id'])
                elif provisioning_status == f5const.F5_ERROR:
                    self.plugin_rpc.update_member_status(
                        member['id'],
                        f5const.F5_ERROR,
                        f5const.F5_OFFLINE)

    def _update_health_monitor_status(self, health_monitors):
        """Update pool monitor status in OpenStack."""
        for health_monitor in health_monitors:
            if 'provisioning_status' in health_monitor:
                provisioning_status = health_monitor['provisioning_status']
                if provisioning_status in self.positive_plugin_const_state:
                    self.plugin_rpc.update_health_monitor_status(
                        health_monitor['id'],
                        f5const.F5_ACTIVE,
                        f5const.F5_ONLINE
                    )
                    health_monitor['provisioning_status'] = \
                        f5const.F5_ACTIVE
                elif provisioning_status == f5const.F5_PENDING_DELETE:
                    self.plugin_rpc.health_monitor_destroyed(
                        health_monitor['id'])
                elif provisioning_status == f5const.F5_ERROR:
                    self.plugin_rpc.update_health_monitor_status(
                        health_monitor['id'])

    @log_helpers.log_method_call
    def _update_pool_status(self, pools):
        """Update pool status in OpenStack."""
        for pool in pools:
            if 'provisioning_status' in pool:
                provisioning_status = pool['provisioning_status']
                if provisioning_status in self.positive_plugin_const_state:
                    self.plugin_rpc.update_pool_status(
                        pool['id'],
                        f5const.F5_ACTIVE,
                        f5const.F5_ONLINE
                    )
                    pool['provisioning_status'] = f5const.F5_ACTIVE
                elif provisioning_status == f5const.F5_PENDING_DELETE:
                    self.plugin_rpc.pool_destroyed(
                        pool['id'])
                elif provisioning_status == f5const.F5_ERROR:
                    self.plugin_rpc.update_pool_status(pool['id'])

    @log_helpers.log_method_call
    def _update_listener_status(self, service):
        """Update listener status in OpenStack."""
        listeners = service['listeners']
        for listener in listeners:
            if 'provisioning_status' in listener:
                provisioning_status = listener['provisioning_status']
                if provisioning_status in self.positive_plugin_const_state:
                    self.plugin_rpc.update_listener_status(
                        listener['id'],
                        f5const.F5_ACTIVE,
                        listener['operating_status']
                    )
                    listener['provisioning_status'] = \
                        f5const.F5_ACTIVE
                elif provisioning_status == f5const.F5_PENDING_DELETE:
                    self.plugin_rpc.listener_destroyed(
                        listener['id'])
                elif provisioning_status == f5const.F5_ERROR:
                    self.plugin_rpc.update_listener_status(
                        listener['id'],
                        provisioning_status,
                        f5const.F5_OFFLINE)

    @log_helpers.log_method_call
    def _update_l7rule_status(self, l7rules):
        """Update l7rule status in OpenStack."""
        for l7rule in l7rules:
            if 'provisioning_status' in l7rule:
                provisioning_status = l7rule['provisioning_status']
                if provisioning_status in self.positive_plugin_const_state:
                    self.plugin_rpc.update_l7rule_status(
                        l7rule['id'],
                        l7rule['policy_id'],
                        f5const.F5_ACTIVE,
                        f5const.F5_ONLINE
                    )
                elif provisioning_status == f5const.F5_PENDING_DELETE:
                    self.plugin_rpc.l7rule_destroyed(
                        l7rule['id'])
                elif provisioning_status == f5const.F5_ERROR:
                    self.plugin_rpc.update_l7rule_status(
                        l7rule['id'], l7rule['policy_id'])

    @log_helpers.log_method_call
    def _update_l7policy_status(self, l7policies):
        LOG.debug("_update_l7policy_status")
        """Update l7policy status in OpenStack."""
        for l7policy in l7policies:
            if 'provisioning_status' in l7policy:
                provisioning_status = l7policy['provisioning_status']
                if provisioning_status in self.positive_plugin_const_state:
                    self.plugin_rpc.update_l7policy_status(
                        l7policy['id'],
                        f5const.F5_ACTIVE,
                        f5const.F5_ONLINE
                    )
                elif provisioning_status == f5const.F5_PENDING_DELETE:
                    LOG.debug("calling l7policy_destroyed")
                    self.plugin_rpc.l7policy_destroyed(
                        l7policy['id'])
                elif provisioning_status == f5const.F5_ERROR:
                    self.plugin_rpc.update_l7policy_status(l7policy['id'])

    @log_helpers.log_method_call
    def _update_loadbalancer_status(self, service, timed_out=False):
        """Update loadbalancer status in OpenStack."""
        loadbalancer = service.get('loadbalancer', {})
        provisioning_status = loadbalancer.get('provisioning_status',
                                               f5const.F5_ERROR)

        if provisioning_status in self.positive_plugin_const_state:
            if timed_out:
                operating_status = (f5const.F5_OFFLINE)
                if provisioning_status == f5const.F5_PENDING_CREATE:
                    loadbalancer['provisioning_status'] = \
                        f5const.F5_ERROR
                else:
                    loadbalancer['provisioning_status'] = \
                        f5const.F5_ACTIVE
            else:
                operating_status = (f5const.F5_ONLINE)
                loadbalancer['provisioning_status'] = \
                    f5const.F5_ACTIVE

            self.plugin_rpc.update_loadbalancer_status(
                loadbalancer['id'],
                loadbalancer['provisioning_status'],
                operating_status)

        elif provisioning_status == f5const.F5_PENDING_DELETE:
            self.plugin_rpc.loadbalancer_destroyed(
                loadbalancer['id'])
        elif provisioning_status == f5const.F5_ERROR:
            self.plugin_rpc.update_loadbalancer_status(
                loadbalancer['id'],
                provisioning_status,
                f5const.F5_OFFLINE)
        elif provisioning_status == f5const.F5_ACTIVE:
            LOG.debug('Loadbalancer provisioning status is active')
        else:
            LOG.error('Loadbalancer provisioning status is invalid')

    @is_operational
    def update_operating_status(self, service):
        if 'members' in service:
            if self.network_builder:
                # append route domain to member address
                try:
                    self.network_builder._annotate_service_route_domains(
                        service)
                except f5ex.InvalidNetworkType as exc:
                    LOG.warning(exc.message)
                    return

            # get currrent member status
            self.lbaas_builder.update_operating_status(service)

            # udpate Neutron
            for member in service['members']:
                if member['provisioning_status'] == f5const.F5_ACTIVE:
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
            if hasattr(bigip, 'failover_state'):
                if bigip.failover_state == 'active':
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

    # these functions should return only active BIG-IP
    # not errored BIG-IPs.
    def get_bigip(self):
        hostnames = sorted(list(self.__bigips))
        for host in hostnames:
            if hasattr(self.__bigips[host], 'status') and \
               self.__bigips[host].status == 'active':
                return self.__bigips[host]

    def get_bigip_hosts(self):
        return_hosts = []
        for host in list(self.__bigips):
            if hasattr(self.__bigips[host], 'status') and \
               self.__bigips[host].status == 'active':
                return_hosts.append(host)
        return sorted(return_hosts)

    def get_all_bigips(self):
        return_bigips = []
        for host in list(self.__bigips):
            if hasattr(self.__bigips[host], 'status') and \
               self.__bigips[host].status == 'active':
                return_bigips.append(self.__bigips[host])
        return return_bigips

    def get_config_bigips(self):
        return self.get_all_bigips()

    # these are the refactored methods
    def get_active_bigips(self):
        return self.get_all_bigips()

    def get_errored_bigips_hostnames(self):
        return_hostnames = []
        for host in list(self.__bigips):
            bigip = self.__bigips[host]
            if hasattr(bigip, 'status') and bigip.status == 'error':
                return_hostnames.append(host)
        return return_hostnames

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
        try:
            LOG.debug('retrieving traffic groups from %s' % bigip.hostname)
            self.__traffic_groups = \
                self.cluster_manager.get_traffic_groups(bigip)
            if 'traffic-group-local-only' in self.__traffic_groups:
                LOG.debug('removing reference to non-floating traffic group')
                self.__traffic_groups.remove('traffic-group-local-only')
            self.__traffic_groups.sort()
            LOG.debug('service placement will done on traffic group(s): %s'
                      % self.__traffic_groups)
        except Exception:
            bigip.status = 'error'
            bigip.status_message = \
                'could not determine traffic groups for service placement'
            raise

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

    @serialized('create_l7policy')
    @is_operational
    def create_l7policy(self, l7policy, service):
        """Create lb l7policy."""
        LOG.debug("Creating l7policy")
        self._common_service_handler(service)

    @serialized('update_l7policy')
    @is_operational
    def update_l7policy(self, old_l7policy, l7policy, service):
        """Update lb l7policy."""
        LOG.debug("Updating l7policy")
        self._common_service_handler(service)

    @serialized('delete_l7policy')
    @is_operational
    def delete_l7policy(self, l7policy, service):
        """Delete lb l7policy."""
        LOG.debug("Deleting l7policy")
        self._common_service_handler(service)

    @serialized('create_l7rule')
    @is_operational
    def create_l7rule(self, pool, service):
        """Create lb l7rule."""
        LOG.debug("Creating l7rule")
        self._common_service_handler(service)

    @serialized('update_l7rule')
    @is_operational
    def update_l7rule(self, old_l7rule, l7rule, service):
        """Update lb l7rule."""
        LOG.debug("Updating l7rule")
        self._common_service_handler(service)

    @serialized('delete_l7rule')
    @is_operational
    def delete_l7rule(self, l7rule, service):
        """Delete lb l7rule."""
        LOG.debug("Deleting l7rule")
        self._common_service_handler(service)

    def trace_service_requests(self, service):
        """Dump services to a file for debugging."""
        with open(self.file_name, 'r+') as fp:
            fp.seek(-1, 2)
            fp.write(',')
            json.dump(service, fp, sort_keys=True, indent=2)
            fp.write(']')

    def get_config_dir(self):
        """Determine F5 agent configuration directory.

        Oslo cfg has a config_dir option, but F5 agent is not currently
        started with this option. To be complete, the code will check if
        config_dir is defined, and use that value as long as it is a single
        string (no idea what to do if it is not a str). If not defined,
        get the full dir path of the INI file, which is currently used when
        starting F5 agent. If neither option is available,
        use /etc/neutron/services/f5.

        :return: str defining configuration directory.
        """
        if self.conf.config_dir and isinstance(self.conf.config_dir, str):
            # use config_dir parameter if defined, and is a string
            return self.conf.config_dir
        elif self.conf.config_file:
            # multiple config files (neutron and agent) are usually defined
            if isinstance(self.conf.config_file, list):
                # find agent config (f5-openstack-agent.ini)
                config_files = self.conf.config_file
                for file_name in config_files:
                    if 'f5-openstack-agent.ini' in file_name:
                        return os.path.dirname(file_name)
            elif isinstance(self.conf.config_file, str):
                # not a list, just a single string
                return os.path.dirname(self.conf.config_file)

        # if all else fails
        return '/etc/neutron/services/f5'
