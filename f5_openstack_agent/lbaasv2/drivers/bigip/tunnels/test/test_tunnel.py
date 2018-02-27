"""A module meant for unit testing tunnel.py

This test library hosts all things for testing Tunnel operations.
"""
# Copyright 2018 F5 Networks Inc.
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

import mock
import pytest

import f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.tunnel as target_mod

from ...test.class_tester_base_class import ClassTesterBase
from ...test.conftest import TestingWithServiceConstructor
from ...test.mock_builder_base_class import MockBuilderBase
from .test_network_cache_handler import TestNetworkCacheHandlerMockBuilder


class TestTunnelMockBuilder(MockBuilderBase):
    """Hosts a MockBuilder for Tunnels"""
    _other_builders = {
        '_TunnelHandler__network_cache_handler':
        TestNetworkCacheHandlerMockBuilder}

    @mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.tunnel.'
                'Tunnel.__init__')
    def mock_target(self, init):
        init.return_value = None
        return target_mod.TunnelHandler()

    def fully_mocked_target(self, mocked_target):
        mocked_target._CacheBase__lock_acquired = mock.Mock()
        mocked_target._CacheBase__mechanism = mock.Mock()
        mocked_target._CacheBase__workers_waiting = mock.Mock()
        mocked_target._CacheBase__workers_locks = mock.Mock()
        mocked_target._CacheBase__my_pid = 33
        super(TestTunnelMockBuilder, self).fully_mocked_target(mocked_target)
        return mocked_target


class TestTunnelHandlerMockBuilder(MockBuilderBase,
                                   TestingWithServiceConstructor):
    """Hosts a MockBuilder for TunnelHandlers"""
    _other_builders = {
        '_TunnelHandler__network_cache_handler':
        TestNetworkCacheHandlerMockBuilder}

    @mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.tunnels.tunnel.'
                'TunnelHandler.__init__')
    def mocked_target(self, init):
        init.return_value = None
        return target_mod.TunnelHandler()

    def fully_mocked_target(self, mocked_target):
        mocked_target._CacheBase__lock_acquired = mock.Mock()
        mocked_target._CacheBase__mechanism = mock.Mock()
        mocked_target._CacheBase__mechanism.__enter__ = mock.Mock()
        mocked_target._CacheBase__mechanism.__exit__ = mock.Mock()
        mocked_target.__name__ = 'TunnelHandler'
        mocked_target._CacheBase__workers_waiting = mock.Mock()
        mocked_target._CacheBase__workers_locks = mock.Mock()
        mocked_target._CacheBase__my_pid = 33
        mocked_target._TunnelHandler__pending_exists = []
        mocked_target._TunnelHandler__profiles = []
        mocked_target.logger = mock.Mock()
        mocked_target.tunnel_rpc = mock.Mock()
        mocked_target.l2pop_rpc = mock.Mock()
        mocked_target.context = mock.Mock()
        super(TestTunnelHandlerMockBuilder, self).fully_mocked_target(
            mocked_target)
        return mocked_target


