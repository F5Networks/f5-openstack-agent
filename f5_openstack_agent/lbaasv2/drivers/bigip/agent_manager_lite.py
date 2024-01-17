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

from datetime import datetime
from f5_openstack_agent.utils import exec_helper
from f5_openstack_agent.utils import timer
import random
import re
import sys
from time import sleep

from oslo_log import helpers as log_helpers
from oslo_log import log as logging
import oslo_messaging
from oslo_messaging.rpc.client import RemoteError
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_utils import importutils

from neutron.agent import rpc as agent_rpc
from neutron.plugins.ml2.drivers.l2pop import rpc as l2pop_rpc
try:
    from neutron_lib import context as ncontext
except ImportError:
    from neutron import context as ncontext

from f5_openstack_agent.lbaasv2.drivers.bigip import bigip_device
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import \
    ClusterManager
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip import opts
from f5_openstack_agent.lbaasv2.drivers.bigip import plugin_rpc
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_manager
from f5_openstack_agent.lbaasv2.drivers.bigip.utils import serialized

from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import \
    SystemHelper

from icontrol.exceptions import iControlUnexpectedHTTPError


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

        self.cluster_manager = ClusterManager()
        self.conf = conf
        self.context = ncontext.get_admin_context_without_session()

        # Create the cache of provisioned services
        self.cache = LogicalServiceCache()
        self.last_resync = datetime.now()
        self.needs_resync = False

        self.plugin_rpc = None
        self.tunnel_rpc = None
        self.l2_pop_rpc = None
        self.state_rpc = None
        self.system_helper = None
        self.resync_interval = conf.resync_interval
        LOG.debug('setting service resync intervl to %d seconds' %
                  self.resync_interval)

        self.service_queue_map = {"default": []}

        # Load the driver.
        self._load_driver(conf)

        # Set the agent ID
        if self.conf.agent_id:
            self.agent_host = self.conf.agent_id
            LOG.debug('setting agent host to %s' % self.agent_host)
        else:
            self.agent_host = conf.host
            LOG.debug('setting agent host to %s' % self.agent_host)

        # Initialize agent configurations
        agent_configurations = (
            {'environment_prefix': self.conf.environment_prefix}
        )

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

        cache_interval = self.conf.config_save_interval
        if cache_interval:
            config_beat = loopingcall.FixedIntervalLoopingCall(
                self._persist_config)
            config_beat.start(interval=cache_interval)

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

    def _persist_config(self):
        cache_pool_items = bigip_device.BigipDevice.cache_pool.items()
        LOG.info("Start to persist config %s." % cache_pool_items)

        if len(cache_pool_items) == 0:
            return

        for host, info in cache_pool_items:
            LOG.info(
                "Periodically persist config on device %s" %
                host
            )
            try:
                bigip = bigip_device.build_connection(
                    host, info
                )
                self.cluster_manager.save_config(bigip)
                LOG.info(
                    "Finish persist config on device %s" %
                    host
                )
                bigip_device.BigipDevice.cache_pool.pop(
                    host
                )
            except Exception as exc:
                LOG.exception(
                    "Fail to persist config on device %s."
                    "The detail is %s"
                    % (host, exc)
                )

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

    @log_helpers.log_method_call
    def occupy_device(self, context, service):
        expire = self.conf.device_lock_expire_seconds
        # Only enable device access limit when expire value > 0
        if expire <= 0:
            return

        if "device" in service:
            device_id = service["device"]["id"]
            max_wait = 180
            attempt = 0
            occupied = False
            start_time = datetime.utcnow()
            while not occupied:
                attempt += 1
                try:
                    occupied = self.plugin_rpc.occupy_device(
                        context, device_id, expire)
                except RemoteError as ex:
                    if "DeviceIsBusy" in ex.message:
                        end_time = datetime.utcnow()
                        if (end_time - start_time).total_seconds() < max_wait:
                            # Wait up to 1 second
                            interval = random.uniform(0.5, 1.0)
                            sleep(interval)
                        else:
                            LOG.error("Fail to occupy device %s "
                                      "after %s attempts: %s",
                                      device_id, attempt, ex.message)
                            raise
                    else:
                        LOG.error("Fail to occupy device %s "
                                  "after %s attempts: %s",
                                  device_id, attempt, ex.message)
                        LOG.exception(ex)
                        raise
                except Exception as ex:
                    LOG.error("Fail to occupy device %s "
                              "after %s attempts: %s",
                              device_id, attempt, ex.message)
                    LOG.exception(ex)
                    raise

    @log_helpers.log_method_call
    def release_device(self, context, service):
        expire = self.conf.device_lock_expire_seconds
        # Only enable device access limit when expire value > 0
        if expire <= 0:
            return

        if "device" in service:
            device_id = service["device"]["id"]
            max_wait = expire
            attempt = 0
            released = False
            start_time = datetime.utcnow()
            while not released:
                attempt += 1
                try:
                    released = self.plugin_rpc.release_device(context,
                                                              device_id)
                except RemoteError as ex:
                    if "DeviceIsBusy" in ex.message:
                        end_time = datetime.utcnow()
                        if (end_time - start_time).total_seconds() < max_wait:
                            # Wait up to half second
                            interval = random.uniform(0, 0.5)
                            sleep(interval)
                        else:
                            LOG.warning("Fail to release device %s "
                                        "after %s attempts: %s",
                                        device_id, attempt, ex.message)
                            # Do NOT raise exception
                            break
                    else:
                        LOG.warning("Fail to release device %s "
                                    "after %s attempts: %s",
                                    device_id, attempt, ex.message)
                        # Do NOT raise exception
                        break
                except Exception as ex:
                    LOG.warning("Fail to release device %s "
                                "after %s attempts: %s",
                                device_id, attempt, ex.message)
                    LOG.exception(ex)
                    # Do NOT raise exception
                    break

    ######################################################################
    #
    # handlers for all in bound requests and notifications from controller
    #
    ######################################################################
    @serialized('create_loadbalancer')
    @log_helpers.log_method_call
    def create_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to create_loadbalancer."""
        id = loadbalancer['id']

        try:
            self.occupy_device(context, service)
            bigip_device.set_bigips(service, self.conf)
            mgr = resource_manager.LoadBalancerManager(self.lbdriver)
            mgr.create(loadbalancer, service)
            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create loadbalancer %s", id)
        except Exception as ex:
            LOG.error("Fail to create loadbalancer %s "
                      "Exception: %s", id, ex.message)
            LOG.exception(ex)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.release_device(context, service)
                self.plugin_rpc.update_loadbalancer_status(
                    id, provision_status,
                    operating_status
                )
                LOG.info("Finish to update status of loadbalancer %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of loadbalancer %s "
                              "Exception: %s", id, ex.message)

    @serialized('update_loadbalancer')
    @log_helpers.log_method_call
    def update_loadbalancer(self, context, old_loadbalancer,
                            loadbalancer, service):
        """Handle RPC cast from plugin to update_loadbalancer."""
        id = loadbalancer['id']

        try:
            bigip_device.set_bigips(service, self.conf)
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

    @serialized('delete_loadbalancer')
    @log_helpers.log_method_call
    def delete_loadbalancer(self, context, loadbalancer, service):
        """Handle RPC cast from plugin to delete_loadbalancer."""
        id = loadbalancer['id']

        try:
            self.occupy_device(context, service)
            bigip_device.set_bigips(service, self.conf)
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
                self.release_device(context, service)
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
            bigip_device.set_bigips(service, self.conf)

            self.cache.put(service, self.agent_host)
        except f5_ex.F5NeutronException as exc:
            LOG.error("f5_ex.F5NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @serialized('create_listener')
    @log_helpers.log_method_call
    def create_listener(self, context, listener, service):
        """Handle RPC cast from plugin to create_listener."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_listener(listener, service={}):
                mgr = resource_manager.ListenerManager(self.lbdriver)
                mgr.create(listener, service)

            _create_listener(listener, service=service)

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

    @serialized('update_listener')
    @log_helpers.log_method_call
    def update_listener(self, context, old_listener, listener, service):
        """Handle RPC cast from plugin to update_listener."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _update_listener(old_listener, listener, service={}):
                mgr = resource_manager.ListenerManager(self.lbdriver)
                mgr.update(old_listener, listener, service)

            _update_listener(old_listener, listener, service=service)

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

    @serialized('delete_listener')
    @log_helpers.log_method_call
    def delete_listener(self, context, listener, service):
        """Handle RPC cast from plugin to delete_listener."""
        loadbalancer = service['loadbalancer']
        id = listener['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_listener(listener, service={}):
                mgr = resource_manager.ListenerManager(self.lbdriver)
                mgr.delete(listener, service)

            _delete_listener(listener, service=service)

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

    @serialized('create_pool')
    @log_helpers.log_method_call
    @timer.timeit
    def create_pool(self, context, pool, service):
        """Handle RPC cast from plugin to create_pool."""
        loadbalancer = service['loadbalancer']
        id = pool['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_pool(pool, service={}):
                mgr = resource_manager.PoolManager(self.lbdriver)
                mgr.create(pool, service)

            _create_pool(pool, service=service)

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

    @serialized('update_pool')
    @log_helpers.log_method_call
    @timer.timeit
    def update_pool(self, context, old_pool, pool, service):
        """Handle RPC cast from plugin to update_pool."""
        loadbalancer = service['loadbalancer']
        id = pool['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _update_pool(old_pool, pool, service={}):
                # TODO(qzhao): Deploy config to BIG-IP
                mgr = resource_manager.PoolManager(self.lbdriver)
                mgr.update(old_pool, pool, service)

            _update_pool(old_pool, pool, service=service)

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

    @serialized('delete_pool')
    @log_helpers.log_method_call
    @timer.timeit
    def delete_pool(self, context, pool, service):
        """Handle RPC cast from plugin to delete_pool."""
        loadbalancer = service['loadbalancer']
        id = pool['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_pool(pool, service={}):
                mgr = resource_manager.PoolManager(self.lbdriver)
                mgr.delete(pool, service)

            _delete_pool(pool, service=service)

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

    @serialized('create_member')
    @log_helpers.log_method_call
    def create_member(
        self, context, member, service,
    ):
        """Handle RPC cast from plugin to create_member."""

        loadbalancer = service['loadbalancer']
        id = member['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_member(member, service={}):
                mgr = resource_manager.MemberManager(self.lbdriver)
                mgr.create(member, service)

            _create_member(member, service=service)

            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
            LOG.debug("Finish to create member %s", id)
        except Exception as ex:
            LOG.error("Fail to create member %s "
                      "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_member_status(
                    id, provision_status, operating_status
                )

                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of member %s", id)
            except Exception as ex:
                LOG.exception("Fail to update status of member %s "
                              "Exception: %s", id, ex.message)

    @serialized('create_bulk_member')
    @log_helpers.log_method_call
    def create_bulk_member(
        self, context, members, service,
    ):
        """Handle RPC cast from plugin to create_member."""
        loadbalancer = service['loadbalancer']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_bulk_member(members, service={}):
                mgr = resource_manager.MemberManager(self.lbdriver)
                mgr.create_bulk(members, service)

            _create_bulk_member(members, service=service)

            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE

            LOG.debug("Finish to create multiple members")
        except Exception as ex:
            LOG.error("Fail to create multiple members "
                      "Exception: %s", ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                for m in members:
                    self.plugin_rpc.update_member_status(
                        m['id'], provision_status, operating_status
                    )

                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of multiple members")

            except Exception as ex:
                LOG.exception("Fail to update status of multiple members "
                              "Exception: %s", ex.message)

    @serialized('update_member')
    @log_helpers.log_method_call
    def update_member(self, context, old_member, member, service):
        """Handle RPC cast from plugin to update_member."""
        loadbalancer = service['loadbalancer']
        id = member['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _update_member(old_member, member, service={}):
                mgr = resource_manager.MemberManager(self.lbdriver)
                mgr.update(old_member, member, service)

            _update_member(old_member, member, service=service)

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

    @serialized('delete_member')
    @log_helpers.log_method_call
    def delete_member(self, context, member, service):
        """Handle RPC cast from plugin to delete_member."""

        loadbalancer = service['loadbalancer']
        id = member['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_member(member, service={}):
                mgr = resource_manager.MemberManager(self.lbdriver)
                mgr.delete(member, service)

            _delete_member(member, service=service)

            provision_status = constants_v2.F5_ACTIVE
            LOG.debug("Finish to delete member %s", id)
        except f5_ex.ProjectIDException as ex:
            LOG.debug("Delete Member with ProjectIDException")
            provision_status = constants_v2.F5_ACTIVE
        except Exception as ex:
            LOG.error("Fail to delete member %s "
                      "Exception: %s", id, ex.message)
            provision_status = constants_v2.F5_ERROR
        finally:
            try:
                if provision_status == constants_v2.F5_ACTIVE:
                    self.plugin_rpc.member_destroyed(member['id'])
                else:
                    self.plugin_rpc.update_member_status(
                        member['id'], provision_status,
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

    @serialized('delete_bulk_member')
    @log_helpers.log_method_call
    def delete_bulk_member(
        self, context, members, service,
    ):
        """Handle RPC cast from plugin to delete members."""
        loadbalancer = service['loadbalancer']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_bulk_member(members, service={}):
                mgr = resource_manager.MemberManager(self.lbdriver)
                mgr.delete_bulk(members, service)

            _delete_bulk_member(members, service=service)

            provision_status = constants_v2.F5_ACTIVE

            # when delete succeed the member should be offline?
            operating_status = constants_v2.F5_ONLINE

            for mb in members:
                self.plugin_rpc.member_destroyed(mb['id'])

            LOG.debug("Finish to delete multiple members")
        except Exception as ex:
            LOG.error("Fail to delete multiple members "
                      "Exception: %s", ex.message)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE

            # update operating status for members,
            # only when delete error happens ?
            for m in members:
                self.plugin_rpc.update_member_status(
                    m['id'], provision_status, operating_status
                )
        finally:
            try:
                self.plugin_rpc.update_loadbalancer_status(
                    loadbalancer['id'], provision_status,
                    loadbalancer['operating_status']
                )
                LOG.info("Finish to update status of multiple members")

            except Exception as ex:
                LOG.exception("Fail to update status of multiple members "
                              "Exception: %s", ex.message)

    @serialized('create_health_monitor')
    @log_helpers.log_method_call
    @timer.timeit
    def create_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to create_pool_health_monitor."""
        loadbalancer = service['loadbalancer']
        id = health_monitor['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_health_monitor(health_monitor, service={}):
                mgr = resource_manager.MonitorManager(
                    self.lbdriver, type=health_monitor['type']
                )
                mgr.create(health_monitor, service)

            _create_health_monitor(health_monitor, service=service)

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

    @serialized('update_health_monitor')
    @log_helpers.log_method_call
    @timer.timeit
    def update_health_monitor(self, context, old_health_monitor,
                              health_monitor, service):
        """Handle RPC cast from plugin to update_health_monitor."""
        loadbalancer = service['loadbalancer']
        id = health_monitor['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _update_health_monitor(old_health_monitor,
                                       health_monitor, service={}):
                mgr = resource_manager.MonitorManager(
                    self.lbdriver, type=health_monitor['type']
                )
                mgr.update(old_health_monitor, health_monitor, service)

            _update_health_monitor(old_health_monitor,
                                   health_monitor, service=service)

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

    @serialized('delete_health_monitor')
    @log_helpers.log_method_call
    @timer.timeit
    def delete_health_monitor(self, context, health_monitor, service):
        """Handle RPC cast from plugin to delete_health_monitor."""
        loadbalancer = service['loadbalancer']
        id = health_monitor['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_health_monitor(health_monitor, service={}):
                mgr = resource_manager.MonitorManager(
                    self.lbdriver, type=health_monitor['type']
                )
                mgr.delete(health_monitor, service)

            _delete_health_monitor(health_monitor, service=service)

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

    @serialized('create_l7policy')
    @log_helpers.log_method_call
    def create_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to create_l7policy."""
        loadbalancer = service['loadbalancer']
        id = l7policy['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_l7policy(l7policy, service={}):
                mgr = resource_manager.L7PolicyManager(self.lbdriver)
                mgr.create(l7policy, service)

            _create_l7policy(l7policy, service=service)

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

    @serialized('update_l7policy')
    @log_helpers.log_method_call
    def update_l7policy(self, context, old_l7policy, l7policy, service):
        """Handle RPC cast from plugin to update_l7policy."""
        loadbalancer = service['loadbalancer']
        id = l7policy['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _update_l7policy(old_l7policy, l7policy, service={}):
                mgr = resource_manager.L7PolicyManager(self.lbdriver)
                mgr.update(old_l7policy, l7policy, service)

            _update_l7policy(old_l7policy, l7policy, service=service)

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

    @serialized('delete_l7policy')
    @log_helpers.log_method_call
    def delete_l7policy(self, context, l7policy, service):
        """Handle RPC cast from plugin to delete_l7policy."""
        loadbalancer = service['loadbalancer']
        id = l7policy['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_l7policy(l7policy, service={}):
                mgr = resource_manager.L7PolicyManager(self.lbdriver)
                mgr.delete(l7policy, service)

            _delete_l7policy(l7policy, service=service)

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

    @serialized('create_l7rule')
    @log_helpers.log_method_call
    def create_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to create_l7rule."""
        loadbalancer = service['loadbalancer']
        id = l7rule['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _create_l7rule(l7rule, service={}):
                mgr = resource_manager.L7RuleManager(self.lbdriver)
                mgr.create(l7rule, service)

            _create_l7rule(l7rule, service=service)

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

    @serialized('update_l7rule')
    @log_helpers.log_method_call
    def update_l7rule(self, context, old_l7rule, l7rule, service):
        """Handle RPC cast from plugin to update_l7rule."""
        loadbalancer = service['loadbalancer']
        id = l7rule['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _update_l7rule(old_l7rule, l7rule, service=service):
                mgr = resource_manager.L7RuleManager(self.lbdriver)
                mgr.update(old_l7rule, l7rule, service)

            _update_l7rule(old_l7rule, l7rule, service=service)

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

    @serialized('delete_l7rule')
    @log_helpers.log_method_call
    def delete_l7rule(self, context, l7rule, service):
        """Handle RPC cast from plugin to delete_l7rule."""
        loadbalancer = service['loadbalancer']
        id = l7rule['id']

        try:
            bigip_dev = bigip_device.BigipDevice(service['device'], self.conf)
            allbips = bigip_dev.get_all_bigips()

            @exec_helper.On(allbips)
            def _delete_l7rule(l7rule, service={}):
                # TODO(qzhao): Deploy config to BIG-IP
                mgr = resource_manager.L7RuleManager(self.lbdriver)
                mgr.delete(l7rule, service)

            _delete_l7rule(l7rule, service=service)

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

    @serialized('create_acl_group')
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

    @serialized('delete_acl_group')
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

    @serialized('update_acl_group')
    @log_helpers.log_method_call
    def update_acl_group(self, context, acl_group, service):
        """Handle RPC cast from plugin to update ACL Group."""
        id = acl_group['id']
        old_acl_group = dict()
        try:
            bigip_device.set_bigips(service, self.conf)
            mgr = resource_manager.ACLGroupManager(self.lbdriver)
            mgr.update(old_acl_group, acl_group, service)
            LOG.debug("Finish to update acl_group %s", id)
        except Exception as ex:
            LOG.exception("Fail to update acl group %s.\n"
                          "Exception: %s\n" % (
                              acl_group, str(ex)
                          ))
            raise ex

    @serialized('add_acl_bind')
    @log_helpers.log_method_call
    def add_acl_bind(self, context, listener,
                     acl_group, acl_bind, service):
        """Handle RPC cast from plugin to update_acl_bind."""

        # create acl data group on each bigips first
        acl_id = acl_group['id']
        listener_id = listener['id']

        try:
            # create acl data group on each bigips first
            bigip_device.set_bigips(service, self.conf)
            mgr = resource_manager.ACLGroupManager(self.lbdriver)
            mgr.create(acl_group, service)
            LOG.debug("Finish to create data group of acl group %s",
                      acl_id)

            # create acl irule on each bigips
            mgr = resource_manager.ListenerManager(self.lbdriver)
            mgr.update_acl_bind(listener, acl_bind, service)
            LOG.debug("Finish to add ACL bind irule of listener %s",
                      listener_id)
        except Exception as ex:
            LOG.exception("Fail to add acl bind of listener.\n"
                          "Exception: %s\n"
                          "Binding details:\n Listener: %s\n"
                          "ACL binding: %s \n"
                          "ACL group: %s \n" % (
                              str(ex), listener, acl_bind, acl_group
                          ))
            raise ex

    @serialized('remove_acl_bind')
    @log_helpers.log_method_call
    def remove_acl_bind(self, context, listener,
                        acl_group, acl_bind, service):
        """Handle RPC cast from plugin to update_acl_bind."""

        # create acl irule on each bigips
        listener_id = listener['id']
        acl_id = acl_group['id']

        try:
            bigip_device.set_bigips(service, self.conf)

            # set acl_bind enabled False to remove irules
            acl_bind["enabled"] = False

            mgr = resource_manager.ListenerManager(self.lbdriver)
            mgr.update_acl_bind(listener, acl_bind, service)
            LOG.debug(
                "Finish to remove ACL bind irule of listener %s",
                listener_id
            )

            # delete acl data group on each bigips
            mgr = resource_manager.ACLGroupManager(self.lbdriver)
            mgr.try_delete(acl_group, service)
            LOG.debug("Finish to remove acl_group %s", acl_id)
        except Exception as ex:
            LOG.exception("Fail to remove acl bind of listener.\n"
                          "Exception: %s\n"
                          "Binding details:\n Listener: %s\n"
                          "ACL binding: %s \n"
                          "ACL group: %s \n" % (
                              str(ex), listener, acl_bind, acl_group
                          ))
            raise ex

    @serialized('rebuild_loadbalancer')
    @log_helpers.log_method_call
    def rebuild_loadbalancer(self, context, loadbalancer, service):

        lb_id = loadbalancer['id']
        listeners = service.get("listeners", [])
        pools = service.get('pools', [])
        monitors = service.get("healthmonitors", [])
        l7policies = service.get("l7policies", [])

        # For 'reuse the create code', the order of rebuild is important
        # pool is needs by all resource when rebuild.
        # The Pool rebuild is not dependent on any other process, except
        # loadbalancer.
        # Listener needs pool:
        # 1. if a listener and its default pool are both absent,
        #    the pool must rebuild first, since the listener rebuild
        #    wil configure its default pool.
        # 2. if a listener is absent, the default pool of listener
        #    must exist.
        # Member needs pool:
        # 1. if member and pool are both absent, the pool must rebuild
        #    first, since the member needs the pool eixsts for updating
        #    the pool member in member create process.
        # 2. if a member is absent, the pool must exist for updating
        #    the pool member.
        # Monitor is the same as the member.

        try:
            bigip_device.set_bigips(service, self.conf)

            mgr = resource_manager.LoadBalancerManager(self.lbdriver)
            mgr.create(loadbalancer, service)
            LOG.debug("Finish to create loadbalancer %s", lb_id)

            for pl in pools:
                pl_id = pl['id']
                service['pool'] = pl

                mgr = resource_manager.PoolManager(self.lbdriver)
                mgr.create(pl, service)
                LOG.debug("Finish to create pool %s", pl_id)

                mgr = resource_manager.MemberManager(self.lbdriver)
                mgr.rebuild(pl, service)
                LOG.debug(
                    "Finish to create all the members of the pool %s", pl_id)

            for lstn in listeners:
                ls_id = lstn['id']
                service['listener'] = lstn

                mgr = resource_manager.ListenerManager(self.lbdriver)
                mgr.create(lstn, service)
                LOG.debug("Finish to create listener %s", ls_id)

                acl_group = lstn.get("acl_group")
                acl_bind = lstn.get("acl_group_bind")
                if acl_group and acl_bind:
                    # set base resource
                    service['acl_group'] = acl_group

                    acl_mgr = resource_manager.ACLGroupManager(self.lbdriver)
                    acl_mgr.create(acl_group, service)

                    LOG.debug("Finish to create data group of acl group %s",
                              acl_group['id'])

                    mgr.update_acl_bind(lstn, acl_bind, service)
                    LOG.debug("Finish to add ACL bind irule of listener %s",
                              ls_id)

            for mn in monitors:
                mn_id = mn['id']
                service["healthmonitor"] = mn

                mgr = resource_manager.MonitorManager(
                    self.lbdriver, type=mn['type'])
                mgr.create(mn, service)
                LOG.debug("Finish to create monitor %s", mn_id)

            # a l7policy contains l7rules, no need to rebuild l7rule.
            for plc in l7policies:
                plc_id = plc['id']
                service["l7policy"] = plc

                mgr = resource_manager.L7PolicyManager(self.lbdriver)
                mgr.create(plc, service)
                LOG.debug("Finish to create l7policy %s", plc_id)

            provision_status = constants_v2.F5_ACTIVE
            operating_status = constants_v2.F5_ONLINE
        except Exception as ex:
            LOG.error("Fail to rebuild loadbalancer %s ", lb_id)
            LOG.exception(ex)
            provision_status = constants_v2.F5_ERROR
            operating_status = constants_v2.F5_OFFLINE
        finally:
            try:
                self.plugin_rpc.update_loadbalancer_status(
                    lb_id, provision_status,
                    operating_status
                )
                LOG.info(
                    "Finish to update status of loadbalancer %s",
                    lb_id
                )
            except Exception as ex:
                LOG.exception(
                    "Fail to update status of loadbalancer %s "
                    "Exception: %s", lb_id, ex.message
                )
