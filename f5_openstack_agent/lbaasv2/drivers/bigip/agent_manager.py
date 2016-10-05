"""Agent manager to handle plugin to agent RPC and periodic tasks."""
# coding=utf-8
# Copyright 2016 F5 Networks Inc.
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
import uuid

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
import oslo_messaging
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_utils import importutils

from neutron.agent import rpc as agent_rpc
from neutron.common import constants as plugin_const
from neutron.common import exceptions as q_exception
from neutron.common import topics
from neutron import context as ncontext
from neutron.plugins.ml2.drivers.l2pop import rpc as l2pop_rpc
from neutron_lbaas.services.loadbalancer import constants as lb_const

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import plugin_rpc


LOG = logging.getLogger(__name__)

# XXX OPTS is used in (at least) agent.py Maybe move/rename to agent.py
OPTS = [
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
        default=300,
        help=('Number of seconds between service refresh checks')
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
]


class LogicalServiceCache(object):
    """Manage a cache of known services."""

    class Service(object):  # XXX maybe promote/use this class elsewhere?
        """Inner classes used to hold values for weakref lookups."""

        def __init__(self, port_id, loadbalancer_id, tenant_id, agent_host):
            self.port_id = port_id
            self.loadbalancer_id = loadbalancer_id
            self.tenant_id = tenant_id
            self.agent_host = agent_host

        def __eq__(self, other):
            return self.__dict__ == other.__dict__

        def __hash__(self):
            return hash(
                (self.port_id,
                 self.loadbalancer_id,
                 self.tenant_id,
                 self.agent_host)
            )

    def __init__(self):
        """Initialize Service cache object."""
        LOG.debug("Initializing LogicalServiceCache")
        self.services = {}

    @property
    def size(self):
        """Return the number of services cached."""
        return len(self.services)

    def put(self, service, agent_host):
        """Add a service to the cache."""
        if 'port_id' in service['loadbalancer']:
            port_id = service['loadbalancer']['port_id']
        else:
            port_id = None
        loadbalancer_id = service['loadbalancer']['id']
        tenant_id = service['loadbalancer']['tenant_id']
        if loadbalancer_id not in self.services:
            s = self.Service(port_id, loadbalancer_id, tenant_id, agent_host)
            self.services[loadbalancer_id] = s
        else:
            s = self.services[loadbalancer_id]
            s.tenant_id = tenant_id
            s.port_id = port_id
            s.agent_host = agent_host

    def remove(self, service):
        """Remove a service from the cache."""
        if not isinstance(service, self.Service):
            loadbalancer_id = service['loadbalancer']['id']
        else:
            loadbalancer_id = service.loadbalancer_id
        if loadbalancer_id in self.services:
            del(self.services[loadbalancer_id])

    def remove_by_loadbalancer_id(self, loadbalancer_id):
        """Remove service by providing the loadbalancer id."""
        if loadbalancer_id in self.services:
            del(self.services[loadbalancer_id])

    def get_by_loadbalancer_id(self, loadbalancer_id):
        """Retreive service by providing the loadbalancer id."""
        if loadbalancer_id in self.services:
            return self.services[loadbalancer_id]
        else:
            return None

    def get_loadbalancer_ids(self):
        """Return a list of cached loadbalancer ids."""
        return self.services.keys()

    def get_tenant_ids(self):
        """Return a list of tenant ids in the service cache."""
        tenant_ids = {}
        for service in self.services:
            tenant_ids[service.tenant_id] = 1
        return tenant_ids.keys()

    def get_agent_hosts(self):
        """Return a list of agent ids stored in the service cache."""
        agent_hosts = {}
        for service in self.services:
            agent_hosts[service.agent_host] = 1
        return agent_hosts.keys()


