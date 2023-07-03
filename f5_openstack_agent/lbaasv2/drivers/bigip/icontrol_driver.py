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
import hashlib
import json
import os

from cryptography.fernet import Fernet
# from eventlet import greenthread
from time import strftime

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import importutils

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
        'confd_hostname',
        default="",
        help='The hostname (name or IP address) to use for F5OS confd access'
    ),
    cfg.IntOpt(
        'confd_port',
        default=443,
        help='The port to use for F5OS confd access'
    ),
    cfg.StrOpt(
        'confd_username', default='admin',
        help='The username to use for F5OS confd access'
    ),
    cfg.StrOpt(
        'confd_password', default='', secret=True,
        help='The password to use for F5OS confd access'
    ),
    cfg.StrOpt(
        've_tenant', default="",
        help='Default VE tenant name in F5OS to deploy loadbalancer'
    ),
    cfg.StrOpt(
        'lag_interface', default="",
        help='Default LAG interface name in F5OS to associate vlan'
    ),
    cfg.StrOpt(
        'icontrol_vcmp_hostname',
        help='The hostname (name or IP address) to use for vCMP Host '
             'iControl access'
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
        default=1,
        help="connection rate limit ratio for listener, setting to 5 means "
        "a listener's connection rate limit will be set to 1/5 of the lb's "
        "upper limit, which is predefined by the flavors 1-7."
    ),
    cfg.IntOpt(
        'tcp_options',
        default=254,
        help='Default tcp Options value of server tcp profile'
    ),
    cfg.BoolOpt(
        'use_mgmt_ipv6',
        default=False,
        help='Use IPv6 management address of device instead of IPv4'
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

        # base configurations to report to Neutron agent state reports
        self.agent_configurations = {}  # overrides base, same value

        # service component managers
        self.tenant_manager = None
        self.cluster_manager = None
        self.system_helper = None
        self.lbaas_builder = None
        self.service_adapter = None
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
            else:
                for net_id in self.conf.common_network_ids:
                    LOG.debug('network %s will be mapped to /Common/%s'
                              % (net_id, self.conf.common_network_ids[net_id]))

                LOG.debug('Setting static ARP population to %s'
                          % self.conf.f5_populate_static_arp)
                f5const.FDB_POPULATE_STATIC_ARP = \
                    self.conf.f5_populate_static_arp

            # instantiate the managers
            self._init_bigip_managers()

            self.initialized = True
            LOG.debug('iControlDriver loaded successfully')
        except Exception as exc:
            LOG.error("exception in intializing driver %s" % str(exc))
            self._set_agent_status(False)

    def _init_bigip_managers(self):

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

    def _set_agent_status(self, force_resync=False):

        # Policy - if any BIG-IP are active we're operational
        if self.get_active_bigips():
            self.operational = True
        else:
            self.operational = False
        if self.agent_report_state:
            self.agent_report_state(force_resync=force_resync)

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

    def tunnel_update(self, **kwargs):
        # Tunnel Update from Neutron Core RPC
        pass

    def tunnel_sync(self):
        # Only sync when supported types are present
        if not self.conf.f5_global_routed_mode:
            if not [i for i in self.conf.advertised_tunnel_types
                    if i in ['gre', 'vxlan']]:
                return False

        tunnel_ips = []
        for bigip in self.get_all_bigips():
            if bigip.local_ip:
                tunnel_ips.append(bigip.local_ip)

        self.network_builder.tunnel_sync(tunnel_ips)

        # Tunnel sync sent.
        return False

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

        bigips = service['bigips']
        loadbalancer = service['loadbalancer']

        # Does the correctly named virtual address exist?
        for bigip in bigips:
            virtual_address = VirtualAddress(self.service_adapter,
                                             loadbalancer)
            if not virtual_address.exists(bigip):
                rename_required = True
                break

        return rename_required

    # pzhang: is anyone use this function?
    def service_object_teardown(self, service):

        # Returns whether the bigip has a pool for the service
        if not service['loadbalancer']:
            return False

        bigips = service['bigips']
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

        for bigip in service['bigips']:
            # Does the tenant folder exist?
            if not self.system_helper.folder_exists(bigip, folder_name):
                LOG.debug("Folder %s does not exist on bigip: %s" %
                          (folder_name, bigip.hostname))
                return False

        if self.network_builder:
            # append route domain to member address
            self.network_builder._annotate_service_route_domains(service)

        # Foreach bigip in the cluster:
        for bigip in service['bigips']:

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

    def get_traffic_group_1(self):
        return "traffic-group-1"

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

    # these are the refactored methods
    def get_active_bigips(self):
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


# Decrypt device password

def generate_key(key):
    h = hashlib.md5(key.encode()).hexdigest()
    return base64.urlsafe_b64encode(h.encode())


def decrypt_data(key, data):
    f = Fernet(generate_key(key))
    return f.decrypt(data.encode()).decode()
