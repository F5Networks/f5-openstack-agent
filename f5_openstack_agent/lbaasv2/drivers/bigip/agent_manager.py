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
from random import randint

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
from f5_openstack_agent.lbaasv2.drivers.bigip import utils
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex

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
    cfg.IntOpt(
        'f5_pending_services_timeout',
        default=60,
        help=(
            'Amount of time to wait for a pending service to become active')
    ),
    cfg.IntOpt(
        'ccloud_orphans_cleanup_interval',
        default=0,
        help=(
            'Rescheduling interval for orphan cleanup in hours')
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

        # Create the cache of provisioned services
        self.cache = LogicalServiceCache()
        self.last_resync = datetime.datetime.now()
        # try to avoid orphan cleaning right after start and schedule differently on agents
        if self.conf.environment_group_number:
            start = int(self.conf.environment_group_number)
        else:
            start = randint(1, 3)

        # get orphan cleanup interval and set to a value between 0 and 24 if nonsense given
        orphans_interval = int(self.conf.ccloud_orphans_cleanup_interval)
        if orphans_interval < 0:
            orphans_interval = 0
        elif orphans_interval > 24:
            orphans_interval = 24

        # define interval in minutes
        self.orphans_cleanup_interval = 60 * orphans_interval
        # schedule first run with 1 hour difference on every agent. Start first run after 5 minutes, 1h and 5 mins, ...
        t = [60, 40, 20]
        if start < 1:
            start = 1
        self.last_clean_orphans = datetime.datetime.now() - datetime.timedelta(minutes=t[start-1] + 5)
        LOG.info('ccloud: Orphan cleanup interval = %s', self.orphans_cleanup_interval)

        self.needs_resync = False
        self.plugin_rpc = None
        self.pending_services = {}

        self.service_resync_interval = conf.service_resync_interval

        LOG.debug('Setting service resync interval to %d seconds' %
                  self.service_resync_interval)

        # Set the agent ID
        if self.conf.agent_id:
            self.agent_host = self.conf.agent_id
            LOG.debug('setting agent host to %s' % self.agent_host)
        else:
            self.agent_host = conf.host

        # Load the iControl driver.
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

        # Set iControl driver context for RPC.
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
                    'environment_capacity_score'] = env_score
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
        self.sync_state()

    @periodic_task.periodic_task(spacing=10)
    def periodic_resync(self, context):
        try:
            """Resync tunnels/service state."""
            now = datetime.datetime.now()
            LOG.debug("%s: periodic_resync called." % now)

            # Only force resync if the agent thinks it is
            # synchronized and the resync timer has exired
            if (now - self.last_resync).seconds > self.service_resync_interval:
                LOG.info("ccloud - periodic_resync: Running sync tasks")
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
            else:
                LOG.info("ccloud - periodic_resync: Skipped because resync interval not expired. Waiting another {0} seconds".format((self.service_resync_interval - (now - self.last_resync ).seconds)))

            # resync if we need to
            if self.needs_resync:
                LOG.info('periodic_resync: Forcing resync of services.')
                self.needs_resync = False
                if self.tunnel_sync():
                    self.needs_resync = True
                if self.sync_state():
                    self.needs_resync = True
                self.clean_orphaned_snat_objects()
            else:
                LOG.info("ccloud - periodic_resync: Resync not needed! Discarding ...")

            if self.orphans_cleanup_interval > 0:
                if (self.last_clean_orphans + datetime.timedelta(minutes=self.orphans_cleanup_interval)) < now:
                    LOG.info("ccloud - orphans: Start cleaning orphan objects from F5 device")
                    self.last_clean_orphans = self.last_clean_orphans + datetime.timedelta(minutes=self.orphans_cleanup_interval)
                    self.needs_resync = self.clean_orphaned_objects_and_save_device_config()
                    LOG.info("ccloud - orphans: Finished cleaning orphan objects from F5 device. Remaining objects --> {0}".format(self.lbdriver.get_orphans_cache()))
                else:
                    LOG.info("ccloud - periodic_resync: Skipping cleaning orphan objects because cleanup interval not expired. Waiting another {0} seconds"
                             .format((self.last_clean_orphans + datetime.timedelta(minutes=self.orphans_cleanup_interval) - now).seconds))
            else:
                LOG.info("ccloud - orphans: No orphan cleaning enabled. Only SNAT pool orphan handling will be done")

            LOG.info("ccloud - periodic_resync: Resync took {0} seconds".format((datetime.datetime.now() - now).seconds))

        except Exception as e:
            LOG.exception(("ccloud - Exception in periodic resync happend: " + str(e.message)))
            pass

    # ccloud: clean orphaned snat pools
    @log_helpers.log_method_call
    def clean_orphaned_snat_objects(self):
        virtual_addresses = self.lbdriver.get_all_virtual_addresses()
        snat_pools = self.lbdriver.get_all_snat_pools()

        for va in virtual_addresses:
            snat_obj = self.find_in_collection(va.name.replace('Project_', 'lb_'), snat_pools)
            if snat_obj is not None:
                snat_pools.remove(snat_obj)

        for orphaned_snat in snat_pools:
            LOG.debug("sapcc: purging orphaned snat pool %s" % orphaned_snat.name)
            orphaned_snat.delete()

    def find_in_collection(self, name, collection):
        for item in collection:
            if item is not None and item.name == name:
                return item
        return None

    @periodic_task.periodic_task(spacing=30)
    def update_operating_status(self, context):
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

    def tunnel_sync(self):
        """Call into driver to advertise tunnels."""
        LOG.debug("manager:tunnel_sync: calling driver tunnel_sync")
        return self.lbdriver.tunnel_sync()

    @log_helpers.log_method_call
    @utils.instrument_execution_time
    def sync_state(self):
        """Sync state of BIG-IP with that of the neutron database."""
        resync = False

        known_services = set()
        owned_services = set()
        for lb_id, service in self.cache.services.iteritems():
            known_services.add(lb_id)
            if self.agent_host == service.agent_host:
                owned_services.add(lb_id)
        now = datetime.datetime.now()

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

            for deleted_lb in owned_services - all_loadbalancer_ids:
                LOG.error("Cached service not found in neutron database")
                # self.destroy_service(deleted_lb)

            # Validate each service we own, i.e. loadbalancers to which this
            # agent is bound, that does not exist in our service cache.
            for lb_id in all_loadbalancer_ids:
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

        except Exception as e:
            LOG.warning("Unable to retrieve service. Service might be deleted in between: %s" % e.message)
            resync = True

        return resync

    @log_helpers.log_method_call
    @utils.instrument_execution_time
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
            LOG.warning(exc.msg)
        except q_exception.NeutronException as exc:
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
            if provisioning_status == plugin_const.ERROR:
                obj_id = obj.get('id', 'unknown')
                LOG.warning("Service object has object of type(id) {}({})"
                            " that is in '{}' status.".format(
                    item, obj_id, plugin_const.ERROR))
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
            loadbalancer['provisioning_status'] = plugin_const.ERROR
        return error_status

    @utils.instrument_execution_time
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

    @log_helpers.log_method_call
    def clean_orphaned_objects_and_save_device_config(self):

        cleaned = False

        try:
            #
            # Global cluster refresh tasks
            #

            # global_agent = self.plugin_rpc.get_clusterwide_agent(
            #     self.conf.environment_prefix,
            #     self.conf.environment_group_number
            # )
            #
            # if 'host' not in global_agent:
            #     LOG.debug('No global agent available to sync config')
            #     return True

            # ccloud: Set the agent to the cluster wide one as we have onley one per cluster at the moment

            global_agent = {}
            global_agent['host'] = self.agent_host

            if global_agent['host'] == self.agent_host:
                LOG.debug('this agent is the global config agent')
                # We're the global agent perform global cluster tasks

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
                    self.purge_orphaned_nodes(pools)

                # Ask the BIG-IP for all deployed monitors not associated
                # to a pool
                monitors = self.lbdriver.get_all_deployed_health_monitors()
                if monitors:
                    self.purge_orphaned_health_monitors(monitors)

            else:
                LOG.debug('the global agent is %s' % (global_agent['host']))
                cleaned = False

            cleaned = True
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
            # If the listener status is Unknown, it no longer exists
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
        """Deletes hanging nodes from the deleted listeners"""
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
