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

from neutron.common.rpc import get_client

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as constants

LOG = logging.getLogger


class LBaaSv2PluginRPC(object):

    RPC_API_NAMESPACE = None

    def __init__(self, topic, context, env, group, host):
        super(LBaaSv2PluginRPC, self).__init__()

        if topic:
            self.topic = topic
        else:
            self.topic = constants.TOPIC_PROCESS_ON_HOST_V2

        self.target = messaging.Target(topic=self.topic,
                                       version=constants.RPC_API_VERSION)
        self._client = get_client(self.target, version_cap=None)

        self.context = context
        self.env = env
        self.group = group
        self.host = host

    def make_msg(self, method, **kwargs):
        return {'method': method,
                'namespace': self.RPC_API_NAMESPACE,
                'args': kwargs}

    def call(self, context, msg, **kwargs):
        return self.__call_rpc_method(
            context, msg, rpc_method='call', **kwargs)

    def cast(self, context, msg, **kwargs):
        self.__call_rpc_method(context, msg, rpc_method='cast', **kwargs)

    def fanout_cast(self, context, msg, **kwargs):
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
    def assure_service(self, context, service, agent):
        return self.cast(
            context,
            self.make_msg('assure_service', service=service),
            topic='%s.%s' % (self.topic, agent['host'])
        )

    @log_helpers.log_method_call
    def service_stats(self, context, service, agent):
        return self.cast(
            context,
            self.make_msg('service_stats', service=service),
            topic='%s.%s' % (self.topic, agent['host'])
        )

    @log_helpers.log_method_call
    def update_loadbalancer_status(self,
                                   lb_id,
                                   provisioning_status,
                                   operating_status):
        return self.cast(
            self.context,
            self.make_msg('update_loadbalancer_status',
                          loadbalancer_id=lb_id,
                          status=provisioning_status,
                          operating_status=operating_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def loadbalancer_destroyed(self, loadbalancer_id):
        return self.cast(
            self.context,
            self.make_msg('loadbalancer_destroyed',
                          loadbalancer_id=loadbalancer_id),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def update_listener_status(self,
                               listener_id,
                               provisioning_status):
        return self.cast(
            self.context,
            self.make_msg('update_listener_status',
                          listener_id=listener_id,
                          provisioning_status=provisioning_status),
            topic=self.topic
        )

    @log_helpers.log_method_call
    def listener_destroyed(self, listener_id):
        return self.cast(
            self.context,
            self.make_msg('listener_destroyed',
                          listener_id=listener_id),
            topic=self.topic
        )
