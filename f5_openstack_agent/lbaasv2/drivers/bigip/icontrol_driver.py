""" F5 Networks LBaaS Driver using iControl API of BIG-IP """
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

import logging as std_logging
from time import time
import uuid

from neutron.common.exceptions import InvalidConfigurationOption
from neutron.plugins.common import constants as plugin_const
from neutron_lbaas.services.loadbalancer import constants as lb_const
from oslo_config import cfg
from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_driver import \
    LBaaSBaseDriver
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import OBJ_PREFIX
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import serialized
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import strip_domain_address

LOG = logging.getLogger(__name__)
NS_PREFIX = 'qlbaas-'
__VERSION__ = '0.1.1'

# configuration objects specific to iControl driver
OPTS = [
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
        'sync_mode', default='replication',
        help='The sync mechanism: autosync or replication'
    ),
    cfg.StrOpt(
        'f5_sync_mode', default='replication',
        help='The sync mechanism: autosync or replication'
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
        'f5_populate_static_arp', default=True,
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
        default="localhost",
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
    )
]


def is_connected(method):
    """Decorator to check we are connected before provisioning."""
    def wrapper(*args, **kwargs):
        """Necessary wrapper """
        instance = args[0]
        if instance.connected:
            try:
                return method(*args, **kwargs)
            except IOError as ioe:
                LOG.error('IO Error detected: %s' % method.__name__)
                instance.connect_bigips()
                raise ioe
        else:
            LOG.error('Cannot execute %s. Not connected. Connecting.'
                      % method.__name__)
            instance.connect_bigips()
    return wrapper


