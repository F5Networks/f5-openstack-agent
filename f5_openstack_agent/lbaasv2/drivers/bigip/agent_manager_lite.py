"""Agent manager lite to handle plugin to agent RPC and periodic tasks."""
# coding=utf-8
# Copyright (c) 2020, F5 Networks, Inc.
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
import re
import sys
import uuid

from f5.bigip import ManagementRoot
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

from f5_openstack_agent.client.bigip import BipipCommand
from f5_openstack_agent.lbaasv2.drivers.bigip import bigip_device
from f5_openstack_agent.lbaasv2.drivers.bigip.bigip_device import set_bigips
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import \
    persist_config
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip import opts
from f5_openstack_agent.lbaasv2.drivers.bigip import plugin_rpc
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_manager

from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import \
    SystemHelper

from icontrol.exceptions import iControlUnexpectedHTTPError
from requests import HTTPError


LOG = logging.getLogger(__name__)

opts.register_f5_opts()

PERIODIC_MEMBER_UPDATE_INTERVAL = 30


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

        # Create the cache of provisioned services
        self.cache = LogicalServiceCache()
        self.last_resync = datetime.datetime.now()
        self.last_member_update = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.needs_resync = False
        self.needs_member_update = True
        self.member_update_base = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.member_update_mode = self.conf.member_update_mode
        self.member_update_number = self.conf.member_update_number
        self.member_update_interval = self.conf.member_update_interval
        self.member_update_agent_number = self.conf.member_update_agent_number
        self.member_update_agent_order = self.conf.member_update_agent_order
        self.plugin_rpc = None
        self.tunnel_rpc = None
        self.l2_pop_rpc = None
        self.state_rpc = None
        self.system_helper = None
        self.resync_interval = conf.resync_interval
        self.config_save_interval = conf.config_save_interval
        LOG.debug('setting service resync intervl to %d seconds' %
                  self.resync_interval)

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
            {'environment_prefix': self.conf.environment_prefix}
        )

        if self.conf.vtep_ip:
            llinfo = []
            llinfo.append({"node_vtep_ip": self.conf.vtep_ip})
            agent_configurations["local_link_information"] = llinfo

        if self.conf.static_agent_configuration_data:
            entries = str(self.conf.static_agent_configuration_data).split(',')
            for entry in entries:
                nv = entry.strip().split(':')
                if len(nv) > 1:
                    agent_configurations[nv[0]] = nv[1]

        self.agent_state = {
            'binary': constants_v2.AGENT_BINARY_NAME,
            'host': self.agent_host,
            'topic': constants_v2.TOPIC_LOADBALANCER_AGENT_V2,
            'agent_type': constants_v2.F5_AGENT_TYPE_LOADBALANCERV2,
            'l2_population': self.conf.l2_population,
            'start_flag': True,
            'configurations': agent_configurations,
            'availability_zone': self.conf.availability_zone
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
        self.system_helper = SystemHelper()

        # NOTE(pzhang): agent state update
        # Start state reporting of agent to Neutron
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            reportbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            reportbeat.start(interval=report_interval)

        member_update_interval = self.conf.member_update_interval
        if member_update_interval > 0:
            LOG.debug('Starting the member status update task.')
            member_update_task = loopingcall.FixedIntervalLoopingCall(
                self.update_member_status_task)
            member_update_task.start(interval=30)
        else:
            LOG.debug('The member update interval %d is negative.' %
                      member_update_interval)

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
            self.conf,
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
            if self.lbdriver:
                if not self.lbdriver.backend_integrity():
                    self.needs_resync = True
                    self.cache.services = {}
                    self.lbdriver.flush_cache()

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

    def connect_driver(self):
        """Trigger driver connect attempts to all devices."""
        if self.lbdriver:
            self.lbdriver.connect()

    @staticmethod
    def calculate_member_status(member):
        member_status = None
        session = None
        status = None
        if 'state' in member:
            status = member['state']
        if 'session' in member:
            session = member['session']

        if status == 'unchecked':
            member_status = constants_v2.F5_NO_MONITOR
        elif status == 'down':
            if session == 'user-disabled':
                member_status = constants_v2.F5_DISABLED
            else:
                member_status = constants_v2.F5_OFFLINE
        elif status == 'up':
            if session == 'user-disabled':
                member_status = constants_v2.F5_DISABLED
            else:
                member_status = constants_v2.F5_ONLINE
        elif status == 'checking':
            if session == 'monitor-enabled':
                member_status = constants_v2.F5_CHECKING
        else:
            LOG.warning("Unexpected status %s and session %s",
                        status, session)
        return member_status

    def append_one_member(self, member, pool_id, all_members):
        """append one member """
        if not member:
            LOG.debug("member is empty.")
            return

        if 'name' in member:
            name = member['name']
            if not name:
                LOG.debug("member's name is empty.")
                return

            match_obj = re.match(r'(.*)[:|.][1-9]\d*', name, re.M | re.I)
            if match_obj:
                address = match_obj.group(1)
                if "%" in address:
                    address = address.split("%")[0]
            else:
                LOG.debug("name %s format is wrong.", name)
                return

            port = name[len(address):]

            if ":" in port:
                port = port.split(":")[1]
            elif "." in port:
                port = port.split(".")[1]
            else:
                LOG.debug("port format is invalid.")
                return

            member_info = {}
            member_info['pool_id'] = pool_id
            member_info['address'] = address
            member_info['protocol_port'] = int(port)
            member_info['state'] = \
                self.calculate_member_status(member)
            if member_info['state'] is not None and \
               member_info['state'] != constants_v2.F5_CHECKING:
                all_members.append(member_info)
        else:
            LOG.debug("member name doesn't exist.")
        return

    def append_members_one_pool(self, bigip, pool, all_members):
        """update the members' status in one pool """
        if not bigip:
            LOG.debug("bigip is empty.")
            return

        try:
            tenant_id = pool['tenant_id']
            pool_id = pool['id']
            pool_name = self.conf.environment_prefix + '_' + pool_id
            partition = self.conf.environment_prefix + '_' + tenant_id
            pool = resource_helper.BigIPResourceHelper(
                resource_helper.ResourceType.pool).load(
                   bigip, name=pool_name, partition=partition)
            members = pool.members_s.get_collection()
            # figure out the members in this pool and send
            # the members and their statuses to driver in batch
            LOG.debug("The member length is %d for pool %s.",
                      len(members), pool_name)
            for member in members:
                self.append_one_member(member.__dict__, pool_id,
                                       all_members)
        except HTTPError as err:
            if err.response.status_code == 404:
                LOG.debug('pool %s not on BIG-IP %s.'
                          % (pool_id, bigip.hostname))
        except Exception as exc:
            LOG.exception('Exception get members %s' % str(exc))

        return

    @log_helpers.log_method_call
    def update_all_member_status_by_folders(self, bigip, folders):
        """update the members in all pools """
        if not bigip:
            LOG.debug("bigip is empty.")
            return
        prefix_name = self.conf.environment_prefix
        batch_number = self.conf.member_update_number
        prefix_len = len(prefix_name)
        all_members = []
        member_number = 0
        folder_number = len(folders)
        for folder in folders:
            LOG.debug("The folder is %s." % folder)
            # tenant_id = folder[len(self.conf.environment_prefix):]
            try:
                if not str(folder).startswith(prefix_name):
                    LOG.debug("folder %s doesn't start with prefix.",
                              str(folder))
                    continue

                resource = resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.pool)
                deployed_pools = resource.get_resources(bigip, folder, True)
                if deployed_pools:
                    LOG.debug("get %d pool(s) for %s.",
                              len(deployed_pools), str(folder))
                    for pool in deployed_pools:
                        # retrieve and append members in pool
                        reference = pool.membersReference
                        if 'items' not in reference:
                            LOG.debug("no items attribute for pool %s",
                                      pool.name)
                            continue

                        if not str(pool.name).startswith(prefix_name):
                            LOG.debug("folder %s doesn't start with prefix.",
                                      str(pool.name))
                            continue

                        members = reference['items']
                        pool_id = pool.name[prefix_len + 1:]
                        LOG.debug("Get %d members.", len(members))
                        for member in members:
                            self.append_one_member(
                                member,
                                pool_id,
                                all_members
                            )

                # check after one folder
                if batch_number > 0 and len(all_members) >= batch_number:
                    member_number += len(all_members)
                    LOG.debug("update member status in batch %d",
                              len(all_members))
                    self.plugin_rpc.update_member_status_in_batch(
                        all_members)
                    all_members[:] = []

            except Exception as e:
                all_members[:] = []
                LOG.error("Unable to update member state: %s" % e.message)

        if len(all_members) > 0:
            member_number += len(all_members)
            LOG.debug("last round update member status in batch %d",
                      len(all_members))
            self.plugin_rpc.update_member_status_in_batch(
                     all_members)
            all_members[:] = []

        LOG.debug("Totally update %u folders %u members",
                  folder_number, member_number)

        return

    @log_helpers.log_method_call
    def update_all_member_status_by_pools(self, bigip, pools):
        """update the members in all pools """
        if not bigip:
            LOG.debug("bigip is empty.")
            return

        batch_number = self.conf.member_update_number
        all_members = []
        pool_number = len(pools)
        member_number = 0

        for pool_id in pools:
            pool = pools.get(pool_id, None)
            if not pool:
                LOG.debug("couldn't find pool %s.", pool_id)
                continue

            self.append_members_one_pool(bigip, pool, all_members)
            if batch_number > 0 and len(all_members) >= batch_number:
                member_number += len(all_members)
                LOG.debug("update member status in batch %d",
                          len(all_members))
                self.plugin_rpc.update_member_status_in_batch(
                    all_members)
                all_members[:] = []

        if len(all_members):
            member_number += len(all_members)
            LOG.debug("update member status in batch %d",
                      len(all_members))
            self.plugin_rpc.update_member_status_in_batch(
                all_members)
            all_members[:] = []

        LOG.debug("Totally update %u pools %u members",
                  pool_number, member_number)

        return

    def update_member_status_task(self):
        """Update pool member operational status from devices to controller."""
        if not self.needs_member_update:
            LOG.debug("The previous task is still running.")
            return

        if self.member_update_interval < 0:
            LOG.debug('The interval is negative %d' %
                      self.member_update_interval)
            return

        if self.member_update_agent_order < 0:
            LOG.debug('The agent order is negative %d' %
                      self.member_update_agent_order)
            return

        now = datetime.datetime.now()
        time_delta = (now - self.last_member_update).seconds
        if time_delta < self.member_update_interval:
            LOG.debug('The interval %d (%d) is not met yet.',
                      time_delta, self.member_update_interval)
            return

        time_delta = (now - self.member_update_base).seconds
        order = time_delta % (self.member_update_agent_number *
                              self.member_update_interval)
        order /= self.member_update_interval

        if (order != self.member_update_agent_order):
            LOG.debug("Not the order %u for this agent %u to be runnning",
                      order, self.member_update_agent_order)
            return

        """ we only update the member status when:
         1) the order is the right.
         2) the time passed since last update is no less than interval.
        """

        LOG.debug("Begin updating member status at %s." % now)
        self.last_member_update = now
        self.needs_member_update = False

        """ the logic is, we retrieve all the members from bigip directly
        and update the neutron server in batch with the members' statuses.

        two modes for the update. One is per pool and the other is
        per folder. """

        try:
            commander = BipipCommand()
            bigips = commander.get_active_bigips(self.conf.availability_zone)
            LOG.debug("get %s active bigips" % len(bigips))
            for info in bigips:
                LOG.debug("bigip info: %s" % info)
                bigip = ManagementRoot(info['hostname'],
                                       info['username'],
                                       info['password'],
                                       port=info['port'])

                if self.conf.member_update_mode == 1:
                    # logic of update member by pools
                    pools = self.lbdriver.get_all_pools_for_one_bigip(bigip)
                    if pools:
                        LOG.debug("%d pool(s) found", len(pools))
                        self.update_all_member_status_by_pools(bigip, pools)
                    else:
                        LOG.debug("no vailable pools")
                elif self.conf.member_update_mode == 2:
                    # logic of update member by folders
                    folders = self.system_helper.get_folders(bigip)
                    if folders:
                        LOG.debug("%d folder(s) found", len(folders))
                        self.update_all_member_status_by_folders(
                            bigip, folders)
                    else:
                        LOG.debug("no vailable folders")
                else:
                    LOG.debug("member update mode %d isnt' supported.",
                              self.conf.member_update_mode)
        except Exception as e:
            self.needs_member_update = True
            LOG.error("Unable to update member state: %s" % e.message)

        self.needs_member_update = True
        now = datetime.datetime.now()
        LOG.debug("End updating member status at %s." % now)

        return

    ######################################################################
    #
    # handlers for all in bound requests and notifications from controller
    #
    ######################################################################
    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to create_loadbalancer."""
        id = loadbalancer['id']

        try:
            mgr = resource_manager.LoadBalancerManager(self.lbdriver)
            mgr.create(loadbalancer, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create loadbalancer %s", id)
        except Exception as ex:
            LOG.error("Fail to create loadbalancer %s "
                      "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_loadbalancer_status(
                    id, provision_status,
                    operating_status
                )
                LOG.info("Finish to update status of loadbalancer %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of loadbalancer %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_loadbalancer(self, context, old_loadbalancer,
                            loadbalancer, service):
        """Handle RPC cast from plugin to update_loadbalancer."""
        id = loadbalancer['id']

        try:
            mgr = resource_manager.LoadBalancerManager(self.lbdriver)
            mgr.update(old_loadbalancer, loadbalancer, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to update loadbalancer %s", id)
        except Exception as ex:
            LOG.exception("Fail to update loadbalancer %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_loadbalancer_status(
                    id, provision_status,
                    operating_status
                )
                LOG.info("Finish to update status of loadbalancer %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of loadbalancer %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to delete_loadbalancer."""
        id = loadbalancer['id']

        try:
            mgr = resource_manager.LoadBalancerManager(self.lbdriver)
            mgr.delete(loadbalancer, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to delete loadbalancer %s", id)
        except iControlUnexpectedHTTPError as ex:
            fd_matched = re.search(
                "The requested folder (.*) was not found.",
                ex.response.content
            )
            rd_matched = re.search(
                "The requested route domain (.*) was not found.",
                ex.response.content
            )
            provision_status = constants_v2.F5_ERROR
            if ex.response.status_code == 400 and fd_matched:
                LOG.warning("Not Found Exception to delete loadbalancer %s "
                            "by exception: %s, delete loadbalancer in Neutron",
                            id, ex.response.content)
                provision_status = constants_v2.F5_ACTIVE
            if ex.response.status_code == 404 and rd_matched:
                LOG.warning("Not Found Exception to delete loadbalancer %s "
                            "by exception: %s, delete loadbalancer in Neutron",
                            id, ex.response.content)
                provision_status = constants_v2.F5_ACTIVE
        except f5_ex.ProjectIDException as ex:
            LOG.debug("Delete loadbalancer with ProjectIDException")
            provision_status = constants_v2.F5_ACTIVE
        except Exception as ex:
            LOG.error("Fail to delete loadbalancer %s "
                      "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.loadbalancer_destroyed(id)
                else:
                    self.plugin_rpc.update_loadbalancer_status(
                        id, provision_status,
                        loadbalancer['operating_status']
                    )
                LOG.info("Finish to update status of loadbalancer %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of loadbalancer %s "
                              "Exception: %s", id, ex.message)

    # NOTE(pzhang): do we use this ?
    @log_helpers.log_method_call
    def update_loadbalancer_stats(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to get stats."""

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'])
            service['bigips'] = bigip_dev.get_all_bigips()

            self.lbdriver.get_stats(service)
            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_listener(self, context, listener, service):
        """Handle RPC cast from plugin to create_listener."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            mgr = resource_manager.ListenerManager(self.lbdriver)
            mgr.create(listener, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create listener %s", id)
        except Exception as ex:
            LOG.exception("Fail to create listener %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_listener_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of listener %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of listener %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_listener(self, context, old_listener, listener, service):
        """Handle RPC cast from plugin to update_listener."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            mgr = resource_manager.ListenerManager(self.lbdriver)
            mgr.update(old_listener, listener, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to update listener %s", id)
        except Exception as ex:
            LOG.exception("Fail to update listener %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                self.plugin_rpc.update_listener_status(
                    id, provision_status,
                    listener['operating_status']
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of listener %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of listener %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_listener(self, context, listener, service):
        """Handle RPC cast from plugin to delete_listener."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            mgr = resource_manager.ListenerManager(self.lbdriver)
            mgr.delete(listener, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to delete listener %s", id)
        except Exception as ex:
            LOG.exception("Fail to delete listener %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.listener_destroyed(id)
                else:
                    self.plugin_rpc.update_listener_status(
                        id, provision_status,
                        listener['operating_status']
                    )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info(
                    "Finish to update status of listener %s", id
                )
            except Exception as ex:
                LOG.exception("Fail to update status of listener %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_acl_bind(self, context, listener, acl_bind, service):
        """Handle RPC cast from plugin to update_acl_bind."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            mgr = resource_manager.ListenerManager(self.lbdriver)
            mgr.update_acl_bind(listener, acl_bind, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to update ACL bind of listener %s", id)
        except Exception as ex:
            LOG.exception("Fail to update ACL bind of listener %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                self.plugin_rpc.update_listener_status(
                    id, provision_status,
                    listener['operating_status']
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info(
                    "Finish to update acl status of listener %s", id
                )
            except Exception as ex:
                LOG.exception("Fail to update status of listener %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_pool(self, context, pool, service):
        """Handle RPC cast from plugin to create_pool."""
        loadbalancer = service['loadbalancer']
        id = pool['id']

        try:
            mgr = resource_manager.PoolManager(self.lbdriver)
            mgr.create(pool, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create pool %s", id)
        except Exception as ex:
            LOG.exception("Fail to create pool %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_pool_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of pool %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of pool %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_pool(self, context, old_pool, pool, service):
        """Handle RPC cast from plugin to update_pool."""
        loadbalancer = service['loadbalancer']
        id = pool['id']

        try:
            # TODO(qzhao): Deploy config to BIG-IP
            mgr = resource_manager.PoolManager(self.lbdriver)
            mgr.update(old_pool, pool, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to update pool %s", id)
        except Exception as ex:
            LOG.exception("Fail to uppdate pool %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                self.plugin_rpc.update_pool_status(
                    id, provision_status,
                    pool['operating_status']
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of pool %s", id)
            except Exception as ex:
                LOG.error("Fail to update status of pool %s "
                          "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_pool(self, context, pool, service):
        """Handle RPC cast from plugin to delete_pool."""
        loadbalancer = service['loadbalancer']
        id = pool['id']

        try:
            mgr = resource_manager.PoolManager(self.lbdriver)
            mgr.delete(pool, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to delete pool %s", id)
        except Exception as ex:
            LOG.exception("Fail to delete pool %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.pool_destroyed(id)
                else:
                    self.plugin_rpc.update_pool_status(
                        id, provision_status,
                        pool['operating_status']
                    )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of pool %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of pool %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_member(
        self, context, member, service, the_port_id=None,
        the_port_ids=[]
    ):
        """Handle RPC cast from plugin to create_member."""
        loadbalancer = service['loadbalancer']
        multiple = service.get("multiple", False)
        id = member['id']

        try:
            mgr = resource_manager.MemberManager(self.lbdriver)
            mgr.create(member, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            if multiple:
                LOG.debug("Finish to create multiple members")
            else:
                LOG.debug("Finish to create member %s", id)
        except Exception as ex:
            if multiple:
                LOG.error("Fail to create multiple members "
                          "Exception: %s", ex.message)
            else:
                LOG.error("Fail to create member %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                members = []
                if not multiple:
                    members.append(member)
                else:
                    for m in service['members']:
                        if m['provisioning_status'] == \
                           constants_v2.F5_PENDING_CREATE:
                            members.append(m)

                for m in members:
                    self.plugin_rpc.update_member_status(
                        m['id'], provision_status, operating_status
                    )

                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                if multiple:
                    LOG.info("Finish to update status of multiple members")
                else:
                    LOG.info("Finish to update status of member %s", id)

                if the_port_id:
                    LOG.info(the_port_id)
                    self.plugin_rpc.delete_port(port_id=the_port_id)
                if the_port_ids:
                    LOG.info(the_port_ids)
                    for each in the_port_ids:
                        self.plugin_rpc.delete_port(port_id=each)
            except Exception as ex:
                if multiple:
                    LOG.exception("Fail to update status of multiple members "
                                  "Exception: %s", ex.message)
                else:
                    LOG.exception("Fail to update status of member %s "
                                  "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_member(self, context, old_member, member, service):
        """Handle RPC cast from plugin to update_member."""
        loadbalancer = service['loadbalancer']
        id = member['id']

        try:
            mgr = resource_manager.MemberManager(self.lbdriver)
            mgr.update(old_member, member, service)
            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to update member %s", id)
        except Exception as ex:
            LOG.exception("Fail to update member %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                self.plugin_rpc.update_member_status(
                    id, provision_status,
                    member['operating_status']
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of member %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of member %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_member(self, context, member, service):
        """Handle RPC cast from plugin to delete_member."""
        loadbalancer = service['loadbalancer']
        multiple = service.get("multiple", False)
        id = member['id']

        try:
            mgr = resource_manager.MemberManager(self.lbdriver)
            mgr.delete(member, service)
            provision_status = constants_v2.F5_ACTIVE
            if multiple:
                LOG.debug("Finish to delete multiple members")
            else:
                LOG.debug("Finish to delete member %s", id)
        except f5_ex.ProjectIDException as ex:
            LOG.debug("Delete Member with ProjectIDException")
            provision_status = constants_v2.F5_ACTIVE
        except Exception as ex:
            if multiple:
                LOG.error("Fail to delete multiple members "
                          "Exception: %s", ex.message)
            else:
                LOG.error("Fail to delete member %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                members = []
                if not multiple:
                    members.append(member)
                else:
                    for m in service['members']:
                        if m['provisioning_status'] == \
                           constants_v2.F5_PENDING_DELETE:
                            members.append(m)

                for m in members:
                    if provision_status == constants_v2.F5_ACTIVE:
                        self.plugin_rpc.member_destroyed(m['id'])
                    else:
                        self.plugin_rpc.update_member_status(
                            m['id'], provision_status,
                            m['operating_status']
                        )

                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                if multiple:
                    LOG.info("Finish to update status of multiple members")
                else:
                    LOG.info("Finish to update status of member %s", id)
            except Exception as ex:
                if multiple:
                    LOG.exception("Fail to update status of multiple members "
                                  "Exception: %s", ex.message)
                else:
                    LOG.exception("Fail to update status of member %s "
                                  "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to create_pool_health_monitor."""
        loadbalancer = service['loadbalancer']
        id = health_monitor['id']

        try:
            mgr = resource_manager.MonitorManager(
                self.lbdriver, type=health_monitor['type']
            )
            mgr.create(health_monitor, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create monitor %s", id)
        except Exception as ex:
            LOG.exception("Fail to create monitor %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_health_monitor_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info(
                    "Finish to update status of health_monitor %s", id
                )
            except Exception as ex:
                LOG.exception("Fail to update status of health_monitor %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_health_monitor(self, context, old_health_monitor,
                              health_monitor, service):
        """Handle RPC cast from plugin to update_health_monitor."""
        loadbalancer = service['loadbalancer']
        id = health_monitor['id']

        try:
            mgr = resource_manager.MonitorManager(
                self.lbdriver, type=health_monitor['type']
            )
            mgr.update(old_health_monitor, health_monitor, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to update health_monitor %s", id)
        except Exception as ex:
            LOG.exception("Fail to update health_monitor %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_health_monitor_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of health_monitor %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of health_monitor %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to delete_health_monitor."""
        loadbalancer = service['loadbalancer']
        id = health_monitor['id']

        try:
            mgr = resource_manager.MonitorManager(
                self.lbdriver, type=health_monitor['type']
            )
            mgr.delete(health_monitor, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to delete health_monitor %s", id)
        except Exception as ex:
            LOG.exception("Fail to delete health_monitor %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.health_monitor_destroyed(id)
                else:
                    self.plugin_rpc.update_health_monitor_status(
                        id, provision_status, operating_status
                    )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info(
                    "Finish to update status of health_monitor %s",
                    id
                )
            except Exception as ex:
                LOG.exception("Fail to update status of health_monitor %s "
                              "Exception: %s", id, ex.message)

    # NOTE(pzhang): anyone use this please delete this comment
    @log_helpers.log_method_call
    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        LOG.info("agent administration status updated %s!", payload)
        # the agent transitioned to down to up and the
        # driver reports healthy, trash the cache
        # and force an update to update agent scheduler
        if self.lbdriver.backend_integrity():
            self._report_state(True)
        else:
            self._report_state(False)

    # NOTE(pzhang): anyone use this please delete this comment
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

    # NOTE(pzhang): anyone use this please delete this comment
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

    # NOTE(pzhang): anyone use this please delete this comment
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

    # NOTE(pzhang): anyone use this please delete this comment
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

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to create_l7policy."""
        loadbalancer = service['loadbalancer']
        id = l7policy['id']

        try:
            mgr = resource_manager.L7PolicyManager(self.lbdriver)
            mgr.create(l7policy, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create l7policy %s", id)
        except Exception as ex:
            LOG.exception("Fail to create l7policy %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_l7policy_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of l7policy %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of l7policy %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_l7policy(self, context, old_l7policy, l7policy, service):
        """Handle RPC cast from plugin to update_l7policy."""
        loadbalancer = service['loadbalancer']
        id = l7policy['id']

        try:
            mgr = resource_manager.L7PolicyManager(self.lbdriver)
            mgr.update(old_l7policy, l7policy, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to update l7policy %s", id)
        except Exception as ex:
            LOG.exception("Fail to update l7policy %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_l7policy_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of l7policy %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of l7policy %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to delete_l7policy."""
        loadbalancer = service['loadbalancer']
        id = l7policy['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'])
            service['bigips'] = bigip_dev.get_all_bigips()

            mgr = resource_manager.L7PolicyManager(self.lbdriver)
            mgr.delete(l7policy, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to delete l7policy %s", id)
        except Exception as ex:
            LOG.exception("Fail to delete l7policy %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.l7policy_destroyed(id)
                else:
                    self.plugin_rpc.update_l7policy_status(
                        id, provision_status, operating_status
                    )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of l7policy %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of l7policy %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def create_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to create_l7rule."""
        loadbalancer = service['loadbalancer']
        id = l7rule['id']

        try:
            mgr = resource_manager.L7RuleManager(self.lbdriver)
            mgr.create(l7rule, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create l7rule %s", id)
        except Exception as ex:
            LOG.exception("Fail to create l7rule %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_l7rule_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of l7rule %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of l7rule %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def update_l7rule(self, context, old_l7rule, l7rule, service):
        """Handle RPC cast from plugin to update_l7rule."""
        loadbalancer = service['loadbalancer']
        id = l7rule['id']

        try:
            mgr = resource_manager.L7RuleManager(self.lbdriver)
            mgr.update(old_l7rule, l7rule, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to update l7rule %s", id)
        except Exception as ex:
            LOG.exception("Fail to update l7rule %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_l7rule_status(
                    id, provision_status, operating_status
                )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of l7rule %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of l7 rule %s "
                              "Exception: %s", id, ex.message)

    @set_bigips
    @persist_config
    @log_helpers.log_method_call
    def delete_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to delete_l7rule."""
        loadbalancer = service['loadbalancer']
        id = l7rule['id']

        try:
            # TODO(qzhao): Deploy config to BIG-IP
            mgr = resource_manager.L7RuleManager(self.lbdriver)
            mgr.delete(l7rule, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to delete l7rule %s", id)
        except Exception as ex:
            LOG.exception("Fail to delete l7rule %s "
                          "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.l7rule_destroyed(id)
                else:
                    self.plugin_rpc.update_l7rule_status(
                        id, provision_status, operating_status
                    )
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of l7rule %s", id)
            except Exception as ex:
                LOG.exception("Failt to updte status of l7rule %s "
                              "Exception: %s", id, ex.message)

    @log_helpers.log_method_call
    def create_acl_group(self, context, acl_group):
        """Handle RPC cast from plugin to create ACL Group."""
        id = acl_group['id']
        try:
            mgr = resource_manager.ACLGroupManager(self.lbdriver)
            mgr.create(acl_group)
            LOG.debug("Finish to create acl_group %s", id)
        except Exception as ex:
            LOG.error("Fail to create acl_group %s "
                      "Exception: %s", id, ex.message)

    @log_helpers.log_method_call
    def delete_acl_group(self, context, acl_group):
        """Handle RPC cast from plugin to delete ACL Group."""
        try:
            mgr = resource_manager.ACLGroupManager(self.lbdriver)
            mgr.delete(acl_group)
            LOG.debug("Finish to delete ACL Group %s", id)
        except Exception as ex:
            LOG.error("Fail to delete ACL Group %s "
                      "Exception: %s", id, ex.message)

    @log_helpers.log_method_call
    def update_acl_group(self, context, acl_group):
        """Handle RPC cast from plugin to update ACL Group."""
        id = acl_group['id']
        old_acl_group = dict()
        try:
            mgr = resource_manager.ACLGroupManager(self.lbdriver)
            mgr.update(old_acl_group, acl_group)
            LOG.debug("Finish to update acl_group %s", id)
        except Exception as ex:
            LOG.error("Fail to update loadbalancer %s "
                      "Exception: %s", id, ex.message)
