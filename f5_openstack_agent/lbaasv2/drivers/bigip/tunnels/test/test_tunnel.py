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
from .test_fdb_builder import TestFdbMockBuilder
from .test_network_cache_handler import TestNetworkCacheHandlerMockBuilder


class TestTunnelMockBuilder(MockBuilderBase):
    """Hosts a MockBuilder for Tunnels"""
    _other_builders = {}

    @mock.patch("{}.Tunnel.__init__".format(target_mod.__name__))
    def mocked_target(self, init):
        """Creates a mocked Tunnel object"""
        init.return_value = None
        return target_mod.Tunnel(1, 2, 3, 4, 5, 6, 7)

    def fully_mocked_target(self, mocked_target):
        """Creates a fully-mocked Tunnel object"""
        mocked_target._CacheBase__lock_acquired = mock.Mock()
        mechanism = mock.Mock()
        mechanism.__exit__ = mock.Mock()
        mechanism.__enter__ = mock.Mock()
        mechanism.__enter__.return_value = mechanism
        mocked_target._CacheBase__mechanism = mechanism
        mocked_target._CacheBase__workers_waiting = mock.Mock()
        mocked_target._CacheBase__workers_locks = mock.Mock()
        mocked_target._CacheBase__my_pid = 33
        mocked_target._Tunnel__local_address = '192.168.1.1'
        mocked_target._Tunnel__remote_address = '10.22.22.1'
        mocked_target._Tunnel__bigip_host = 'host'
        mocked_target._Tunnel__segment_id = 33
        mocked_target._Tunnel__tunnel_type = 'vxlan'
        mocked_target._Tunnel__partition = 'vxlan'
        mocked_target._Tunnel__exists = False
        mocked_target._Tunnel__fdbs = []
        mocked_target.logger = mock.Mock()
        return mocked_target

    def set_partition(self, target, partition):
        """Sets the partition on the target Tunnel object"""
        target._Tunnel__partition = partition

    def set_network_id(self, target, network_id):
        """Sets the network_id on the target Tunnel object"""
        target._Tunnel__network_id = network_id

    def add_fdb(self, target, fdb):
        """Bypasses production in adding an fdb to the provided target"""
        target._Tunnel__fdbs.append(fdb)


class TestTunnelHandlerMockBuilder(MockBuilderBase,
                                   TestingWithServiceConstructor):
    """Hosts a MockBuilder for TunnelHandlers"""
    _other_builders = {
        '_TunnelHandler__network_cache_handler':
        TestNetworkCacheHandlerMockBuilder}

    @mock.patch("{}.TunnelHandler.__init__".format(target_mod.__name__))
    def mocked_target(self, init):
        """Creates a mocked TunnelHandler"""
        init.return_value = None
        return target_mod.TunnelHandler()

    def fully_mocked_target(self, mocked_target):
        """Creates a fully mocked TunnelHandler"""
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

    def add_pending_exists(self, target, tunnel):
        """Adds a tunnel to the pending_exists array on the target"""
        target._TunnelHandler__pending_exists.append(tunnel)