class iControlDriver(LBaaSBaseDriver):
    """F5 LBaaS Driver for BIG-IP using iControl"""

    def __init__(self, conf, registerOpts=True):
        # The registerOpts parameter allows a test to
        # turn off config option handling so that it can
        # set the options manually instead. """
        super(iControlDriver, self).__init__(conf)
        self.conf = conf
        if registerOpts:
            self.conf.register_opts(OPTS)
        self.hostnames = None
        self.device_type = conf.f5_device_type
        self.plugin_rpc = None
        self.__last_connect_attempt = None

        # BIG-IP containers
        self.__bigips = {}
        self.__traffic_groups = []

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

            if self.conf.environment_prefix:
                LOG.debug('BIG-IP name prefix for this environment: %s' %
                          self.conf.environment_prefix)
                # bigip_interfaces.OBJ_PREFIX = \
                #            self.conf.environment_prefix + '_'

            LOG.debug('Setting static ARP population to %s'
                      % self.conf.f5_populate_static_arp)
            # f5const.FDB_POPULATE_STATIC_ARP=self.conf.f5_populate_static_arp

        self._init_bigip_hostnames()

        self.vcmp_manager = None
        self.tenant_manager = None
        self.fdb_connector = None
        self.bigip_l2_manager = None
        self.vlan_binding = None
        self.l3_binding = None
        self.network_builder = None
        self.lbaas_builder_bigip_iapp = None
        self.lbaas_builder_bigip_objects = None
        self.lbaas_builder_bigiq_iapp = None

        # self._init_bigip_managers()
        # self.connect_bigips()
        self.connected = True

        LOG.info('iControlDriver initialized to %d bigips with username:%s'
                 % (len(self.__bigips), self.conf.icontrol_username))
        LOG.info('iControlDriver dynamic agent configurations:%s'
                 % self.agent_configurations)

    def connect_bigips(self):
        """Connect big-ips """
        pass

    def post_init(self):
        """Run and Post Initialization Tasks """
        # run any post initialized tasks, now that the agent
        # is fully connected
        LOG.debug('Getting BIG-IP device interface for VLAN Binding')

    def _init_bigip_managers(self):
        """Setup the managers that create big-ip configurations. """
        pass

    def _init_bigip_hostnames(self):
        """Validate and parse bigip credentials """
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

        # Setting an agent_id is the flag to the agent manager
        # that your plugin has initialized correctly. If you
        # don't set one, the agent manager will not register
        # with Neutron as a valid agent.
        if self.conf.environment_prefix:
            self.agent_id = str(
                uuid.uuid5(uuid.NAMESPACE_DNS,
                           self.conf.environment_prefix +
                           '.' + self.hostnames[0])
                )
        else:
            self.agent_id = str(
                uuid.uuid5(uuid.NAMESPACE_DNS, self.hostnames[0])
            )

    def _init_bigips(self):
        """Connect to all BIG-IPs """
        pass

    def _open_bigip(self, hostname):
        """Open bigip connection """
        LOG.info('Opening iControl connection to %s @ %s' %
                 (self.conf.icontrol_username, hostname))

    def _init_bigip(self, bigip, hostname, check_group_name=None):
        """Prepare a bigip for usage """
        pass

    def _validate_ha(self, first_bigip):
        # if there was only one address supplied and
        # this is not a standalone device, get the
        # devices trusted by this device. """
        pass

    def _init_agent_config(self, local_ips):
        """Init agent config """
        pass

    def generate_capacity_score(self, capacity_policy=None):
        """Generate the capacity score of connected devices """
        return 0

    def set_context(self, context):
        """Context to keep for database access """
        self.context = context

    def set_plugin_rpc(self, plugin_rpc):
        """Provide Plugin RPC access """
        self.plugin_rpc = plugin_rpc

    def set_tunnel_rpc(self, tunnel_rpc):
        """Provide FDB Connector with ML2 RPC access """
        pass

    def set_l2pop_rpc(self, l2pop_rpc):
        """Provide FDB Connector with ML2 RPC access """
        pass

    def exists(self, service):
        """Check that service exists"""
        return True

    def flush_cache(self):
        """Remove cached objects so they can be created if necessary"""
        pass

    @serialized('create_loadbalancer')
    @is_connected
    def create_loadbalancer(self, loadbalancer, service):
        """Create virtual server"""
        self._common_service_handler(service)

    @serialized('update_loadbalancer')
    @is_connected
    def update_loadbalancer(self, old_loadbalancer, loadbalancer, service):
        """Update virtual server"""
        self._common_service_handler(service)

    @serialized('delete_loadbalancer')
    @is_connected
    def delete_loadbalancer(self, loadbalancer, service):
        """Delete virtual server"""
        self._common_service_handler(service)


    @serialized('create_listener')
    @is_connected
    def create_listener(self, listener, service):
        """Create virtual server"""
        self._common_service_handler(service)

    @serialized('update_listener')
    @is_connected
    def update_listener(self, old_listener, listener, service):
        """Update virtual server"""
        self._common_service_handler(service)

    @serialized('delete_listener')
    @is_connected
    def delete_listener(self, listener, service):
        """Delete virtual server"""
        self._common_service_handler(service)

    @serialized('create_pool')
    @is_connected
    def create_pool(self, pool, service):
        """Create lb pool"""
        self._common_service_handler(service)

    @serialized('update_pool')
    @is_connected
    def update_pool(self, old_pool, pool, service):
        """Update lb pool"""
        self._common_service_handler(service)

    @serialized('delete_pool')
    @is_connected
    def delete_pool(self, pool, service):
        """Delete lb pool"""
        self._common_service_handler(service)

    @serialized('create_member')
    @is_connected
    def create_member(self, member, service):
        """Create pool member"""
        self._common_service_handler(service)

    @serialized('update_member')
    @is_connected
    def update_member(self, old_member, member, service):
        """Update pool member"""
        self._common_service_handler(service)

    @serialized('delete_member')
    @is_connected
    def delete_member(self, member, service):
        """Delete pool member"""
        self._common_service_handler(service)

    @serialized('create_pool_health_monitor')
    @is_connected
    def create_pool_health_monitor(self, health_monitor, pool, service):
        """Create pool health monitor"""
        self._common_service_handler(service)
        return True

    @serialized('update_health_monitor')
    @is_connected
    def update_health_monitor(self, old_health_monitor,
                              health_monitor, pool, service):
        """Update pool health monitor"""
        # The altered health monitor does not mark its
        # status as PENDING_UPDATE properly.  Force it.
        for i in range(len(service['pool']['health_monitors_status'])):
            if service['pool']['health_monitors_status'][i]['monitor_id'] == \
                    health_monitor['id']:
                service['pool']['health_monitors_status'][i]['status'] = \
                    plugin_const.PENDING_UPDATE
        self._common_service_handler(service)
        return True

    @serialized('delete_pool_health_monitor')
    @is_connected
    def delete_pool_health_monitor(self, health_monitor, pool, service):
        """Delete pool health monitor"""
        # Two behaviors of the plugin dictate our behavior here.
        # 1. When a plug-in deletes a monitor that is not being
        # used by a pool, it does not notify the drivers. Therefore,
        # we need to aggresively remove monitors that are not in use.
        # 2. When a plug-in deletes a monitor which is being
        # used by one or more pools, it calls delete_pool_health_monitor
        # against the driver that owns each pool, but it does not
        # set status to PENDING_DELETE in the health_monitors_status
        # list for the pool monitor. This may be a bug or perhaps this
        # is intended to be a synchronous process.
        #
        # In contrast, when a pool monitor association is deleted, the
        # PENDING DELETE status is set properly, so this code will
        # run unnecessarily in that case.
        for status in service['pool']['health_monitors_status']:
            if status['monitor_id'] == health_monitor['id']:
                # Signal to our own code that we should delete the
                # pool health monitor. The plugin should do this.
                status['status'] = plugin_const.PENDING_DELETE

        self._common_service_handler(service)
        return True
    # pylint: enable=unused-argument

    @is_connected
    def get_stats(self, service):
        """Get service stats"""
        # use pool stats because the pool_id is the
        # the service definition...
        stats = {}
        stats[lb_const.STATS_IN_BYTES] = 0
        stats[lb_const.STATS_OUT_BYTES] = 0
        stats[lb_const.STATS_ACTIVE_CONNECTIONS] = 0
        stats[lb_const.STATS_TOTAL_CONNECTIONS] = 0
        # add a members stats return dictionary
        members = {}
        for hostbigip in self.get_all_bigips():
            # It appears that stats are collected for pools in a pending delete
            # state which means that if those messages are queued (or delayed)
            # it can result in the process of a stats request after the pool
            # and tenant are long gone. Check if the tenant exists.
            if not service['pool'] or not hostbigip.system.folder_exists(
                    OBJ_PREFIX + service['pool']['tenant_id']):
                return None
            pool = service['pool']
            pool_stats = hostbigip.pool.get_statistics(
                name=pool['id'],
                folder=pool['tenant_id'],
                config_mode=self.conf.icontrol_config_mode)
            if 'STATISTIC_SERVER_SIDE_BYTES_IN' in pool_stats:
                stats[lb_const.STATS_IN_BYTES] += \
                    pool_stats['STATISTIC_SERVER_SIDE_BYTES_IN']
                stats[lb_const.STATS_OUT_BYTES] += \
                    pool_stats['STATISTIC_SERVER_SIDE_BYTES_OUT']
                stats[lb_const.STATS_ACTIVE_CONNECTIONS] += \
                    pool_stats['STATISTIC_SERVER_SIDE_CURRENT_CONNECTIONS']
                stats[lb_const.STATS_TOTAL_CONNECTIONS] += \
                    pool_stats['STATISTIC_SERVER_SIDE_TOTAL_CONNECTIONS']
                # are there members to update status
                if 'members' in service:
                    # only query BIG-IP pool members if they
                    # not in a state indicating provisioning or error
                    # provisioning the pool member
                    some_members_require_status_update = False
                    update_if_status = [plugin_const.ACTIVE,
                                        plugin_const.DOWN,
                                        plugin_const.INACTIVE]
                    if plugin_const.ACTIVE not in update_if_status:
                        update_if_status.append(plugin_const.ACTIVE)

                    for member in service['members']:
                        if member['status'] in update_if_status:
                            some_members_require_status_update = True
                    # are we have members who are in a
                    # state to update there status
                    if some_members_require_status_update:
                        # query pool members on each BIG-IP
                        monitor_states = \
                            hostbigip.pool.get_members_monitor_status(
                                name=pool['id'],
                                folder=pool['tenant_id'],
                                config_mode=self.conf.icontrol_config_mode
                            )
                        for member in service['members']:
                            if member['status'] in update_if_status:
                                # create the entry for this
                                # member in the return status
                                # dictionary set to ACTIVE
                                if not member['id'] in members:
                                    members[member['id']] = \
                                        {'status': plugin_const.INACTIVE}
                                # check if it down or up by monitor
                                # and update the status
                                for state in monitor_states:
                                    # matched the pool member
                                    # by address and port number
                                    if member['address'] == \
                                            strip_domain_address(
                                            state['addr']) and \
                                            int(member['protocol_port']) == \
                                            int(state['port']):
                                        # if the monitor says member is up
                                        if state['state'] == \
                                                'MONITOR_STATUS_UP' or \
                                           state['state'] == \
                                                'MONITOR_STATUS_UNCHECKED':
                                            # set ACTIVE as long as the
                                            # status was not set to 'DOWN'
                                            # on another BIG-IP
                                            if members[
                                                member['id']]['status'] != \
                                                    'DOWN':
                                                if member['admin_state_up']:
                                                    members[member['id']][
                                                        'status'] = \
                                                        plugin_const.ACTIVE
                                                else:
                                                    members[member['id']][
                                                        'status'] = \
                                                        plugin_const.INACTIVE
                                        else:
                                            members[member['id']]['status'] = \
                                                plugin_const.DOWN
        stats['members'] = members
        return stats

    @serialized('remove_orphans')
    def remove_orphans(self, all_pools):
        """Remove out-of-date configuration on big-ips """
        existing_tenants = []
        existing_pools = []
        for pool in all_pools:
            existing_tenants.append(pool['tenant_id'])
            existing_pools.append(pool['pool_id'])
        for bigip in self.get_all_bigips():
            bigip.pool.purge_orphaned_pools(existing_pools)
        for bigip in self.get_all_bigips():
            bigip.system.purge_orphaned_folders_contents(existing_tenants)

        sudslog = std_logging.getLogger('suds.client')
        sudslog.setLevel(std_logging.FATAL)
        for bigip in self.get_all_bigips():
            bigip.system.force_root_folder()
        sudslog.setLevel(std_logging.ERROR)

        for bigip in self.get_all_bigips():
            bigip.system.purge_orphaned_folders(existing_tenants)

    def fdb_add(self, fdb):
        """Add (L2toL3) forwarding database entries """
        self.remove_ips_from_fdb_update(fdb)
        for bigip in self.get_all_bigips():
            self.bigip_l2_manager.add_bigip_fdb(bigip, fdb)

    def fdb_remove(self, fdb):
        """Remove (L2toL3) forwarding database entries """
        self.remove_ips_from_fdb_update(fdb)
        for bigip in self.get_all_bigips():
            self.bigip_l2_manager.remove_bigip_fdb(bigip, fdb)

    def fdb_update(self, fdb):
        """Update (L2toL3) forwarding database entries """
        self.remove_ips_from_fdb_update(fdb)
        for bigip in self.get_all_bigips():
            self.bigip_l2_manager.update_bigip_fdb(bigip, fdb)

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
        """Tunnel Update from Neutron Core RPC """
        pass

    def tunnel_sync(self):
        """Advertise all bigip tunnel endpoints """
        # Only sync when supported types are present
        if not [i for i in self.agent_configurations['tunnel_types']
                if i in ['gre', 'vxlan']]:
            return

        tunnel_ips = []
        for bigip in self.get_all_bigips():
            if bigip.local_ip:
                tunnel_ips.append(bigip.local_ip)
        if self.fdb_connector:
            self.fdb_connector.advertise_tunnel_ips(tunnel_ips)

    @serialized('sync')
    @is_connected
    def sync(self, service):
        """Sync service defintion to device"""
        # plugin_rpc may not be set when unit testing
        if self.plugin_rpc:
            # Get the latest service. It may have changed.
            service = self.plugin_rpc.get_service_by_pool_id(
                service['pool']['id'],
                self.conf.f5_global_routed_mode
            )
        if service['pool']:
            self._common_service_handler(service)
        else:
            LOG.debug("Attempted sync of deleted pool")

    @serialized('backup_configuration')
    @is_connected
    def backup_configuration(self):
        """Save Configuration on Devices """
        for bigip in self.get_all_bigips():
            LOG.debug('_backup_configuration: saving device %s.'
                      % bigip.icontrol.hostname)
            bigip.cluster.save_config()

    def _service_exists(self, service):
        """Returns whether the bigip has a pool for the service """
        if not service['pool']:
            return False
        if self.lbaas_builder_bigiq_iapp:
            builder = self.lbaas_builder_bigiq_iapp
            readiness = builder.check_tenant_bigiq_readiness(service)
            use_bigiq = readiness['found_bigips']
        else:
            use_bigiq = False
        if use_bigiq:
            return self.lbaas_builder_bigiq_iapp.exists(service)
        else:
            bigip = self.get_bigip()
            return bigip.pool.exists(
                name=service['pool']['id'],
                folder=service['pool']['tenant_id'],
                config_mode=self.conf.icontrol_config_mode)

    def _common_service_handler(self, service):
        """Assure that the service is configured on bigip(s) """
        start_time = time()
        LOG.debug("    _common_service_handler took %.5f secs" %
                  (time() - start_time))

        if not 'loadbalancer' in service:
            LOG.error("Service handler called with incomplete "
                      "service: No loadbalancer")
            return
        self._update_service_status(service)

    def _update_service_status(self, service):
        """Update status of objects in OpenStack """
        if not self.plugin_rpc:
            LOG.error("Cannot update status in Neutron without "
                      "RPC handler.")
            return
            
        if 'members' in service:
            # Call update_members_status
            self._update_member_status(service['members'])
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
            # Call update_listner_status
            self._update_listener_status(
                service['listeners']
            )
        self._update_loadbalancer_status(
            service['loadbalancer']
        )
                                             
    def _update_members_status(self, members):
        """Update member status in OpenStack """
        pass

    def _update_pool_status(self, pool):
        """Update pool status in OpenStack """
        pass

    def _update_health_monitor_status(self, service):
        """Update pool monitor status in OpenStack """
        pass

    def _update_listener_status(self, listeners):
        """Update listener status in OpenStack """
        pass

    def _update_loadbalancer_status(self, loadbalancer):
        """Update loadbalancer status in OpenStack """
        status = plugin_const.ACTIVE
        operating_status = 'ONLINE'
        if (loadbalancer['provisioning_status'] ==
                plugin_const.PENDING_CREATE):
            self.plugin_rpc.update_loadbalancer_status(
                loadbalancer['id'],
                status,
                operating_status
            )
        elif (loadbalancer['provisioning_status'] ==
                  plugin_const.PENDING_DELETE):
            pass

    def _service_to_traffic_group(self, service):
        """Hash service tenant id to index of traffic group """
        pass

    def tenant_to_traffic_group(self, tenant_id):
        """Hash tenant id to index of traffic group """
        pass

    def get_bigip(self):
        """Get one consistent big-ip """
        pass

    def get_bigip_hosts(self):
        """Get all big-ips hostnames under management """
        return self.__bigips

    def get_all_bigips(self):
        """Get all big-ips under management """
        # return self.__bigips.values()
        pass

    def get_config_bigips(self):
        # Return a list of big-ips that need to be configured.
        # In replication sync mode, we configure all big-ips
        # individually. In autosync mode we only use one big-ip
        # and then sync the configuration to the other big-ips.

        pass

    def get_inbound_throughput(self, bigip, global_statistics=None):
        pass

    def get_outbound_throughput(self, bigip, global_statistics=None):
        pass

    def get_throughput(self, bigip=None, global_statistics=None):
        pass

    def get_active_connections(self, bigip=None, global_statistics=None):
        pass

    def get_ssltps(self, bigip=None, global_statistics=None):
        pass

    def get_node_count(self, bigip=None, global_statistics=None):
        pass

    def get_clientssl_profile_count(self, bigip=None, global_statistics=None):
        pass

    def get_tenant_count(self, bigip=None, global_statistics=None):
        pass

    def get_tunnel_count(self, bigip=None, global_statistics=None):
        pass

    def get_vlan_count(self, bigip=None, global_statistics=None):
        pass

    def get_route_domain_count(self, bigip=None, global_statistics=None):
        pass

    def _init_traffic_groups(self, bigip):
        pass

    def sync_if_clustered(self):
        """sync device group if not in replication mode """
        pass

    def _sync_with_retries(self, bigip, force_now=False,
                           attempts=4, retry_delay=130):
        """sync device group """
        pass


def _validate_bigip_version(bigip, hostname):
    """Ensure the BIG-IP has sufficient version """
    major_version = "12"
    minor_version = "0"
    return major_version, minor_version
