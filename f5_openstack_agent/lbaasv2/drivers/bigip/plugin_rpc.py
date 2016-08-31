"""RPC API for calls back to the plugin."""
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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging
import oslo_messaging as messaging

from neutron.common import rpc
from neutron.plugins.common import constants as plugin_const
from neutron_lbaas.services.loadbalancer import constants as lb_const

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as constants

LOG = logging.getLogger


class LBaaSv2PluginRPC(object):
    """Client interface for agent to plugin RPC."""

    RPC_API_NAMESPACE = None

    def __init__(self, topic, context, env, group, host):
        """Initialize LBaaSv2PluginRPC."""
        super(LBaaSv2PluginRPC, self).__init__()

        if topic:
            self.topic = topic
        else:
            self.topic = constants.TOPIC_PROCESS_ON_HOST_V2

        self.target = messaging.Target(topic=self.topic,
                                       version=constants.RPC_API_VERSION)
        self._client = rpc.get_client(self.target, version_cap=None)

        self.context = context
        self.env = env
        self.group = group
        self.host = host

    def _make_msg(self, method, **kwargs):
        return {'method': method,
                'namespace': self.RPC_API_NAMESPACE,
                'args': kwargs}

    def _call(self, context, msg, **kwargs):
        return self.__call_rpc_method(context,
                                      msg,
                                      rpc_method='call',
                                      **kwargs)

    def _cast(self, context, msg, **kwargs):
        self.__call_rpc_method(context,
                               msg,
                               rpc_method='cast',
                               **kwargs)

    def _fanout_cast(self, context, msg, **kwargs):
        kwargs['fanout'] = True
        self.__call_rpc_method(context, msg, rpc_method='cast', **kwargs)

    def __call_rpc_method(self, context, msg, **kwargs):
        options = dict(
            ((opt, kwargs[opt])
             for opt in ('fanout', 'timeout', 'topic', 'version')
             if kwargs.get(opt))
        )
        if msg['namespace']:
            options['namespace'] = msg['namespace']

        if options:
            callee = self._client.prepare(**options)
        else:
            callee = self._client

        func = getattr(callee, kwargs['rpc_method'])
        return func(context, msg['method'], **msg['args'])

    @log_helpers.log_method_call
    def update_loadbalancer_status(self,
                                   lb_id,
                                   provisioning_status=plugin_const.ERROR,
                                   operating_status=lb_const.OFFLINE):
        """Update the database with loadbalancer status."""
        return self._cast(
            self.context,
            self._make_msg('update_loadbalancer_status',
                           loadbalancer_id=lb_id,
                           status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def loadbalancer_destroyed(self, loadbalancer_id):
        """Delete the loadbalancer from the database."""
        return self._cast(
            self.context,
            self._make_msg('loadbalancer_destroyed',
                           loadbalancer_id=loadbalancer_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_listener_status(self,
                               listener_id,
                               provisioning_status=plugin_const.ERROR,
                               operating_status=lb_const.OFFLINE):
        """Update the database with listener status."""
        return self._cast(
            self.context,
            self._make_msg('update_listener_status',
                           listener_id=listener_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def listener_destroyed(self, listener_id):
        """Delete listener from database."""
        return self._cast(
            self.context,
            self._make_msg('listener_destroyed',
                           listener_id=listener_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_pool_status(self,
                           pool_id,
                           provisioning_status=plugin_const.ERROR,
                           operating_status=lb_const.OFFLINE):
        """Update the database with pool status."""
        return self._cast(
            self.context,
            self._make_msg('update_pool_status',
                           pool_id=pool_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def pool_destroyed(self, pool_id):
        """Delete pool from database."""
        return self._cast(
            self.context,
            self._make_msg('pool_destroyed',
                           pool_id=pool_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_member_status(self,
                             member_id,
                             provisioning_status=plugin_const.ERROR,
                             operating_status=lb_const.OFFLINE):
        """Update the database with member status."""
        return self._cast(
            self.context,
            self._make_msg('update_member_status',
                           member_id=member_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def member_destroyed(self, member_id):
        """Delete member from database."""
        return self._cast(
            self.context,
            self._make_msg('member_destroyed',
                           member_id=member_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_health_monitor_status(
            self,
            health_monitor_id,
            provisioning_status=plugin_const.ERROR,
            operating_status=lb_const.OFFLINE):
        """Update the database with health_monitor status."""
        return self._cast(
            self.context,
            self._make_msg('update_health_monitor_status',
                           health_monitor_id=health_monitor_id,
                           provisioning_status=provisioning_status,
                           operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def health_monitor_destroyed(self, healthmonitor_id):
        """Delete health_monitor from database."""
        return self._cast(
            self.context,
            self._make_msg('healthmonitor_destroyed',
                           healthmonitor_id=healthmonitor_id),
            topic=self.topic
        )

    # for L3 binding
    @log_helpers.log_method_call
    def add_allowed_address(self, port_id=None, ip_address=None):
        """Add allowed address to the port."""
        return self._call(
            self.context,
            self._make_msg('add_allowed_address',
                           port_id=port_id,
                           ip_address=ip_address),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def remove_allowed_address(self, port_id=None, ip_address=None):
        """Remove allowed address on the port."""
        return self._call(
            self.context,
            self._make_msg('remove_allowed_address',
                           port_id=port_id,
                           ip_address=ip_address),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def get_ports_for_mac_addresses(self, mac_addresses=None):
        """Get a list of ports that correspond to the mac addrs."""
        ports = []
        try:
            ports = self._call(
                self.context,
                self._make_msg('get_ports_for_mac_addresses',
                               mac_addresses=mac_addresses),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_ports_for_mac_addresses")

        return ports

    @log_helpers.log_method_call
    def get_ports_on_network(self, network_id=None):
        """Get a list of ports on the network."""
        return self._call(
            self.context,
            self._make_msg('get_ports_on_network',
                           network_id=network_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def get_port_by_name(self, port_name=None):
        """Get a list of ports that have the name port_name."""
        ports = []
        try:
            ports = self._call(
                self.context,
                self._make_msg('get_port_by_name',
                               port_name=port_name),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_port_by_name")

        return ports

    @log_helpers.log_method_call
    def create_port_on_subnet(self, subnet_id=None,
                              mac_address=None, name=None,
                              fixed_address_count=1):
        """Add a neutron port to the subnet."""
        port = None
        try:
            port = self._call(
                self.context,
                self._make_msg('create_port_on_subnet',
                               subnet_id=subnet_id,
                               mac_address=mac_address,
                               name=name,
                               fixed_address_count=fixed_address_count,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: "
                      "create_port_on_subnet")

        return port

    @log_helpers.log_method_call
    def create_port_on_subnet_with_specific_ip(self, subnet_id=None,
                                               mac_address=None,
                                               name=None,
                                               ip_address=None):
        """Add a neutron port to the subnet with given IP."""
        port = None
        try:
            port = self._call(
                self.context,
                self._make_msg('create_port_on_subnet_with_specific_ip',
                               subnet_id=subnet_id,
                               mac_address=mac_address,
                               name=name,
                               ip_address=ip_address,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: "
                      "create_port_on_subnet_with_specific_ip")

        return port

    @log_helpers.log_method_call
    def delete_port_by_name(self, port_name=None):
        """Delete ports with the given name."""
        try:
            return self._cast(
                self.context,
                self._make_msg('delete_port_by_name',
                               port_name=port_name),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: "
                      "delet_port_by_name")

    @log_helpers.log_method_call
    def delete_port(self, port_id=None, mac_address=None):
        """Delete port with the given port_id."""
        return self._cast(
            self.context,
            self._make_msg('delete_port',
                           port_id=port_id,
                           mac_address=mac_address),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def get_service_by_loadbalancer_id(self,
                                       loadbalancer_id=None):
        """Retrieve the service definition for this loadbalancer."""
        service = {}
        try:
            service = self._call(
                self.context,
                self._make_msg('get_service_by_loadbalancer_id',
                               loadbalancer_id=loadbalancer_id,
                               host=self.host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_service_by_loadbalancer_id")

        return service

    @log_helpers.log_method_call
    def get_all_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of loadbalancers in Neutron."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_all_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_all_loadbalancers")

        return loadbalancers

    @log_helpers.log_method_call
    def get_active_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of active loadbalancers for this agent."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_active_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_all_loadbalancers")

        return loadbalancers

    @log_helpers.log_method_call
    def get_pending_loadbalancers(self, env=None, group=None, host=None):
        """Retrieve a list of pending loadbalancers for this agent."""
        loadbalancers = []

        if not env:
            env = self.env

        try:
            loadbalancers = self._call(
                self.context,
                self._make_msg('get_pending_loadbalancers',
                               env=env,
                               group=group,
                               host=host),
                topic=self.topic
            )
        except messaging.MessageDeliveryFailure:
            LOG.error("agent->plugin RPC exception caught: ",
                      "get_all_loadbalancers")

        return loadbalancers
