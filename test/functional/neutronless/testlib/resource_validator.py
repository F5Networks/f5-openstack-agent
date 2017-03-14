# coding=utf-8
# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType


class ResourceValidator(object):
    def __init__(self, bigip, prefix):
        self.bigip = bigip
        self.prefix = prefix

    def assert_healthmonitor_deleted(self, monitor, folder):
        monitor_name = '{0}_{1}'.format(self.prefix, monitor['id'])
        monitor_type = self.get_monitor_type(monitor)
        assert not self.bigip.resource_exists(
            monitor_type, monitor_name, partition=folder)

    def assert_healthmonitor_valid(self, monitor, folder):
        monitor_name = '{0}_{1}'.format(self.prefix, monitor['id'])
        monitor_type = self.get_monitor_type(monitor)
        assert self.bigip.resource_exists(
            monitor_type, monitor_name, partition=folder)

    def assert_member_valid(self, pool, member, folder):
        pool_name = '{0}_{1}'.format(self.prefix, pool['id'])
        member_name = '{0}:{1}'.format(member['address'],
                                       member['protocol_port'])
        node_name = '{0}'.format(member['address'])

        assert self.bigip.member_exists(
            pool_name, member_name, partition=folder)
        assert self.bigip.resource_exists(
            ResourceType.node, node_name, partition=folder)

    def assert_pool_deleted(self, pool, member, folder):
        pool_name = '{0}_{1}'.format(self.prefix, pool['id'])
        assert not self.bigip.resource_exists(
            ResourceType.pool, pool_name, partition=folder)

        if member:
            member_name = '{0}:{1}'.format(member['address'],
                                       member['protocol_port'])

            node_name = '{0}%1'.format(member['address'])

            assert not self.bigip.member_exists(
                pool_name, member_name, partition=folder)
            assert not self.bigip.resource_exists(
                ResourceType.node, node_name, partition=folder)

    def assert_pool_valid(self, pool, folder):
        pool_name = '{0}_{1}'.format(self.prefix, pool['id'])
        assert self.bigip.resource_exists(
            ResourceType.pool, pool_name, partition=folder)

    def assert_virtual_deleted(self, listener, folder):
        listener_name = '{0}_{1}'.format(self.prefix, listener['id'])
        assert not self.bigip.resource_exists(
            ResourceType.virtual, listener_name, partition=folder)

    def assert_virtual_valid(self, listener, folder):
        listener_name = '{0}_{1}'.format(self.prefix, listener['id'])

        # created?
        assert self.bigip.resource_exists(
            ResourceType.virtual, listener_name, partition=folder)
        vs = self.bigip.get_resource(
            ResourceType.virtual, listener_name, partition=folder)

        # admin state
        assert vs.enabled == listener['admin_state_up']

        # connection limit
        connection_limit =  listener['connection_limit']
        if connection_limit == -1:
            connection_limit = 0
        assert vs.connectionLimit == connection_limit

        # description
        description = listener['description']
        if listener['name']:
            description = '{0}:{1}'.format(listener['name'], description)
        vs.description == description

        # port
        assert vs.destination.endswith(
            ':{0}'.format(listener['protocol_port']))

    def get_monitor_type(self, monitor):
        monitor_type = monitor['type']
        if monitor_type == "HTTPS":
            return ResourceType.https_monitor
        elif monitor_type == "TCP":
            return ResourceType.tcp_monitor
        elif monitor_type == "PING":
            return ResourceType.ping_monitor
        else:
            return ResourceType.http_monitor

    def assert_esd_applied(self, esd, listener, folder):
        # check that vs exists
        listener_name = '{0}_{1}'.format(self.prefix, listener['id'])
        assert self.bigip.resource_exists(
            ResourceType.virtual, listener_name, partition=folder)
        vs = self.bigip.get_resource(
            ResourceType.virtual, listener_name, partition=folder)

        profiles = vs.profiles_s.get_collection()
        policies = vs.policies_s.get_collection()

        if 'lbaas_ctcp' in esd:
            assert self.is_in_collection(profiles, esd['lbaas_ctcp'])

        if 'lbaas_stcp' in esd:
            assert self.is_in_collection(profiles, esd['lbaas_stcp'])

        if 'lbaas_cssl_profile' in esd:
            assert self.is_in_collection(profiles, esd['lbaas_cssl_profile'])

        if 'lbaas_sssl_profile' in esd:
            assert self.is_in_collection(profiles, esd['lbaas_sssl_profile'])

        if 'lbaas_persist' in esd:
            assert vs.persist[0]['name'] == esd['lbaas_persist']

        if 'lbaas_fallback_persist' in esd:
            assert vs.fallbackPersistence == \
                   '/Common/' + esd['lbaas_fallback_persist']

        if 'lbaas_irule' in esd:
            for rule in esd['lbaas_irule']:
                rule_name = '/Common/' + rule
                assert  rule_name in vs.rules

        if 'lbaas_policy' in esd:
            for policy in esd['lbaas_policy']:
                assert self.is_in_collection(policies, policy)

    def assert_esd_removed(self, esd, listener, folder):
        listener_name = '{0}_{1}'.format(self.prefix, listener['id'])
        assert self.bigip.resource_exists(
            ResourceType.virtual, listener_name, partition=folder)
        vs = self.bigip.get_resource(
            ResourceType.virtual, listener_name, partition=folder)

        profiles = vs.profiles_s.get_collection()

        if 'lbaas_ctcp' in esd:
            assert not self.is_in_collection(profiles, esd['lbaas_ctcp'])

        if 'lbaas_stcp' in esd:
            assert not self.is_in_collection(profiles, esd['lbaas_stcp'])

        if 'lbaas_cssl_profile' in esd:
            assert not self.is_in_collection(profiles,
                                             esd['lbaas_cssl_profile'])

        if 'lbaas_sssl_profile' in esd:
            assert not self.is_in_collection(profiles,
                                             esd['lbaas_sssl_profile'])

        if 'lbaas_persist' in esd:
            persist = getattr(vs, 'persist', None)
            if not persist:
                assert vs.persist[0]['name'] != esd['lbaas_persist']

        if 'lbaas_fallback_persist' in esd:
            fallback_persist = getattr(vs, 'fallbackPersistence', None)
            if fallback_persist:
                assert fallback_persist != \
                       '/Common/' + esd['lbaas_fallback_persist']

        if 'lbaas_irule' in esd:
            assert not getattr(vs, 'rules', None)

        if 'lbaas_policy' in esd:
            assert not vs.policies_s.get_collection()


    def is_in_collection(self, collection, name):
        for item in collection:
            if item.name == name:
                return True

        return False