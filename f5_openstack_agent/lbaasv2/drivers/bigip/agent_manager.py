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
from neutron.common import topics
from neutron import context as ncontext
from neutron.plugins.ml2.drivers.l2pop import rpc as l2pop_rpc
from neutron_lbaas.services.loadbalancer import constants as lb_const
from neutron_lib import constants as plugin_const
from neutron_lib import exceptions as q_exception

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import plugin_rpc


LOG = logging.getLogger(__name__)

# XXX OPTS is used in (at least) agent.py Maybe move/rename to agent.py
OPTS = [
    cfg.IntOpt(
        'periodic_interval',
        default=10,
        help='Seconds between periodic task runs'
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
    cfg.IntOpt(
        'f5_pending_services_timeout',
        default=60,
        help=(
            'Amount of time to wait for a pending service to become active')
    ),
]

PERIODIC_TASK_INTERVAL = 10


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
        port_id = service['loadbalancer'].get('vip_port_id', None)
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
        return self.services.get(loadbalancer_id, None)

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

        global PERIODIC_TASK_INTERVAL
        PERIODIC_TASK_INTERVAL = self.conf.periodic_interval

        # Create the cache of provisioned services
        self.cache = LogicalServiceCache()
        self.last_resync = datetime.datetime.now()
        self.needs_resync = False
        self.plugin_rpc = None
        self.pending_services = {}

        self.service_resync_interval = conf.service_resync_interval
        LOG.debug('setting service resync intervl to %d seconds' %
                  self.service_resync_interval)

        # Set the agent ID
        if self.conf.agent_id:
            self.agent_host = self.conf.agent_id
            LOG.debug('setting agent host to %s' % self.agent_host)
        else:
            # If not set statically, add the driver agent env hash
            agent_hash = str(
                uuid.uuid5(uuid.NAMESPACE_DNS,
                           self.conf.environment_prefix +
                           '.' + self.lbdriver.hostnames[0])
                )
            self.agent_host = conf.host + ":" + agent_hash
            LOG.debug('setting agent host to %s' % self.agent_host)

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

        # Initialize agent-state to a default values
        self.admin_state_up = self.conf.start_agent_admin_state_up

        self.agent_state = {
            'binary': constants_v2.AGENT_BINARY_NAME,
            'host': self.agent_host,
            'topic': constants_v2.TOPIC_LOADBALANCER_AGENT_V2,
            'configurations': agent_configurations,
            'agent_type': lb_const.AGENT_TYPE_LOADBALANCERV2,
            'l2_population': self.conf.l2_population,
            'start_flag': True
        }

        # Load the driver.
        self._load_driver(conf)

        # Allow the driver to force the agent to
        # report state if something happens requring
        # the agent to show an error message in configuration
        # and set the admin_state_up to False so no further
        # scheduling will take place on this agent
        self.lbdriver.agent_report_state = self._report_state

        # Set driver context for RPC.
        self.lbdriver.set_context(self.context)

        # Setup RPC for communications to controller
        self._setup_rpc()

        # Allow driver to run post init process not that the RPC is all setup.
        self.lbdriver.post_init()

        # Set the flag to resync tunnels/services
        self.needs_resync = True

        if(self.admin_state_up):
            self.plugin_rpc.set_agent_admin_state(self.admin_state_up)

    def _load_driver(self, conf):
        self.lbdriver = None

        LOG.debug('loading LBaaS driver %s' %
                  conf.f5_bigip_lbaas_device_driver)
        try:
            self.lbdriver = importutils.import_object(
                conf.f5_bigip_lbaas_device_driver,
                self.conf)
            return
        except ImportError as ie:
            msg = ('Error importing loadbalancer device driver: %s error %s'
                   % (conf.f5_bigip_lbaas_device_driver, repr(ie)))
            LOG.error(msg)
            raise SystemExit(msg)

    def _setup_rpc(self):

        #
        # Setting up outbound (callbacks) communications from agent
        #

        # setup the topic to send oslo messages RPC calls
        # from this agent to the controller
        topic = constants_v2.TOPIC_PROCESS_ON_HOST_V2
        if self.conf.environment_specific_plugin:
            topic = topic + '_' + self.conf.environment_prefix
            LOG.debug('agent in %s environment will send callbacks to %s'
                      % (self.conf.environment_prefix, topic))

        # create our class we will use to send callbacks to the controller
        # for processing by the driver plugin
        self.plugin_rpc = plugin_rpc.LBaaSv2PluginRPC(
            topic,
            self.context,
            self.conf.environment_prefix,
            self.conf.environment_group_number,
            self.agent_host
        )

        # Allow driver to make direct callbacks not proxy
        # through this manager
        self.lbdriver.set_plugin_rpc(self.plugin_rpc)

        #
        # Setting up outbound communcations with the neutron agent extension
        #
        self._setup_state_rpc(topic)

        #
        # Setting up all inbound notifications and outbound callbacks
        # for standard neutron agent services:
        #
        #     tunnel_sync - used to advertise the driver VTEP endpoints
        #                   and optionally learn about other VTEP endpoints
        #
        #     update - used to get updates to agent state triggered by
        #              the controller, like setting admin_state_up
        #              the agent
        #
        #     l2_populateion - used to get updates on neturon SDN topology
        #                      changes
        #
        #  We only establish notification if we care about L2/L3 updates
        #

        if not self.conf.f5_global_routed_mode:

            # allow the driver to issue notifications of
            # topology change to the controller
            self.lbdriver.set_tunnel_rpc(agent_rpc.PluginApi(topics.PLUGIN))

            # define which controler notifications the agent comsumes
            consumers = [[constants_v2.TUNNEL, topics.UPDATE]]

            # if we are dynamically changing tunnel peers,
            # register to recieve and send notificatoins via RPC
            if self.conf.l2_population:
                # communications of notifications from the
                # driver to neutron for SDN topology changes
                self.lbdriver.set_l2pop_rpc(
                    l2pop_rpc.L2populationAgentNotifyAPI())

                # notification of SDN topology updates from the
                # controller by adding to the general consumer list
                consumers.append(
                    [topics.L2POPULATION, topics.UPDATE, self.agent_host]
                )

            # kick off the whole RPC process by creating
            # a connection to the message bus
            self.endpoints = [self]
            self.connection = agent_rpc.create_consumers(
                self.endpoints,
                topics.AGENT,
                consumers
            )

    def _setup_state_rpc(self, topic):
        # notify the controller (agent extension) of
        # agent state on a period basis using oslo services
        self.state_rpc = agent_rpc.PluginReportStateAPI(topic)
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)

    def _report_state(self, force_resync=False):

        try:
            if force_resync:
                self.needs_resync = True
                self.cache.services = {}
                self.lbdriver.flush_cache()
            # use the admin_state_up to notify the
            # controller if all backend devices
            # are functioning properly. If not
            # automatically set the admin_state_up
            # for this agent to False
            if not self.lbdriver.backend_integrity():
                self.needs_resync = True
                self.cache.services = {}
                self.last_resync = datetime.datetime.now()
                self.lbdriver.flush_cache()
                self.plugin_rpc.set_agent_admin_state(False)
                self.admin_state_up = False
            else:
                # if we are transitioning from down to up,
                # change the controller state for this agent
                if not self.admin_state_up:
                    self.plugin_rpc.set_agent_admin_state(True)
                    self.admin_state_up = True

            # allow the service cache size to be monitored from neutron
            service_count = self.cache.size
            self.agent_state['configurations']['services'] = service_count

            # add the agent configurations from driver.
            if self.lbdriver.agent_configurations:
                self.agent_state['configurations'].update(
                    self.lbdriver.get_agent_configurations()
                )

            # add the capacity score, used by the scheduler
            # for horizontal scaling of an environment, from
            # the driver
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

    # callback from oslo messaging letting us know we are properly
    # connected to the message bus so we can register for inbound
    # messages to this agent
    def initialize_service_hook(self, started_by):
        """Create service hook to listen for messanges on agent topic."""
        node_topic = "%s_%s.%s" % (constants_v2.TOPIC_LOADBALANCER_AGENT_V2,
                                   self.conf.environment_prefix,
                                   self.agent_host)
        LOG.debug("Creating topic for consuming messages: %s" % node_topic)
        endpoints = [started_by.manager]
        started_by.conn.create_consumer(
            node_topic, endpoints, fanout=False)
        self.sync_state()

    # setup a period task to decide if it is time empty the local service
    # cache and resync service definitions form the controller
    @periodic_task.periodic_task(spacing=PERIODIC_TASK_INTERVAL)
    def periodic_resync(self, context):
        """Determine if it is time to resync services from controller."""
        now = datetime.datetime.now()
        LOG.debug("%s: periodic_resync called." % now)

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
            LOG.debug("periodic_sync: service_resync_interval expired: %s"
                      % str(self.needs_resync))
        # resync if we need to
        if self.needs_resync:
            self.needs_resync = False
            if self.tunnel_sync():
                self.needs_resync = True
            if self.sync_state():
                self.needs_resync = True

    @periodic_task.periodic_task(
        spacing=constants_v2.UPDATE_OPERATING_STATUS_INTERVAL)
    def update_operating_status(self, context):
        """Update pool member operational status from devices to controller."""
        if not self.plugin_rpc:
            return

        active_loadbalancers = \
            self.plugin_rpc.get_active_loadbalancers(host=self.agent_host)
        for loadbalancer in active_loadbalancers:
            if self.agent_host == loadbalancer['agent_host']:
                try:
                    lb_id = loadbalancer['lb_id']
                    LOG.debug(
                        'getting operating status for loadbalancer %s.', lb_id)
                    svc = self.plugin_rpc.get_service_by_loadbalancer_id(
                        lb_id)
                    self.lbdriver.update_operating_status(svc)

                except Exception as e:
                    LOG.exception('Error updating status %s.', e.message)

    @periodic_task.periodic_task(
        spacing=constants_v2.UPDATE_OPERATING_STATUS_INTERVAL)
    def scrub_dead_agents_in_env_and_group(self, context):
        """Triggering a dead agent scrub on the controller."""
        LOG.debug("running periodic scrub_dead_agents_in_env_and_group")
        self.plugin_rpc.scrub_dead_agents(self.conf.environment_prefix,
                                          self.conf.environment_group_number)

    @periodic_task.periodic_task(spacing=PERIODIC_TASK_INTERVAL)
    def recover_errored_devices(self, context):
        """Try to reconnect to errored devices."""
        LOG.debug("running periodic task to retry errored devices")
        self.lbdriver.recover_errored_devices()

    def tunnel_sync(self):
        """Call into driver to advertise device tunnel endpoints."""
        LOG.debug("manager:tunnel_sync: calling driver tunnel_sync")
        return self.lbdriver.tunnel_sync()

    @log_helpers.log_method_call
    def sync_state(self):
        """Synchronize device configuration from controller state."""
        resync = False

        known_services = set()
        owned_services = set()
        for lb_id, service in self.cache.services.iteritems():
            known_services.add(lb_id)
            if self.agent_host == service.agent_host:
                owned_services.add(lb_id)
        now = datetime.datetime.now()

        try:
            # Trigger a culling of all dead agents
            self.plugin_rpc.scrub_dead_agents(
                self.conf.environment_prefix,
                self.conf.environment_group_number
            )
            # Get loadbalancers from the environment which are bound to
            # this agent.
            active_loadbalancers = (
                self.plugin_rpc.get_active_loadbalancers(host=self.agent_host)
            )
            active_loadbalancer_ids = set(
                [lb['lb_id'] for lb in active_loadbalancers]
            )

            LOG.debug("plugin produced the list of active loadbalancer ids: %s"
                      % list(active_loadbalancer_ids))
            LOG.debug("currently known loadbalancer ids before sync are: %s"
                      % list(known_services))

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
                lb_pending = self.refresh_service(lb_id)
                if lb_pending:
                    if lb_id not in self.pending_services:
                        self.pending_services[lb_id] = now

                    time_added = self.pending_services[lb_id]
                    time_expired = ((now - time_added).seconds >
                                    self.conf.f5_pending_services_timeout)

                    if time_expired:
                        lb_pending = False
                        self.service_timeout(lb_id)

                if not lb_pending:
                    del self.pending_services[lb_id]

            # If there are services in the pending cache resync
            if self.pending_services:
                resync = True

            # Get a list of any cached service we now know after
            # refreshing services
            known_services = set()
            for (lb_id, service) in self.cache.services.iteritems():
                if self.agent_host == service.agent_host:
                    known_services.add(lb_id)
            LOG.debug("currently known loadbalancer ids after sync: %s"
                      % list(known_services))

            #
            # Global cluster refresh tasks
            #

            global_agent = self.plugin_rpc.get_clusterwide_agent(
                self.conf.environment_prefix,
                self.conf.environment_group_number
            )

            if global_agent and global_agent['host'] == self.agent_host:
                LOG.debug('this agent is the global config agent')
                # We're the global agent perform global cluster tasks

                # Query BIG-IPs for tenant folders and load balancers in
                # each tenant. Query neutron for all discovered loadbalancer's
                # state. If they are 'Unknown' state, meaning Neutron could
                # not find it, delete it.
                lbs = self.lbdriver.get_all_deployed_loadbalancers(
                    purge_orphaned_folders=True)
                if lbs:
                    lbs_status = self.plugin_rpc.validate_loadbalancers_state(
                        list(lbs.keys()))
                    for lbid in lbs_status:
                        if lbs_status[lbid] in ['Unknown']:
                            self.lbdriver.purge_orphaned_loadbalancer(
                                tenant_id=lbs[lbid]['tenant_id'],
                                loadbalancer=lbid)
            else:
                LOG.debug('the global agent is %s' % (global_agent['host']))
            # serialize config and save to disk
            self.lbdriver.backup_configuration()

        except Exception as e:
            LOG.error("Unable to sync state: %s" % e.message)
            resync = True

        return resync

    @log_helpers.log_method_call
    def validate_service(self, lb_id):

        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            if not self.lbdriver.service_exists(service):
                LOG.error('active loadbalancer %s is not on BIG-IP...syncing'
                          % lb_id)

                if self.lbdriver.service_rename_required(service):
                    self.lbdriver.service_object_teardown(service)
                    LOG.error('active loadbalancer %s is configured with '
                              'non-unique names on BIG-IP...rename in '
                              'progress.'
                              % lb_id)
                    LOG.error('removing the service objects that are '
                              'incorrectly named')
                else:
                    LOG.debug('service rename not required')

                self.lbdriver.sync(service)
            else:
                LOG.debug("Found service definition for %s" % (lb_id))
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.exception("Service validation error: %s" % exc.message)

    @log_helpers.log_method_call
    def refresh_service(self, lb_id):
        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            if self.lbdriver.sync(service):
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as e:
            LOG.error("Exception: %s" % e.message)
            self.needs_resync = True

        return self.needs_resync

    @log_helpers.log_method_call
    def service_timeout(self, lb_id):
        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            self.lbdriver.update_service_status(service, timed_out=True)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as e:
            LOG.error("Exception: %s" % e.message)

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

    ######################################################################
    #
    # handlers for all in bound requests and notifications from controller
    #
    ######################################################################

    @log_helpers.log_method_call
    def create_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to create_loadbalancer."""
        try:
            service_pending = \
                self.lbdriver.create_loadbalancer(loadbalancer,
                                                  service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True

        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_loadbalancer(self, context, old_loadbalancer,
                            loadbalancer, service):
        """Handle RPC cast from plugin to update_loadbalancer."""
        try:
            service_pending = self.lbdriver.update_loadbalancer(
                old_loadbalancer,
                loadbalancer, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to delete_loadbalancer."""
        try:
            service_pending = \
                self.lbdriver.delete_loadbalancer(loadbalancer, service)
            self.cache.remove_by_loadbalancer_id(loadbalancer['id'])
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_loadbalancer_stats(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to get stats."""
        try:
            self.lbdriver.get_stats(service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_listener(self, context, listener, service):
        """Handle RPC cast from plugin to create_listener."""
        try:
            service_pending = \
                self.lbdriver.create_listener(listener, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_listener(self, context, old_listener, listener, service):
        """Handle RPC cast from plugin to update_listener."""
        try:
            service_pending = \
                self.lbdriver.update_listener(old_listener, listener, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("q_exception.NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_listener(self, context, listener, service):
        """Handle RPC cast from plugin to delete_listener."""
        try:
            service_pending = \
                self.lbdriver.delete_listener(listener, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("delete_listener: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_listener: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_pool(self, context, pool, service):
        """Handle RPC cast from plugin to create_pool."""
        try:
            service_pending = self.lbdriver.create_pool(pool, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_pool(self, context, old_pool, pool, service):
        """Handle RPC cast from plugin to update_pool."""
        try:
            service_pending = \
                self.lbdriver.update_pool(old_pool, pool, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_pool(self, context, pool, service):
        """Handle RPC cast from plugin to delete_pool."""
        try:
            service_pending = self.lbdriver.delete_pool(pool, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("delete_pool: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_pool: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_member(self, context, member, service):
        """Handle RPC cast from plugin to create_member."""
        try:
            service_pending = \
                self.lbdriver.create_member(member, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("create_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("create_member: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_member(self, context, old_member, member, service):
        """Handle RPC cast from plugin to update_member."""
        try:
            service_pending = \
                self.lbdriver.update_member(old_member, member, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("update_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_member: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_member(self, context, member, service):
        """Handle RPC cast from plugin to delete_member."""
        try:
            service_pending = self.lbdriver.delete_member(member, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("delete_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_member: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to create_pool_health_monitor."""
        try:
            service_pending = \
                self.lbdriver.create_health_monitor(health_monitor, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
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
            service_pending = \
                self.lbdriver.update_health_monitor(old_health_monitor,
                                                    health_monitor,
                                                    service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("update_health_monitor: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_health_monitor: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to delete_health_monitor."""
        try:
            service_pending = \
                self.lbdriver.delete_health_monitor(health_monitor, service)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except q_exception.NeutronException as exc:
            LOG.error("delete_health_monitor: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_health_monitor: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        if payload['admin_state_up'] != self.admin_state_up:
            LOG.info("agent administration status updated %s!", payload)
            self.admin_state_up = payload['admin_state_up']
            # the agent transitioned to down to up and the
            # driver reports healthy, trash the cache
            # and force an update to update agent scheduler
            if self.lbdriver.backend_integrity() and self.admin_state_up:
                self._report_state(True)
            else:
                self._report_state(False)

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

    @log_helpers.log_method_call
    def create_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to create_l7policy."""
        try:
            self.lbdriver.create_l7policy(l7policy, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_l7policy(self, context, old_l7policy, l7policy, service):
        """Handle RPC cast from plugin to update_l7policy."""
        try:
            self.lbdriver.update_l7policy(old_l7policy, l7policy, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to delete_l7policy."""
        try:
            self.lbdriver.delete_l7policy(l7policy, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("delete_l7policy: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_l7policy: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to create_l7rule."""
        try:
            self.lbdriver.create_l7rule(l7rule, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_l7rule(self, context, old_l7rule, l7rule, service):
        """Handle RPC cast from plugin to update_l7rule."""
        try:
            self.lbdriver.update_l7rule(old_l7rule, l7rule, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to delete_l7rule."""
        try:
            self.lbdriver.delete_l7rule(l7rule, service)
            self.cache.put(service, self.agent_host)
        except q_exception.NeutronException as exc:
            LOG.error("delete_l7rule: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_l7rule: Exception: %s" % exc.message)