class TestTunnelMocker(object):
    @pytest.fixture
    def mock_bigip(self):
        """Creates a mock BIG-IP"""
        return mock.Mock()

    @pytest.fixture
    def tunnel_mock_builder(self):
        """Establishes a test-instance based TestTunnelMockBuilder"""
        self.tunnel_builder = TestTunnelMockBuilder()
        return self.tunnel_builder

    @pytest.fixture
    def fully_mocked_tunnel(self, tunnel_mock_builder):
        """Creates and returns a fully-mocked Tunnel object"""
        return tunnel_mock_builder.new_fully_mocked_target()

    @pytest.fixture
    def fdb_mock_builder(self):
        """Establishes a test-instance based FdbMockBuilder"""
        self.fdb_builder = TestFdbMockBuilder()
        return self.fdb_builder

    @pytest.fixture
    def fully_mocked_fdb(self, fdb_mock_builder):
        return fdb_mock_builder.new_fully_mocked_target()

    @pytest.fixture
    def mock_bigip_with_multipoint_vxlan_tunnel_profile(self, mock_bigip):
        """Creates a mock multipoint vxlan tunnel on a mock BIG-IP

        Shortcuts:
            mock_bigip.multipoint_tunnel is
                mock_bigip.tm.net.tunnels.vxlans.vxlan.load()
            mock_bigip.tm_multipoint is
                mock_bigip.tm.net.tunnels.vxlans.vxlan
        """
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
        """Makes referencing tunnel access points on a bigip mock easier

        Shortcuts:
            mock_bigip.tm_fdb_tunnel is mock_bigip.tm.net.fdb.tunnels.tunnel
            mock_bigip.fdb_tunnel is
                mock_bigip.tm.net.fdb.tunnels.tunnel.load()
            mock_bigip.tm_tunnel is mock_bigip.tm.net.tunnels.tunnels.tunnel
            mock_bigip.tunnel is
                mock_bigip.tm.net.tunnels.tunnels.tunnel.load()
            mock_bigip.arp is
                mock_bigip.tm.net.arps.arp.load()
            mock_bigip.tm_arp is
                mock_bigip.tm.net.arps.arp
        """
        bigip = mock_bigip_with_multipoint_vxlan_tunnel_profile
        fdb_tunnel = mock.Mock()
        tunnel = mock.Mock()
        arp = mock.Mock()
        fake_mac = 'aa:bb:cc:dd:ee:ff'
        bigip.local_ip = '192.168.10.1'
        tm_fdb_tunnel = bigip.tm.net.fdb.tunnels.tunnel
        tm_tunnel = bigip.tm.net.tunnels.tunnels.tunnel
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
        """Dopes a BIG-IP without an fdb tunnel for easy access

        Places existential returns as False
        """
        bigip = mock_bigip_with_vxlan_tunnel
        bigip.tm_tunnel.exists.return_value = False
        bigip.tm_fdb_tunnel.exists.return_value = False
        bigip.tm_multipoint.exists.return_value = False
        return bigip

    @pytest.fixture
    def mock_bigip_with_vxlan_fdbs(self, mock_bigip_with_vxlan_tunnel):
        """Dopes a BIG-IP with all necessary vxlan fdb tunnel levels

        Places existential returns as True for tunnels and multipoint profiles
        Places [object] get_collection returns for ""
        """
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
        """Dopes a BIG-IP with all necessary ARP levels

        Places existential returns as True for arp
        Places [object] get_collection returns for arp
        """
        bigip = mock_bigip_with_vxlan_fdbs
        bigip.tm.net.arps.arp.exists.return_value = True
        bigip.tm.net.arps.get_collection.return_value = [bigip.arp]
        return bigip


class TestTunnel(ClassTesterBase, TestTunnelMocker):
    _builder = TestTunnelHandlerMockBuilder

    def test_agent_init(self, standalone_builder, fully_mocked_target,
                        mock_bigip_with_vxlan_arp):
        """This populates the network cache via agent's init

        This test will test the auto-doping of the network cache from what is
        stored on the BIG-IP.  This unit tests is a standalone test; however,
        it simulates what the SDK's ManagementRoot object would do.  Thus,
        this test should be quite close to a functional test in this arena.
        """
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
        fdb_tunnel.records = [record]
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
        assert target._TunnelHandler__profiles
        assert \
            target._TunnelHandler__network_cache_handler.\
            _NetworkCacheHandler__network_cache

    def test_bb_tunnel_remove(self, standalone_builder, fully_mocked_target,
                              mock_bigip_with_vxlan_arp,
                              fully_mocked_tunnel, fully_mocked_fdb):
        """This test will perform all necessary tasks on deleting a tunnel

        This test will perform the following:
            1. Dope a 'bigip' mock object with a vxlan tunnel
            2. Dope the TunnelHandler with the same tunnel
            3. Remove the tunnel from the TunnelHandler
        As part of this, this tests the scenario where the tunnel does not yet
        exist.
        """
        target = fully_mocked_target
        bigip = mock_bigip_with_vxlan_arp
        tunnel_obj = fully_mocked_tunnel
        fdb_obj = fully_mocked_fdb
        partition = 'partition'
        self.tunnel_builder.set_partition(tunnel_obj, partition)
        self.tunnel_builder.add_fdb(tunnel_obj, fdb_obj)
        self.tunnel_builder.set_network_id(tunnel_obj, 'network_id')
        self.fdb_builder.set_network_id(fdb_obj, 'network_id')
        standalone_builder.add_pending_exists(target, tunnel_obj)
        target.remove_multipoint_tunnel(bigip, tunnel_obj.tunnel_name,
                                        partition)
        tm_tunnel = bigip.tm_tunnel
        tunnel = bigip.tunnel
        arp = bigip.arp
        assert tm_tunnel.load.call_count
        assert tunnel.delete.call_count
        assert arp.delete.call_count
