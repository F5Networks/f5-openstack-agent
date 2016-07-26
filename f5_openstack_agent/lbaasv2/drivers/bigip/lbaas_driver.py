# Copyright 2014 F5 Networks Inc.
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


class LBaaSBaseDriver(object):
    """Abstract base LBaaS Driver class for interfacing with Agent Manager """

    def __init__(self, conf):  # XXX 'conf' appears to be unused
        '''Maybe we can remove this method altogether? Or maybe it's for future

        subclassing...
        '''
        self.agent_id = None
        self.plugin_rpc = None  # XXX overridden in the only known subclass
        self.connected = False  # XXX overridden in the only known subclass
        self.service_queue = []
        self.agent_configurations = {}  # XXX overridden in subclass

    def set_context(self, context):
        """Set the global context object for the lbaas driver """
        raise NotImplementedError()

    def post_init(self):
        """Run after agent is fully connected """
        raise NotImplementedError()

    def set_tunnel_rpc(self, tunnel_rpc):  # XXX into this class?
        """Provide FDB Connector RPC access """
        raise NotImplementedError()

    def set_l2pop_rpc(self, l2pop_rpc):
        """Provide FDB Connector with L2 Population RPC access """
        raise NotImplementedError()

    def connect(self):
        """Connect backend API endpoints """
        raise NotImplementedError()

    def flush_cache(self):
        """Remove all cached items """
        raise NotImplementedError()

    def backup_configuration(self):
        """Persist backend configuratoins """
        raise NotImplementedError()

    def get_stats(self, service):
        """Get Stats for a Pool Service """
        raise NotImplementedError()

    def exists(self, service):
        """Check If LBaaS Service is Defined on Driver Target """
        raise NotImplementedError()

    def sync(self, service):
        """Force Sync a Service on Driver Target """
        raise NotImplementedError()

    def remove_orphans(self, known_services):
        """Remove Unknown Service from Driver Target """
        raise NotImplementedError()

    def create_vip(self, vip, service):
        """LBaaS Create VIP """
        raise NotImplementedError()

    def update_vip(self, old_vip, vip, service):
        """LBaaS Update VIP """
        raise NotImplementedError()

    def delete_vip(self, vip, service):
        """LBaaS Delete VIP """
        raise NotImplementedError()

    def create_pool(self, pool, service):
        """LBaaS Delete VIP """
        raise NotImplementedError()

    def update_pool(self, old_pool, pool, service):
        """LBaaS Update Pool """
        raise NotImplementedError()

    def delete_pool(self, pool, service):
        """LBaaS Delete Pool """
        raise NotImplementedError()

    def create_member(self, member, service):
        """LBaaS Create Member """
        raise NotImplementedError()

    def update_member(self, old_member, member, service):
        """LBaaS Update Member """
        raise NotImplementedError()

    def delete_member(self, member, service):
        """LBaaS Delete Member """
        raise NotImplementedError()

    def create_pool_health_monitor(self, health_monitor, pool, service):
        """LBaaS Create Pool Health Monitor """
        raise NotImplementedError()

    def update_health_monitor(self, old_health_monitor,
                              health_monitor,
                              pool,
                              service):
        """LBaaS Update Health Monitor """
        raise NotImplementedError()

    def delete_pool_health_monitor(self, health_monitor, pool, service):
        """LBaaS Delete Health Monitor """
        raise NotImplementedError()

    def tunnel_update(self, **kwargs):
        """Neutron Core Tunnel Update """
        raise NotImplementedError()

    def tunnel_sync(self):
        """Neutron Core Tunnel Sync Messages """
        raise NotImplementedError()

    def fdb_add(self, fdb_entries):
        """L2 Population FDB Add """
        raise NotImplementedError()

    def fdb_remove(self, fdb_entries):
        """L2 Population FDB Remove """
        raise NotImplementedError()

    def fdb_update(self, fdb_entries):
        """L2 Population FDB Update """
        raise NotImplementedError()
