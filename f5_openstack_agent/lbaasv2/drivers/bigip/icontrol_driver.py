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

import base64
import datetime
import hashlib
import json
import logging as std_logging
import os
import signal

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
from time import strftime

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
    cfg.IntOpt(
        'icontrol_port',
        default=443,
        help='The port to use for iControl access'
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
        'separate_host',
        default=False,
        help='whether to use separate host'
    ),
    cfg.IntOpt(
        'persistence_timeout',
        default=1800,
        help='Default timeout of session persistionce profile'
    ),
    cfg.StrOpt(
        'bwc_profile',
        default=None,
        help='bwc_profile name which is configured in bigip side'
    ),
    cfg.IntOpt(
        'connection_rate_limit_ratio',
        default=5,
        help="connection rate limit ratio for listener, setting to 5 means "
        "a listener's connection rate limit will be set to 1/5 of the lb's "
        "upper limit, which is predefined by the flavors 1-7."
    ),
    cfg.IntOpt(
        'tcp_options',
        default=254,
        help='Default tcp Options value of server tcp profile'
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
        # set the options manually instead.
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

        if self.conf.password_cipher_mode:
            self.conf.icontrol_password = \
                base64.b64decode(self.conf.icontrol_password)
            if self.conf.os_password:
                self.conf.os_password = base64.b64decode(self.conf.os_password)

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
        # initialize communications with BIG-IP via iControl
        try:
            self._init_bigips()
        except Exception as exc:
            LOG.error("exception in intializing communications to BIG-IPs %s"
                      % str(exc))
            self._set_agent_status(False)

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
        LOG.debug('checking communications to BIG-IPs')
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
                if bigip.status == 'active':
                    continue

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
        # Open bigip connection
        try:
            bigip = self.__bigips[hostname]
            # active creating connected initializing validating_HA
            # error connecting. If status is e.g. 'initializing' etc,
            # seems should try to connect again, otherwise status stucks
            # the same forever.
            if bigip.status == 'active':
                LOG.debug('BIG-IP %s status is %s, skip reopen it.'
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
                                   port=self.conf.icontrol_port,
                                   debug=self.conf.debug)
            bigip.status = 'connected'
            bigip.status_message = 'connected to BIG-IP'
            self.__bigips[hostname] = bigip
            return bigip
        except Exception as exc:
            LOG.error('could not communicate with ' +
                      'iControl device: %s' % hostname)
            # pzhang: reset the signal from icontrol sdk
            signal.alarm(0)
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

        self._set_agent_status(False)

    def _validate_ha(self, bigip):
        # if there was only one address supplied and
        # this is not a standalone device, get the
        # devices trusted by this device.
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

        ic_host['license'] = {}
        modules = self.system_helper.get_active_modules(bigip)
        for module in modules:
            a = module.find(",")
            b = module.find("|")
            if a > 0 and a+2 < b:
                ic_host['license'][module[0:a]] = module[a+2:b]

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

    def flush_cache(self):
        # Remove cached objects so they can be created if necessary
        for bigip in self.get_all_bigips():
            bigip.assured_networks = {}
            bigip.assured_tenant_snat_subnets = {}
            bigip.assured_gateway_subnets = []

    @serialized('get_all_pools_for_one_bigip')
    @is_operational
    def get_all_pools_for_one_bigip(self, bigip):
        LOG.debug('getting deployed pools for member on BIG-IPs')
        deployed_pool_dict = {}
        if not bigip:
            LOG.debug("bigip is empty.")
            return
        prefix_name = self.service_adapter.prefix
        prefix_len = len(prefix_name)
        folders = self.system_helper.get_folders(bigip)
        LOG.debug('get %d folder(s).', len(folders))

        for folder in folders:
            tenant_id = folder[prefix_len:]
            if str(folder).startswith(prefix_name):
                resource = resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.pool)
                deployed_pools = resource.get_resources(bigip, folder)
                if deployed_pools:
                    LOG.debug("get %d pool(s) for %s.",
                              len(deployed_pools), str(folder))
                    for pool in deployed_pools:
                        if not str(pool.name).startswith(prefix_name):
                            LOG.debug("folder %s doesn't start with prefix.",
                                      str(pool.name))
                            continue
                        pool_id = pool.name[prefix_len:]
                        if pool_id not in deployed_pool_dict:
                            deployed_pool_dict[pool_id] = {
                                'id': pool_id,
                                'tenant_id': tenant_id,
                                'hostnames': [bigip.hostname]
                            }
        return deployed_pool_dict

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

    def get_loadbalancers_in_tenant(self, tenant_id):
        loadbalancers = self.plugin_rpc.get_all_loadbalancers()

        return [lb['lb_id'] for lb in loadbalancers
                if lb['tenant_id'] == tenant_id]

    def annotate_service_members(self, service):
        """Assure network connectivity is established on all bigips."""
        if self.conf.f5_global_routed_mode:
            return

        if self.conf.use_namespaces:
            try:
                LOG.debug("Annotating the service definition networks "
                          "with route domain ID.")
                self.network_builder._annotate_service_route_domains(service)
            except f5ex.InvalidNetworkType as exc:
                LOG.warning(exc.message)
            except Exception as err:
                LOG.exception(err)
                raise f5ex.RouteDomainCreationException(
                    "Route domain annotation error")

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

    def set_all_bigips(self, **kwargs):
        return_bigips = []
        for host in list(self.__bigips):
            if hasattr(self.__bigips[host], 'status') and \
               self.__bigips[host].status == 'active':
                return_bigips.append(self.__bigips[host])
        msg = "Current active bigips are:"
        for bigip in return_bigips:
            msg = msg + " " + bigip.hostname
        LOG.debug(msg)

        if len(return_bigips) == 0 and \
           kwargs.get('no_bigip_exception') is True:
            raise Exception("No active bigips!")

        return return_bigips

    def get_all_bigips(self, **kwargs):
        return_bigips = []
        for host in list(self.__bigips):
            if hasattr(self.__bigips[host], 'status') and \
               self.__bigips[host].status == 'active':
                return_bigips.append(self.__bigips[host])
        msg = "Current active bigips are:"
        for bigip in return_bigips:
            msg = msg + " " + bigip.hostname
        LOG.debug(msg)

        if len(return_bigips) == 0 and \
           kwargs.get('no_bigip_exception') is True:
            raise Exception("No active bigips!")

        return return_bigips

    def get_config_bigips(self, **kwargs):
        return self.get_all_bigips(**kwargs)

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