class LbaasAgentManager(periodic_task.PeriodicTasks):  # b --> B
    """Periodic task that is an endpoint for plugin to agent RPC."""

    RPC_API_VERSION = '1.0'

    target = oslo_messaging.Target(version='1.0')

    def __init__(self, conf):
        """Initialize LbaasAgentManager."""
        super(LbaasAgentManager, self).__init__(conf)
        LOG.debug("Initializing LbaasAgentManager")

        self.conf = conf
        self.context = ncontext.get_admin_context_without_session()
        self.serializer = None

        # Create the cache of provisioned services
        self.cache = LogicalServiceCache()
        self.last_resync = datetime.datetime.now()
        self.needs_resync = False
        self.plugin_rpc = None

        self.service_resync_interval = conf.service_resync_interval
        LOG.debug('setting service resync intervl to %d seconds' %
                  self.service_resync_interval)

        # Set the agent ID
        if self.conf.agent_id:
            self.agent_host = self.conf.agent_id
            LOG.debug('setting agent host to %s' % self.agent_host)
        else:
            self.agent_host = conf.host

        # Load the iControl® driver.
        self._load_driver(conf)

        # Initialize agent configurations
        agent_configurations = (
            {'environment_prefix': self.conf.environment_prefix,
             'environment_group_number': self.conf.environment_group_number,
             'global_routed_mode': self.conf.f5_global_routed_mode}
        )
        if self.conf.static_agent_configuration_data:
            entries = str(self.conf.static_agent_configuration_data).split(',')
            for entry in entries:
                nv = entry.strip().split(':')
                if len(nv) > 1:
                    agent_configurations[nv[0]] = nv[1]

        # Initialize agent-state
        self.agent_state = {
            'binary': constants_v2.AGENT_BINARY_NAME,
            'host': self.agent_host,
            'topic': constants_v2.TOPIC_LOADBALANCER_AGENT_V2,
            'configurations': agent_configurations,
            'agent_type': lb_const.AGENT_TYPE_LOADBALANCERV2,
            'l2_population': self.conf.l2_population,
            'start_flag': True
        }

        self.admin_state_up = True

        # Set iControl® driver context for RPC.
        self.lbdriver.set_context(self.context)

        # Setup RPC:
        self._setup_rpc()

        # Allow driver to run post init process not that the RPC is all setup.
        self.lbdriver.post_init()

        # Set the flag to resync tunnels/services
        self.needs_resync = True

    def _load_driver(self, conf):
        self.lbdriver = None

        LOG.debug('loading LBaaS driver %s' %
                  conf.f5_bigip_lbaas_device_driver)
        try:
            self.lbdriver = importutils.import_object(
                conf.f5_bigip_lbaas_device_driver,
                self.conf)

            if self.lbdriver.initialized:
                if not self.conf.agent_id:
                    # If not set statically, add the driver agent env hash
                    agent_hash = str(
                        uuid.uuid5(uuid.NAMESPACE_DNS,
                                   self.conf.environment_prefix +
                                   '.' + self.lbdriver.hostnames[0])
                    )
                    self.agent_host = conf.host + ":" + agent_hash
                    LOG.debug('setting agent host to %s' % self.agent_host)
            else:
                LOG.error('Driver did not initialize. Fix the driver config '
                          'and restart the agent.')
                return
        except ImportError as ie:
            msg = ('Error importing loadbalancer device driver: %s error %s'
                   % (conf.f5_bigip_lbaas_device_driver, repr(ie)))
            LOG.error(msg)
            raise SystemExit(msg)

    def _setup_rpc(self):

        # LBaaS Plugin API
        topic = constants_v2.TOPIC_PROCESS_ON_HOST_V2
        if self.conf.environment_specific_plugin:
            topic = topic + '_' + self.conf.environment_prefix
            LOG.debug('agent in %s environment will send callbacks to %s'
                      % (self.conf.environment_prefix, topic))
        self.plugin_rpc = plugin_rpc.LBaaSv2PluginRPC(
            topic,
            self.context,
            self.conf.environment_prefix,
            self.conf.environment_group_number,
            self.agent_host
        )

        # Allow driver to make callbacks using the
        # same RPC proxy as the manager
        self.lbdriver.set_plugin_rpc(self.plugin_rpc)

        self._setup_state_rpc(topic)

        # Setup message queues to listen for updates from
        # Neutron.
        if not self.conf.f5_global_routed_mode:
            # Core plugin
            self.lbdriver.set_tunnel_rpc(agent_rpc.PluginApi(topics.PLUGIN))

            consumers = [[constants_v2.TUNNEL, topics.UPDATE]]
            if self.conf.l2_population:
                # L2 Populate plugin Callbacks API
                self.lbdriver.set_l2pop_rpc(
                    l2pop_rpc.L2populationAgentNotifyAPI())

                consumers.append(
                    [topics.L2POPULATION, topics.UPDATE, self.agent_host]
                )

            self.endpoints = [self]

            self.connection = agent_rpc.create_consumers(
                self.endpoints,
                topics.AGENT,
                consumers
            )

    def _setup_state_rpc(self, topic):
        # Agent state API
        self.state_rpc = agent_rpc.PluginReportStateAPI(topic)
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)

    def _report_state(self):

        try:
            # assure the agent is connected
            # FIXME: what happens if we can't connect.
            if not self.lbdriver.connected:
                self.lbdriver.connect()

            service_count = self.cache.size
            self.agent_state['configurations']['services'] = service_count
            if hasattr(self.lbdriver, 'service_queue'):
                self.agent_state['configurations']['request_queue_depth'] = (
                    len(self.lbdriver.service_queue)
                )

            # Add configuration from icontrol_driver.
            if self.lbdriver.agent_configurations:
                self.agent_state['configurations'].update(
                    self.lbdriver.agent_configurations
                )

            # Compute the capacity score.
            if self.conf.capacity_policy:
                env_score = (
                    self.lbdriver.generate_capacity_score(
                        self.conf.capacity_policy
                    )
                )
                self.agent_state['configurations'][
                    'environment_capaciy_score'] = env_score
            else:
                self.agent_state['configurations'][
                    'environment_capacity_score'] = 0

            LOG.debug("reporting state of agent as: %s" % self.agent_state)
            self.state_rpc.report_state(self.context, self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception as e:
            LOG.exception(("Failed to report state: " + str(e.message)))

    def initialize_service_hook(self, started_by):
        """Create service hook to listen for messanges on agent topic."""
        node_topic = "%s_%s.%s" % (constants_v2.TOPIC_LOADBALANCER_AGENT_V2,
                                   self.conf.environment_prefix,
                                   self.agent_host)
        LOG.debug("Creating topic for consuming messages: %s" % node_topic)
        endpoints = [started_by.manager]
        started_by.conn.create_consumer(
            node_topic, endpoints, fanout=False)

    @periodic_task.periodic_task
    def periodic_resync(self, context):
        """Resync tunnels/service state."""
        LOG.debug("tunnel_sync: periodic_resync called")
        now = datetime.datetime.now()
        # Only force resync if the agent thinks it is
        # synchronized and the resync timer has exired
        if (now - self.last_resync).seconds > self.service_resync_interval:
            if not self.needs_resync:
                self.needs_resync = True
                LOG.debug(
                    'Forcing resync of services on resync timer (%d seconds).'
                    % self.service_resync_interval)
                self.cache.services = {}
                self.last_resync = now
                self.lbdriver.flush_cache()
            LOG.debug("tunnel_sync: periodic_resync need_resync: %s"
                      % str(self.needs_resync))
        # resync if we need to
        if self.needs_resync:
            self.needs_resync = False
            if self.tunnel_sync():
                self.needs_resync = True
            if self.sync_state():
                self.needs_resync = True
        else:
            # Resync the next time around.
            self.needs_resync = True

    def tunnel_sync(self):
        """Call into driver to advertise tunnels."""
        LOG.debug("manager:tunnel_sync: calling driver tunnel_sync")
        return self.lbdriver.tunnel_sync()

    @log_helpers.log_method_call
    def sync_state(self):
        """Sync state of BIG-IP with that of the neutron database."""
        resync = False

        known_services = set()
        owned_services = set()
        for lb_id, service in self.cache.services.iteritems():
            known_services.add(lb_id)
            if self.agent_host == service.agent_host:
                owned_services.add(lb_id)

        try:
            # Get loadbalancers from the environment which are bound to
            # this agent.
            active_loadbalancers = (
                self.plugin_rpc.get_active_loadbalancers(host=self.agent_host)
            )
            active_loadbalancer_ids = set(
                [lb['lb_id'] for lb in active_loadbalancers]
            )

            all_loadbalancers = (
                self.plugin_rpc.get_all_loadbalancers(host=self.agent_host)
            )
            all_loadbalancer_ids = set(
                [lb['lb_id'] for lb in all_loadbalancers]
            )

            LOG.debug("plugin produced the list of active loadbalancer ids: %s"
                      % list(active_loadbalancer_ids))
            LOG.debug("currently known loadbalancer ids before sync are: %s"
                      % list(known_services))

            # Remove services that are in Neutron, but no longer managed
            # by this agent.
            for deleted_lb in owned_services - all_loadbalancer_ids:
                LOG.error("Cached service not found in neutron database")
                # TODO(Rich Browne) -- This can't be implemented with the
                # normal tear down b/c the RPC destroy methods walk all
                # over one another.  Although this case suggests that the
                # database lacks the service definitition, there could be
                # some service objects (pools, listeners, etc.) that need
                # to be removed from the database
                # self.destroy_service(deleted_lb)

            # Validate each service we own, i.e. loadbalancers to which this
            # agent is bound, that does not exist in our service cache.
            for lb_id in active_loadbalancer_ids:
                if not self.cache.get_by_loadbalancer_id(lb_id):
                    self.validate_service(lb_id)

            # This produces a list of loadbalancers with pending tasks to
            # be performed.
            pending_loadbalancers = (
                self.plugin_rpc.get_pending_loadbalancers(host=self.agent_host)
            )
            pending_lb_ids = set(
                [lb['lb_id'] for lb in pending_loadbalancers]
            )
            LOG.debug(
                "plugin produced the list of pending loadbalancer ids: %s"
                % list(pending_lb_ids))

            for lb_id in pending_lb_ids:
                self.refresh_service(lb_id)

            # Get a list of any cached service we now know after
            # refreshing services
            known_services = set()
            for (lb_id, service) in self.cache.services.iteritems():
                if self.agent_host == service.agent_host:
                    known_services.add(lb_id)
            LOG.debug("currently known loadbalancer ids after sync: %s"
                      % list(known_services))

        except Exception as e:
            LOG.error("Unable to retrieve ready service: %s" % e.message)
            resync = True

        return resync

    @log_helpers.log_method_call
    def validate_service(self, lb_id):

        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            if not self.lbdriver.exists(service):
                LOG.error('active loadbalancer %s is not on BIG-IP...syncing'
                          % lb_id)
                self.lbdriver.sync(service)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception:
            LOG.error("Exception caught: validate_service, unable to validate",
                      " service for loadbalancer: %s" % lb_id)

    @log_helpers.log_method_call
    def refresh_service(self, lb_id):

        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            self.lbdriver.sync(service)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as e:
            LOG.error("Exception: %s" % e.message)
            self.needs_resync = True

    @log_helpers.log_method_call
    def destroy_service(self, lb_id):
        """Remove the service from BIG-IP and the neutron database."""
        service = self.plugin_rpc.get_service_by_loadbalancer_id(
            lb_id
        )
        if not service:
            return

        # Force removal of this loadbalancer.
        service['loadbalancer']['provisioning_status'] = (
            plugin_const.PENDING_DELETE
        )
        try:
            self.lbdriver.delete_loadbalancer(lb_id, service)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)
            self.needs_resync = True
        self.cache.remove_by_loadbalancer_id(lb_id)

    @log_helpers.log_method_call
    def remove_orphans(self, all_loadbalancers):

        try:
            self.lbdriver.remove_orphans(all_loadbalancers)
        except Exception as exc:
            LOG.error("Exception: removing orphans: %s" % exc.message)

    @log_helpers.log_method_call
    def create_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to create_loadbalancer."""
        try:
            self.lbdriver.create_loadbalancer(loadbalancer, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_loadbalancer(self, context, old_loadbalancer,
                            loadbalancer, service):
        """Handle RPC cast from plugin to update_loadbalancer."""
        try:
            self.lbdriver.update_loadbalancer(old_loadbalancer,
                                              loadbalancer, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to delete_loadbalancer."""
        try:
            self.lbdriver.delete_loadbalancer(loadbalancer, service)
            self.cache.remove_by_loadbalancer_id(loadbalancer['id'])
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_listener(self, context, listener, service):
        """Handle RPC cast from plugin to create_listener."""
        try:
            self.lbdriver.create_listener(listener, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_listener(self, context, old_listener, listener, service):
        """Handle RPC cast from plugin to update_listener."""
        try:
            self.lbdriver.update_listener(old_listener, listener, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_listener(self, context, listener, service):
        """Handle RPC cast from plugin to delete_listener."""
        try:
            self.lbdriver.delete_listener(listener, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("delete_listener: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_listener: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_pool(self, context, pool, service):
        """Handle RPC cast from plugin to create_pool."""
        try:
            self.lbdriver.create_pool(pool, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_pool(self, context, old_pool, pool, service):
        """Handle RPC cast from plugin to update_pool."""
        try:
            self.lbdriver.update_pool(old_pool, pool, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_pool(self, context, pool, service):
        """Handle RPC cast from plugin to delete_pool."""
        try:
            self.lbdriver.delete_pool(pool, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("delete_pool: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_pool: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_member(self, context, member, service):
        """Handle RPC cast from plugin to create_member."""
        try:
            self.lbdriver.create_member(member, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("create_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("create_member: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_member(self, context, old_member, member, service):
        """Handle RPC cast from plugin to update_member."""
        try:
            self.lbdriver.update_member(old_member, member, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("update_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_member: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_member(self, context, member, service):
        """Handle RPC cast from plugin to delete_member."""
        try:
            self.lbdriver.delete_member(member, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("delete_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_member: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to create_pool_health_monitor."""
        try:
            self.lbdriver.create_health_monitor(health_monitor, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("create_pool_health_monitor: NeutronException: %s"
                      % exc.msg)
        except Exception as exc:
            LOG.error("create_pool_health_monitor: Exception: %s"
                      % exc.message)

    @log_helpers.log_method_call
    def update_health_monitor(self, context, old_health_monitor,
                              health_monitor, service):
        """Handle RPC cast from plugin to update_health_monitor."""
        try:
            self.lbdriver.update_health_monitor(old_health_monitor,
                                                health_monitor,
                                                service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("update_health_monitor: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_health_monitor: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to delete_health_monitor."""
        try:
            self.lbdriver.delete_health_monitor(health_monitor, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("delete_health_monitor: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_health_monitor: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        if payload['admin_state_up'] != self.admin_state_up:
            self.admin_state_up = payload['admin_state_up']
            if self.admin_state_up:
                # FIXME: This needs to be changed back to True
                self.needs_resync = False
            else:
                for loadbalancer_id in self.cache.get_loadbalancer_ids():
                    LOG.debug("DESTROYING loadbalancer: " + loadbalancer_id)
                    # self.destroy_service(loadbalancer_id)
            LOG.info("agent_updated by server side %s!", payload)

    @log_helpers.log_method_call
    def tunnel_update(self, context, **kwargs):
        """Handle RPC cast from core to update tunnel definitions."""
        try:
            LOG.debug('received tunnel_update: %s' % kwargs)
            self.lbdriver.tunnel_update(**kwargs)
        except q_exception.NeutronException as exc:
            LOG.error("tunnel_update: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("tunnel_update: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def add_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions."""
        try:
            LOG.debug('received add_fdb_entries: %s host: %s'
                      % (fdb_entries, host))
            self.lbdriver.fdb_add(fdb_entries)
        except q_exception.NeutronException as exc:
            LOG.error("fdb_add: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("fdb_add: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def remove_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions."""
        try:
            LOG.debug('received remove_fdb_entries: %s host: %s'
                      % (fdb_entries, host))
            self.lbdriver.fdb_remove(fdb_entries)
        except q_exception.NeutronException as exc:
            LOG.error("remove_fdb_entries: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("remove_fdb_entries: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions."""
        try:
            LOG.debug('received update_fdb_entries: %s host: %s'
                      % (fdb_entries, host))
            self.lbdriver.fdb_update(fdb_entries)
        except q_exception.NeutronException as exc:
            LOG.error("update_fdb_entrie: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_fdb_entrie: Exception: %s" % exc.message)
