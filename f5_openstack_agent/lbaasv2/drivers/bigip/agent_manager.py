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

import datetime
import sys
import uuid

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
import oslo_messaging
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_utils import importutils

from neutron.agent import rpc as agent_rpc
from neutron.plugins.ml2.drivers.l2pop import rpc as l2pop_rpc
try:
    from neutron_lib import context as ncontext
except ImportError:
    from neutron import context as ncontext

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
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
        'provider_name',
        default='f5networks',
        help=('provider_name for snat pool addresses')
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
        default=True,
        help='Enable ESD file periodic refresh'
    )
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
        LOG.debug("runtime environment: %s" % sys.version)

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
        self.tunnel_rpc = None
        self.l2_pop_rpc = None
        self.state_rpc = None
        self.pending_services = {}

        self.service_resync_interval = conf.service_resync_interval
        LOG.debug('setting service resync intervl to %d seconds' %
                  self.service_resync_interval)

        # Load the driver.
        self._load_driver(conf)

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
            'agent_type': constants_v2.F5_AGENT_TYPE_LOADBALANCERV2,
            'l2_population': self.conf.l2_population,
            'start_flag': True,
            'configurations': agent_configurations
        }

        # Setup RPC for communications to and from controller
        self._setup_rpc()

        # Set driver context for RPC.
        self.lbdriver.set_context(self.context)
        # Allow the driver to make callbacks to the LBaaS driver plugin
        self.lbdriver.set_plugin_rpc(self.plugin_rpc)
        # Allow the driver to update tunnel endpoints
        self.lbdriver.set_tunnel_rpc(self.tunnel_rpc)
        # Allow the driver to update forwarding records in the SDN
        self.lbdriver.set_l2pop_rpc(self.l2_pop_rpc)
        # Allow the driver to force and agent state report to the controller
        self.lbdriver.set_agent_report_state(self._report_state)

        # Set the flag to resync tunnels/services
        self.needs_resync = True

        # Mark this agent admin_state_up per startup policy
        if(self.admin_state_up):
            self.plugin_rpc.set_agent_admin_state(self.admin_state_up)

        # Start state reporting of agent to Neutron
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)

        if self.lbdriver:
            self.lbdriver.connect()

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

        #
        # Setting up outbound communcations with the neutron agent extension
        #
        self.state_rpc = agent_rpc.PluginReportStateAPI(topic)

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

            # notifications when tunnel endpoints get added
            self.tunnel_rpc = agent_rpc.PluginApi(constants_v2.PLUGIN)

            # define which controler notifications the agent comsumes
            consumers = [[constants_v2.TUNNEL, constants_v2.UPDATE]]

            # if we are dynamically changing tunnel peers,
            # register to recieve and send notificatoins via RPC
            if self.conf.l2_population:
                # communications of notifications from the
                # driver to neutron for SDN topology changes
                self.l2_pop_rpc = l2pop_rpc.L2populationAgentNotifyAPI()

                # notification of SDN topology updates from the
                # controller by adding to the general consumer list
                consumers.append(
                    [constants_v2.L2POPULATION,
                     constants_v2.UPDATE,
                     self.agent_host]
                )

            # kick off the whole RPC process by creating
            # a connection to the message bus
            self.endpoints = [self]
            self.connection = agent_rpc.create_consumers(
                self.endpoints,
                constants_v2.AGENT,
                consumers
            )

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
            if self.lbdriver:
                if not self.lbdriver.backend_integrity():
                    self.needs_resync = True
                    self.cache.services = {}
                    self.lbdriver.flush_cache()
                    self.plugin_rpc.set_agent_admin_state(False)
                    self.admin_state_up = False
                else:
                    # if we are transitioning from down to up,
                    # change the controller state for this agent
                    if not self.admin_state_up:
                        self.plugin_rpc.set_agent_admin_state(True)
                        self.admin_state_up = True

            if self.lbdriver:
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

    @periodic_task.periodic_task(spacing=PERIODIC_TASK_INTERVAL)
    def connect_driver(self, context):
        """Trigger driver connect attempts to all devices."""
        if self.lbdriver:
            self.lbdriver.connect()

    @periodic_task.periodic_task(spacing=PERIODIC_TASK_INTERVAL)
    def refresh_esd(self, context):
        """Refresh ESD files."""
        if self.lbdriver.esd_processor and self.conf.esd_auto_refresh:
            LOG.info("refresh ESD files automatically")
            self.lbdriver.init_esd()

    @periodic_task.periodic_task(spacing=PERIODIC_TASK_INTERVAL)
    def recover_errored_devices(self, context):
        """Try to reconnect to errored devices."""
        if self.lbdriver:
            LOG.debug("running periodic task to retry errored devices")
            self.lbdriver.recover_errored_devices()

    @periodic_task.periodic_task(
        spacing=constants_v2.UPDATE_OPERATING_STATUS_INTERVAL)
    def scrub_dead_agents_in_env_and_group(self, context):
        """Triggering a dead agent scrub on the controller."""
        LOG.debug("running periodic scrub_dead_agents_in_env_and_group")
        if not self.plugin_rpc:
            return

        self.plugin_rpc.scrub_dead_agents(self.conf.environment_prefix,
                                          self.conf.environment_group_number)

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

    # setup a period task to decide if it is time empty the local service
    # cache and resync service definitions form the controller
    @periodic_task.periodic_task(spacing=PERIODIC_TASK_INTERVAL)
    def periodic_resync(self, context):
        """Determine if it is time to resync services from controller."""
        now = datetime.datetime.now()

        # check if a resync has not been requested by the driver
        if not self.needs_resync:
            # check if we hit the resync interval
            if (now - self.last_resync).seconds > self.service_resync_interval:
                self.needs_resync = True
                LOG.debug(
                    'forcing resync of services on resync timer (%d seconds).'
                    % self.service_resync_interval)
                self.cache.services = {}
                self.last_resync = now
                self.lbdriver.flush_cache()
                LOG.debug("periodic_sync: service_resync_interval expired: %s"
                          % str(self.needs_resync))
        # resync if we need to
        if self.needs_resync:
            LOG.debug("resync required at: %s" % now)
            self.needs_resync = False
            # advertise devices as VTEPs if required
            if self.tunnel_sync():
                self.needs_resync = True
            # synchronize LBaaS objects from controller
            if self.sync_state():
                self.needs_resync = True
            # clean any objects orphaned on devices and persist configs
            if self.clean_orphaned_objects_and_save_device_config():
                self.needs_resync = True

    def tunnel_sync(self):
        """Call into driver to advertise device tunnel endpoints."""
        LOG.debug("manager:tunnel_sync: calling driver tunnel_sync")
        return self.lbdriver.tunnel_sync()

    @log_helpers.log_method_call
    def sync_state(self):
        """Synchronize device configuration from controller state."""
        resync = False

        if hasattr(self, 'lbdriver'):
            if not self.lbdriver.backend_integrity():
                return resync

        known_services, owned_services = self._all_vs_known_services()

        try:
            # Get loadbalancers from the environment which are bound to
            # this agent.
            active_loadbalancers, active_loadbalancer_ids = \
                self._get_remote_loadbalancers('get_active_loadbalancers',
                                               host=self.agent_host)
            all_loadbalancers, all_loadbalancer_ids = \
                self._get_remote_loadbalancers('get_all_loadbalancers',
                                               host=self.agent_host)

            LOG.debug("plugin produced the list of active loadbalancer ids: %s"
                      % list(active_loadbalancer_ids))
            LOG.debug("currently known loadbalancer ids before sync are: %s"
                      % list(known_services))

            # Validate each service we own, i.e. loadbalancers to which this
            # agent is bound, that does not exist in our service cache.
            self._validate_services(all_loadbalancer_ids)

            resync = self._refresh_pending_services()

            # Get a list of any cached service we now know after
            # refreshing services
            owned_services, known_services = self._all_vs_known_services()
            LOG.debug("currently known loadbalancer ids after sync: %s"
                      % list(known_services))

        except Exception as e:
            LOG.exception("Unable to sync state: %s" % e.message)
            resync = True

        return resync

    def _all_vs_known_services(self):
        all_services = set()
        known_services = set()
        for lb_id, service in self.cache.services.iteritems():
            all_services.add(lb_id)
            if self.agent_host == service.agent_host:
                known_services.add(lb_id)
        return all_services, known_services

    def _refresh_pending_services(self):
        now = datetime.datetime.now()
        resync = False
        # This produces a list of loadbalancers with pending tasks to
        # be performed.
        pending_loadbalancers, pending_lb_ids = \
            self._get_remote_loadbalancers('get_pending_loadbalancers',
                                           host=self.agent_host)
        LOG.debug(
            "plugin produced the list of pending loadbalancer ids: %s"
            % list(pending_lb_ids))

        for lb_id in list(pending_lb_ids):
            lb_pending = self.refresh_service(lb_id)
            if lb_pending:
                if lb_id not in self.pending_services:
                    self.pending_services[lb_id] = now

                time_added = self.pending_services[lb_id]
                has_expired = bool((now - time_added).seconds >
                                   self.conf.f5_pending_services_timeout)

                if has_expired:
                    lb_pending = False
                    self.service_timeout(lb_id)

            if not lb_pending:
                try:
                    del self.pending_services[lb_id]
                except KeyError as e:
                    LOG.debug("LB not found in pending services: {0}".format(
                        e.message))

        # If there are services in the pending cache resync
        if self.pending_services:
            resync = True
        return resync

    def _get_remote_loadbalancers(self, plugin_rpc_attr, host=None):
        loadbalancers = getattr(self.plugin_rpc, plugin_rpc_attr)(host=host)
        lb_ids = [lb['lb_id'] for lb in loadbalancers]
        return tuple(loadbalancers), set(lb_ids)

    def _validate_services(self, lb_ids):
        for lb_id in lb_ids:
            if not self.cache.get_by_loadbalancer_id(lb_id):
                self.validate_service(lb_id)

    @log_helpers.log_method_call
    def validate_service(self, lb_id):

        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            if not self.lbdriver.service_exists(service) or \
                    self.has_provisioning_status_of_error(service):
                LOG.info("active loadbalancer '{}' is not on BIG-IP"
                         " or has error state...syncing".format(lb_id))
                self.lbdriver.sync(service)
            else:
                LOG.debug("Found service definition for '{}', state is ACTIVE"
                          " move on.".format(lb_id))
        except f5_ex.InvalidNetworkType as exc:
            LOG.warning(exc.message)
        except f5_ex.F5NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.exception("Service validation error: %s" % exc.message)

    @staticmethod
    def has_provisioning_status_of_error(service):
        """Determine if a service is in an ERROR/DEGRADED status.

        This staticmethod will go through a service object and determine if it
        has an ERROR status anywhere within the object.
        """
        expected_tree = dict(loadbalancer=dict, members=list, pools=list,
                             listeners=list, healthmonitors=list,
                             l7policies=list, l7policy_rules=list)
        error_status = False  # assume we're in the clear unless otherwise...
        loadbalancer = service.get('loadbalancer', dict())

        def handle_error(error_status, obj):
            provisioning_status = obj.get('provisioning_status')
            if provisioning_status == constants_v2.ERROR:
                obj_id = obj.get('id', 'unknown')
                LOG.warning("Service object has object of type(id) {}({})"
                            " that is in '{}' status.".format(
                                item, obj_id, constants_v2.ERROR))
                error_status = True
            return error_status

        for item in expected_tree:
            obj = service.get(item, expected_tree[item]())
            if expected_tree[item] == dict and isinstance(service[item], dict):
                error_status = handle_error(error_status, obj)
            elif expected_tree[item] == list and \
                    isinstance(obj, list):
                for item in obj:
                    if len(item) == 1:
                        # {'networks': [{'id': {<network_obj>}}]}
                        item = item[item.keys()[0]]
                    error_status = handle_error(error_status, item)
        if error_status:
            loadbalancer['provisioning_status'] = constants_v2.F5_ERROR
        return error_status

    @log_helpers.log_method_call
    def refresh_service(self, lb_id):
        try:
            service = self.plugin_rpc.get_service_by_loadbalancer_id(
                lb_id
            )
            self.cache.put(service, self.agent_host)
            if self.lbdriver.sync(service):
                self.needs_resync = True
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as e:
            LOG.error("Exception: %s" % e.message)

    @log_helpers.log_method_call
    def clean_orphaned_objects_and_save_device_config(self):

        cleaned = False

        try:
            #
            # Global cluster refresh tasks
            #

            global_agent = self.plugin_rpc.get_clusterwide_agent(
                self.conf.environment_prefix,
                self.conf.environment_group_number
            )

            if 'host' not in global_agent:
                LOG.debug('No global agent available to sync config')
                return True

            if global_agent['host'] == self.agent_host:
                LOG.debug('this agent is the global config agent')
                # We're the global agent perform global cluster tasks

                # There are two independent types of service objects
                # the LBaaS implments: 1) loadbalancers + 2) pools
                # We will first try to find any orphaned pools
                # and remove them.

                # Ask BIG-IP for all deployed loadbalancers (virtual addresses)
                lbs = self.lbdriver.get_all_deployed_loadbalancers(
                    purge_orphaned_folders=True)
                if lbs:
                    self.purge_orphaned_loadbalancers(lbs)

                # Ask the BIG-IP for all deployed listeners to make
                # sure we are not orphaning listeners which have
                # valid loadbalancers in a OK state
                listeners = self.lbdriver.get_all_deployed_listeners()
                if listeners:
                    self.purge_orphaned_listeners(listeners)

                policies = self.lbdriver.get_all_deployed_l7_policys()
                if policies:
                    self.purge_orphaned_l7_policys(policies)

                # Ask the BIG-IP for all deployed pools not associated
                # to a virtual server
                pools = self.lbdriver.get_all_deployed_pools()
                if pools:
                    self.purge_orphaned_pools(pools)

                # Ask the BIG-IP for all deployed monitors not associated
                # to a pool
                monitors = self.lbdriver.get_all_deployed_health_monitors()
                if monitors:
                    self.purge_orphaned_health_monitors(monitors)

            else:
                LOG.debug('the global agent is %s' % (global_agent['host']))
                return True
            # serialize config and save to disk
            self.lbdriver.backup_configuration()
        except Exception as e:
            LOG.error("Unable to sync state: %s" % e.message)
            cleaned = True

        return cleaned

    @log_helpers.log_method_call
    def purge_orphaned_loadbalancers(self, lbs):
        """Gets 'unknown' loadbalancers from Neutron and purges them

        Provisioning status of 'unknown' on loadbalancers means that the object
        does not exist in Neutron.  These should be deleted to consolidate
        hanging objects.
        """
        lbs_status = self.plugin_rpc.validate_loadbalancers_state(
            list(lbs.keys()))
        LOG.debug('validate_loadbalancers_state returned: %s'
                  % lbs_status)
        lbs_removed = False
        for lbid in lbs_status:
            # If the statu is Unknown, it no longer exists
            # in Neutron and thus should be removed from the BIG-IP
            if lbs_status[lbid] in ['Unknown']:
                LOG.debug('removing orphaned loadbalancer %s'
                          % lbid)
                # This will remove pools, virtual servers and
                # virtual addresses
                self.lbdriver.purge_orphaned_loadbalancer(
                    tenant_id=lbs[lbid]['tenant_id'],
                    loadbalancer_id=lbid,
                    hostnames=lbs[lbid]['hostnames'])
                lbs_removed = True
        if lbs_removed:
            # If we have removed load balancers, then scrub
            # for tenant folders we can delete because they
            # no longer contain loadbalancers.
            self.lbdriver.get_all_deployed_loadbalancers(
                purge_orphaned_folders=True)

    @log_helpers.log_method_call
    def purge_orphaned_listeners(self, listeners):
        """Deletes the hanging listeners from the deleted loadbalancers"""
        listener_status = self.plugin_rpc.validate_listeners_state(
            list(listeners.keys()))
        LOG.debug('validated_pools_state returned: %s'
                  % listener_status)
        for listenerid in listener_status:
            # If the pool status is Unknown, it no longer exists
            # in Neutron and thus should be removed from BIG-IP
            if listener_status[listenerid] in ['Unknown']:
                LOG.debug('removing orphaned listener %s'
                          % listenerid)
                self.lbdriver.purge_orphaned_listener(
                    tenant_id=listeners[listenerid]['tenant_id'],
                    listener_id=listenerid,
                    hostnames=listeners[listenerid]['hostnames'])

    @log_helpers.log_method_call
    def purge_orphaned_l7_policys(self, policies):
        """Deletes hanging l7_policies from the deleted listeners"""
        policies_used = set()
        listeners = self.lbdriver.get_all_deployed_listeners(
            expand_subcollections=True)
        for li_id in listeners:
            policy = listeners[li_id]['l7_policy']
            if policy:
                policy = policy.split('/')[2]
            policies_used.add(policy)
        has_l7policies = \
            self.plugin_rpc.validate_l7policys_state_by_listener(
                listeners.keys())
        # Ask Neutron for the status of all deployed l7_policys
        for policy_key in policies:
            policy = policies.get(policy_key)
            purged = False
            if policy_key not in policies_used:
                LOG.debug("policy '{}' no longer referenced by a listener: "
                          "({})".format(policy_key, policies_used))
                self.lbdriver.purge_orphaned_l7_policy(
                    tenant_id=policy['tenant_id'],
                    l7_policy_id=policy_key,
                    hostnames=policy['hostnames'])
                purged = True
            elif not has_l7policies.get(policy['id'], False):
                # should always be present on Neutron DB!
                LOG.debug("policy '{}' no longer present in Neutron's DB: "
                          "({})".format(policy_key, has_l7policies))
                self.lbdriver.purge_orphaned_l7_policy(
                    tenant_id=policy['tenant_id'],
                    l7_policy_id=policy_key,
                    hostnames=policy['hostnames'],
                    listener_id=li_id)
                purged = True
            if purged:
                LOG.info("purging orphaned l7policy {} as it's no longer in "
                         "Neutron".format(policy_key))

    @log_helpers.log_method_call
    def purge_orphaned_nodes(self, pools):
        """Deletes hanging pools from the deleted listeners"""
        pools_members = self.plugin_rpc.get_pools_members(
            list(pools.keys()))

        tenant_members = dict()
        for pool_id, pool in pools.iteritems():
            tenant_id = pool['tenant_id']
            members = pools_members.get(pool_id, list())

            if tenant_id not in tenant_members:
                tenant_members[tenant_id] = members
            else:
                tenant_members[tenant_id].extend(members)

        self.lbdriver.purge_orphaned_nodes(tenant_members)

    @log_helpers.log_method_call
    def purge_orphaned_pools(self, pools):
        """Deletes hanging pools from the deleted listeners"""
        # Ask Neutron for the status of all deployed pools
        pools_status = self.plugin_rpc.validate_pools_state(
            list(pools.keys()))
        LOG.debug('validated_pools_state returned: %s'
                  % pools_status)
        for poolid in pools_status:
            # If the pool status is Unknown, it no longer exists
            # in Neutron and thus should be removed from BIG-IP
            if pools_status[poolid] in ['Unknown']:
                LOG.debug('removing orphaned pool %s' % poolid)
                self.lbdriver.purge_orphaned_pool(
                    tenant_id=pools[poolid]['tenant_id'],
                    pool_id=poolid,
                    hostnames=pools[poolid]['hostnames'])

    @log_helpers.log_method_call
    def purge_orphaned_health_monitors(self, monitors):
        """Deletes hanging Health Monitors from the deleted Pools"""
        # ask Neutron for for the status of all deployed monitors...
        monitors_used = set()
        pools = self.lbdriver.get_all_deployed_pools()
        LOG.debug("pools found: {}".format(pools))
        for pool_id in pools:
            monitorid = pools.get(pool_id).get('monitors', 'None')
            monitors_used.add(monitorid)
        LOG.debug('health monitors in use: {}'.format(monitors_used))
        for monitorid in monitors:
            if monitorid not in monitors_used:
                LOG.debug("purging healthmonitor {} as it is not "
                          "in ({})".format(monitorid, monitors_used))
                self.lbdriver.purge_orphaned_health_monitor(
                    tenant_id=monitors[monitorid]['tenant_id'],
                    monitor_id=monitorid,
                    hostnames=monitors[monitorid]['hostnames'])

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

        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.NeutronException: %s" % exc.msg)
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_loadbalancer_stats(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to get stats."""
        try:
            self.lbdriver.get_stats(service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("delete_pool: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_pool: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_member(
        self, context, member, service, the_port_id=None
    ):
        """Handle RPC cast from plugin to create_member."""
        try:
            service_pending = \
                self.lbdriver.create_member(member, service, the_port_id)
            self.cache.put(service, self.agent_host)
            if service_pending:
                self.needs_resync = True
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
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
        except f5_ex.F5NeutronException as exc:
            LOG.error("remove_fdb_entries: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("remove_fdb_entries: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions."""
        try:
            LOG.debug('received update_fdb_entries: %s host: %s'
                      % (fdb_entries, host))
            # self.lbdriver.fdb_update(fdb_entries)
            LOG.warning("update_fdb_entries: the LBaaSv2 Agent does not "
                        "handle an update of the IP address of a neutron "
                        "port. This port is generally tied to a member. If "
                        "the IP address of a member was changed, be sure to "
                        "also recreate the member in neutron-lbaas with the "
                        "new address.")
        except f5_ex.F5NeutronException as exc:
            LOG.error("update_fdb_entries: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_fdb_entries: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to create_l7policy."""
        try:
            self.lbdriver.create_l7policy(l7policy, service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_l7policy(self, context, old_l7policy, l7policy, service):
        """Handle RPC cast from plugin to update_l7policy."""
        try:
            self.lbdriver.update_l7policy(old_l7policy, l7policy, service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to delete_l7policy."""
        try:
            self.lbdriver.delete_l7policy(l7policy, service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("delete_l7policy: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_l7policy: Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def create_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to create_l7rule."""
        try:
            self.lbdriver.create_l7rule(l7rule, service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def update_l7rule(self, context, old_l7rule, l7rule, service):
        """Handle RPC cast from plugin to update_l7rule."""
        try:
            self.lbdriver.update_l7rule(old_l7rule, l7rule, service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log_helpers.log_method_call
    def delete_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to delete_l7rule."""
        try:
            self.lbdriver.delete_l7rule(l7rule, service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("delete_l7rule: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_l7rule: Exception: %s" % exc.message)
