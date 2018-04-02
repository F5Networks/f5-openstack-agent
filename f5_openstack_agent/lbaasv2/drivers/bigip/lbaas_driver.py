# Copyright (c) 2014-2018, F5 Networks, Inc.
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
    """Abstract base LBaaS Driver class for interfacing with Agent Manager."""

    def __init__(self, conf):  # XXX 'conf' appears to be unused
        """Maybe we can remove this method altogether? Or maybe it's for future.

        subclassing...
        """
        self.agent_id = None
        self.plugin_rpc = None  # XXX overridden in the only known subclass
        self.connected = False  # XXX overridden in the only known subclass
        self.service_queue = []
        self.agent_configurations = {}  # XXX overridden in subclass

    def set_context(self, context):
        """Set the global context object for the lbaas driver."""
        raise NotImplementedError()

    def set_plugin_rpc(self, plugin_rpc):
        """Provide LBaaS Plugin RPC access."""

    def set_agent_report_state(self, report_state_callback):
        """Set Agent Report State."""
        raise NotImplementedError()

    def set_tunnel_rpc(self, tunnel_rpc):
        """Provide FDB Connector RPC access."""
        raise NotImplementedError()

    def set_l2pop_rpc(self, l2pop_rpc):
        """Provide FDB Connector with L2 Population RPC access."""
        raise NotImplementedError()

    def flush_cache(self):
        """Remove all cached items."""
        raise NotImplementedError()

    def backend_integrity(self):
        """Return True, if the agent is be considered viable for services."""
        raise NotImplemented()

    def backup_configuration(self):
        """Persist backend configuratoins."""
        raise NotImplementedError()

    def generate_capacity_score(self, capacity_policy):
        """Generate the capacity score of connected devices."""
        raise NotImplemented

    def update_operating_status(self):
        """Update pool member operational status from devices to controller."""
        raise NotImplemented

    def recover_errored_devices(self):
        """Trigger attempt to reconnect any errored devices."""
        raise NotImplemented

    def get_stats(self, service):
        """Get Stats for a loadbalancer Service."""
        raise NotImplementedError()

    def get_all_deployed_loadbalancers(self, purge_orphaned_folders=True):
        """Get all Loadbalancers defined on devices."""
        raise NotImplemented

    def purge_orphaned_loadbalancer(self, tenant_id, loadbalancer_id,
                                    hostnames):
        """Remove all loadbalancers without references in Neutron."""
        raise NotImplemented

    def service_exists(self, service):
        """Check If LBaaS Service is Defined on Driver Target."""
        raise NotImplementedError()

    def sync(self, service):
        """Force Sync a Service on Driver Target."""
        raise NotImplementedError()

    def create_pool(self, pool, service):
        """LBaaS Create Pool."""
        raise NotImplementedError()

    def update_pool(self, old_pool, pool, service):
        """LBaaS Update Pool."""
        raise NotImplementedError()

    def delete_pool(self, pool, service):
        """LBaaS Delete Pool."""
        raise NotImplementedError()

    def create_member(self, member, service):
        """LBaaS Create Member."""
        raise NotImplementedError()

    def update_member(self, old_member, member, service):
        """LBaaS Update Member."""
        raise NotImplementedError()

    def delete_member(self, member, service):
        """LBaaS Delete Member."""
        raise NotImplementedError()

    def create_pool_health_monitor(self, health_monitor, pool, service):
        """LBaaS Create Pool Health Monitor."""
        raise NotImplementedError()

    def update_health_monitor(self, old_health_monitor,
                              health_monitor,
                              pool,
                              service):
        """LBaaS Update Health Monitor."""
        raise NotImplementedError()

    def delete_health_monitor(self, health_monitor, pool, service):
        """LBaaS Delete Health Monior."""
        raise NotImplementedError()

    def delete_pool_health_monitor(self, health_monitor, pool, service):
        """LBaaS Delete Health Monitor."""
        raise NotImplementedError()

    def get_all_deployed_health_monitors(self):
        """Get listing of all deployed Health Monitors"""
        raise NotImplementedError()

    def purge_orphaned_health_monitor(self, tenant_id=None, monitor_id=None,
                                      hostnames=list()):
        """LBaaS Purge Health Monitor."""
        raise NotImplementedError()

    def get_all_deployed_l7_policys(self):
        """Get listing of all deployed Health Monitors"""
        raise NotImplementedError()

    def purge_orphaned_l7_policy(self, tenant_id=None, monitor_id=None,
                                 hostnames=list()):
        """LBaaS Purge Health Monitor."""
        raise NotImplementedError()

    def tunnel_update(self, **kwargs):
        """Neutron Core Tunnel Update."""
        raise NotImplementedError()

    def tunnel_sync(self):
        """Neutron Core Tunnel Sync Messages."""
        raise NotImplementedError()

    def fdb_add(self, fdb_entries):
        """L2 Population FDB Add."""
        raise NotImplementedError()

    def fdb_remove(self, fdb_entries):
        """L2 Population FDB Remove."""
        raise NotImplementedError()

    def fdb_update(self, fdb_entries):
        """L2 Population FDB Update."""
        raise NotImplementedError()

    def create_l7policy(self, l7policy, service):
        """LBaaS Create l7policy."""
        raise NotImplementedError()

    def update_l7policy(self, old_l7policy, l7policy, service):
        """LBaaS Update l7policy."""
        raise NotImplementedError()

    def delete_l7policy(self, l7policy, service):
        """LBaaS Delete l7policy."""
        raise NotImplementedError()

    def create_l7rule(self, l7rule, service):
        """LBaaS Create l7rule."""
        raise NotImplementedError()

    def update_l7rule(self, old_l7rule, l7rule, service):
        """LBaaS Update l7rule."""
        raise NotImplementedError()

    def delete_l7rule(self, l7rule, service):
        """LBaaS Delete l7rule."""
        raise NotImplementedError()
