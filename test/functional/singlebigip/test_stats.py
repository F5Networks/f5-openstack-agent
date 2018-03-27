# -*- coding: utf-8 -*-
'''
test_requirements = {'devices':         [UNDERCLOUD],
                     'openstack_infra': []}

'''
# Copyright (c) 2016-2018, F5 Networks, Inc.
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

import pytest
import requests
requests.packages.urllib3.disable_warnings()

from f5_openstack_agent.lbaasv2.drivers.bigip import network_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import ssl_profile
from f5_openstack_agent.lbaasv2.drivers.bigip import stat_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import system_helper

class TestStats:
    """
    Test global stats used for calculating capacity score.

    Test assumes a BIG-IP with single load balancer in an under cloud
    environment using vxlan tunnels.
    """

    @pytest.fixture(scope="session")
    def network_helper(self):
        return network_helper.NetworkHelper()

    @pytest.fixture(scope="session")
    def stats_helper(self):
        return stat_helper.StatHelper()

    @pytest.fixture(scope="session")
    def system_helper(self):
        return system_helper.SystemHelper()

    def test_get_global_statistics(self, mgmt_root, stats_helper):
        stats = stats_helper.get_global_statistics(mgmt_root)
        assert stats

    def test_get_active_connection_count(self, mgmt_root, stats_helper):
        score = stats_helper.get_active_connection_count(mgmt_root)
        assert score >= 0
        print "Active Connection Count: " + str(score)

    def test_get_active_SSL_TPS(self, mgmt_root, stats_helper):
        score = stats_helper.get_active_SSL_TPS(mgmt_root)
        assert score >= 0
        print "Active SSL TPS: " + str(score)

    def test_get_inbound_throughput(self, mgmt_root, stats_helper):
        score = stats_helper.get_inbound_throughput(mgmt_root)
        assert score >= 0
        print "Inbound Throughtput: " + str(score)

    def test_get_outbound_throughput(self, mgmt_root, stats_helper):
        score = stats_helper.get_outbound_throughput(mgmt_root)
        assert score >= 0
        print "Outbound Throughtput: " + str(score)

    def test_get_throughput(self, mgmt_root, stats_helper):
        score = stats_helper.get_throughput(mgmt_root)
        assert score >= 0
        print "Throughput: " + str(score)

    def test_get_node_count(self, mgmt_root):
        count = len(mgmt_root.tm.ltm.nodes.get_collection())
        assert count == 0
        print "Node Count: " + str(count)

    def test_get_clientssl_profile_count(self, mgmt_root):
        count = ssl_profile.SSLProfileHelper.get_client_ssl_profile_count(mgmt_root)
        assert count > 0
        print "SSL Profile Count: " + str(count)

    def test_get_tenant_count(self, mgmt_root, system_helper):
        count = system_helper.get_tenant_folder_count(mgmt_root)
        assert count == 1
        print "Tenant Count: " + str(count)

    def test_get_tunnel_count(self, mgmt_root, network_helper):
        count = network_helper.get_tunnel_count(mgmt_root)
        assert count == 0
        print "Tunnel Count: " + str(count)


    def test_get_vlan_count(self, mgmt_root, network_helper):
        count = network_helper.get_vlan_count(mgmt_root)
        assert count == 4
        print "VLAN Count: " + str(count)

    def test_get_route_domain_count(self, mgmt_root, network_helper):
        count = network_helper.get_route_domain_count(mgmt_root)
        assert count == 0
        print "Route Domain Count: " + str(count)