class TestTunnelMocker(object):
    @pytest.fixture
    def mock_bigip(self):
        return mock.Mock()

    @pytest.fixture
    def mock_bigip_with_multipoint_vxlan_tunnel_profile(self, mock_bigip):
        multipoint = mock.Mock()
        mock_bigip.tm.net.tunnels.vxlans.vxlan.create.return_value = \
            multipoint
        mock_bigip.tm.net.tunnels.vxlans.vxlan.load.return_value = multipoint
        tm_multipoint = mock_bigip.tm.net.tunnels.vxlans.vxlan
        mock_bigip.tm_multipoint = tm_multipoint
        mock_bigip.multipoint_tunnel = multipoint
        return mock_bigip

    @pytest.fixture
    def mock_bigip_with_vxlan_tunnel(
            self, mock_bigip_with_multipoint_vxlan_tunnel_profile):
        bigip = mock_bigip_with_multipoint_vxlan_tunnel_profile
        fdb_tunnel = mock.Mock()
        tunnel = mock.Mock()
        arp = mock.Mock()
        fake_mac = 'aa:bb:cc:dd:ee:ff'
        bigip.local_ip = '192.168.10.1'
        tm_fdb_tunnel = bigip.tm.net.fdb.tunnels.tunnel
        tm_tunnel = bigip.tm.net.tunnels.tunnel
        tm_arp = bigip.tm.net.arps.arp
        fdb_tunnel.records = [{'name': fake_mac, 'endpoint': bigip.local_ip}]
        tm_fdb_tunnel.load.return_value = fdb_tunnel
        tm_fdb_tunnel.create.return_value = fdb_tunnel
        tm_tunnel.load.return_value = tunnel
        tm_tunnel.create.return_value = tunnel
        tm_arp.load.return_value = arp
        tm_arp.create.return_value = arp
        bigip.tm_fdb_tunnel = tm_fdb_tunnel
        bigip.tm_tunnel = tm_tunnel
        bigip.tm_arp = tm_arp
        bigip.arp = arp
        bigip.fdb_tunnel = fdb_tunnel
        bigip.tunnel = tunnel
        return bigip

    @pytest.fixture
    def mock_bigip_without_vxlan_fdbs(self, mock_bigip_with_vxlan_tunnel):
        bigip = mock_bigip_with_vxlan_tunnel
        bigip.tm_tunnel.exists.return_value = False
        bigip.tm_fdb_tunnel.exists.return_value = False
        bigip.tm_multipoint.exists.return_value = False
        return bigip

    @pytest.fixture
    def mock_bigip_with_vxlan_fdbs(self, mock_bigip_with_vxlan_tunnel):
        bigip = mock_bigip_with_vxlan_tunnel
        bigip.tm_tunnel.exists.return_value = True
        bigip.tm_fdb_tunnel.exists.return_value = True
        bigip.tm_multipoint.exists.return_value = True
        bigip.tm.net.fdbs.tunnels.get_collection.return_value = \
            [bigip.fdb_tunnel]
        bigip.tm.net.tunnels.tunnels.get_collection.return_value = \
            [bigip.tunnel]
        bigip.tm.net.tunnels.vxlans.get_collection.return_value = \
            [bigip.multipoint_tunnel]
        bigip.tm.net.tunnels.gres.get_collection.return_value = []
        return bigip

    @pytest.fixture
    def mock_bigip_with_vxlan_arp(self, mock_bigip_with_vxlan_fdbs):
        bigip = mock_bigip_with_vxlan_fdbs
        bigip.tm.net.arps.arp.exists.return_value = True
        bigip.tm.net.arps.get_collection.return_value = [bigip.arp]
        return bigip


class TestTunnel(ClassTesterBase, TestTunnelMocker):
    _builder = TestTunnelHandlerMockBuilder

    def test_agent_init(self, standalone_builder, fully_mocked_target,
                        mock_bigip_with_vxlan_arp):
        bigip = mock_bigip_with_vxlan_arp
        tunnel = bigip.tunnel
        tunnel.name = 'vxlan_tunnel'
        tunnel.key = '33'
        remote_address = '192.168.1.1'
        tunnel.description = \
            str('{"partition": "partition", "network_id": "network-id", '
                '"remote_address": "%s"}') % remote_address
        fdb_tunnel = bigip.fdb_tunnel
        mac = 'ma:ca:dd:re:ss:es'
        arp = bigip.arp
        arp.name = '192.168.1.6'
        arp.endpoint = mac
        record = mock.Mock()
        record.endpoint = '10.22.22.6'
        record.name = mac
        fdb_tunnel.records_s.get_collection.return_value = [record]
        target = fully_mocked_target
        multipoint_tunnel = bigip.multipoint_tunnel
        multipoint_tunnel.name = 'vxlan_multipoint'
        multipoint_tunnel.partition = 'partition'
        bigip.hostname = 'host'
        target.agent_init([bigip])
        assert bigip.tm.net.tunnels.vxlans.get_collection.call_count
        assert bigip.tm.net.tunnels.tunnels.get_collection.call_count
        assert bigip.tm.net.fdb.tunnels.tunnel.load.call_count
        assert bigip.tm.net.arps.get_collection.call_count
        assert fdb_tunnel.records_s.get_collection.call_count
        assert target._TunnelHandler__profiles
        assert \
            target._TunnelHandler__network_cache_handler.\
            _NetworkCacheHandler__network_cache
