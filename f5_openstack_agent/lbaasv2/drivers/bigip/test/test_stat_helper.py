# coding=utf-8
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

from f5_openstack_agent.lbaasv2.drivers.bigip.stat_helper import StatHelper

import mock


API_ANONYMOUS = """
Sys::Performance System ()
----------------------------------------------------------------------
System CPU Usage(%)  Current  Average  Max(since 2016-09-01T14:53:10Z)
----------------------------------------------------------------------
Utilization                2        2                               28

----------------------------------------------------------------------
Memory Used(%)       Current  Average  Max(since 2016-09-01T14:53:10Z)
----------------------------------------------------------------------
TMM Memory Used           41       41                               41
Other Memory Used         55       53                               55
Swap Used                  0        0                                0

Sys::Performance Connections ()
------------------------------------------------------------------------------
Active Connections           Current  Average  Max(since 2016-09-01T14:53:10Z)
------------------------------------------------------------------------------
Connections                        0        0                                0

------------------------------------------------------------------------------
Total New Connections(/sec)  Current  Average  Max(since 2016-09-01T14:53:10Z)
------------------------------------------------------------------------------
Client Connections                 0        0                                0
Server Connections                 0        0                                0

------------------------------------------------------------------------------
HTTP Requests(/sec)          Current  Average  Max(since 2016-09-01T14:53:10Z)
------------------------------------------------------------------------------
HTTP Requests                      0        0                                0


Sys::Performance Throughput ()
------------------------------------------------------------------------------\
--
Throughput(bits)(bits/sec)     Current  Average  Max(since 2016-09-01T14:53:10\
Z)
------------------------------------------------------------------------------\
--
In                               16995    14108                            \
52077
Out                               7825     2782                           \
197391

------------------------------------------------------------------------------\
--
SSL Transactions               Current  Average  Max(since 2016-09-01T14:53:10\
Z)
------------------------------------------------------------------------------\
--
SSL TPS                              0        0                               \
 0

------------------------------------------------------------------------------\
--
Throughput(packets)(pkts/sec)  Current  Average  Max(since 2016-09-01T14:53:10\
Z)
------------------------------------------------------------------------------\
--
In                                  20       18                               \
43
Out                                  3        1                               \
26


Sys::Performance Ramcache ()
---------------------------------------------------------------------------
RAM Cache Utilization(%)  Current  Average  Max(since 2016-09-01T14:53:10Z)
---------------------------------------------------------------------------
Hit Rate                      nan      nan                              nan
Byte Rate                     nan      nan                              nan
Eviction Rate                 nan      nan                              nan
"""

ALL_STATS_1 = {
    "kind":
        "tm:sys:performance:all-stats:all-statsstats",
    "selfLink":
        "https://localhost/mgmt/tm/sys/performance/all-stats?ver=11.6.0",
    "apiRawValues": {
        "apiAnonymous": API_ANONYMOUS
    }
}

CPS_MAX = 'f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2.\
DEVICE_HEALTH_SCORE_CPS_MAX'

INCREMENT = 15


class TestStatHelper(object):
    global_stats = {
        'Sys::Performance Connections': {
            'Active Connections': {
                'Connections': {
                    'current': 10
                },
            }
        }
    }

    def test_get_global_statistics_no_api_raw_values(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = {}
        sh = StatHelper()
        assert sh.get_global_statistics(bigip) is None

    def test_get_global_statistics_api_raw_values(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1
        sh = StatHelper()
        stats = sh.get_global_statistics(bigip)
        assert isinstance(stats, dict)
        assert stats['since'] == "2016-09-01T14:53:10Z"

        # Validate the sections' stats
        perf_sys_cpu = stats['Sys::Performance System']['System CPU Usage']
        assert(perf_sys_cpu['Utilization']['current'] == 2)
        assert(perf_sys_cpu['Utilization']['average'] == 2)
        assert(perf_sys_cpu['Utilization']['max'] == 28)

        perf_sys_mem = stats['Sys::Performance System']['Memory Used']
        assert(perf_sys_mem['TMM Memory Used']['current'] == 41)
        assert(perf_sys_mem['TMM Memory Used']['average'] == 41)
        assert(perf_sys_mem['TMM Memory Used']['max'] == 41)

        perf_conns_active =\
            stats['Sys::Performance Connections']['Active Connections']
        assert(perf_conns_active['Connections']['current'] == 0)
        assert(perf_conns_active['Connections']['average'] == 0)
        assert(perf_conns_active['Connections']['max'] == 0)

        perf_conns_new =\
            stats['Sys::Performance Connections']['Total New Connections']
        assert(perf_conns_new['Client Connections']['current'] == 0)
        assert(perf_conns_new['Client Connections']['average'] == 0)
        assert(perf_conns_new['Client Connections']['max'] == 0)
        assert(perf_conns_new['Server Connections']['current'] == 0)
        assert(perf_conns_new['Server Connections']['average'] == 0)
        assert(perf_conns_new['Server Connections']['max'] == 0)

        perf_conns_http =\
            stats['Sys::Performance Connections']['HTTP Requests']
        assert(perf_conns_http['HTTP Requests']['current'] == 0)
        assert(perf_conns_http['HTTP Requests']['average'] == 0)
        assert(perf_conns_http['HTTP Requests']['max'] == 0)

        perf_tp_bits =\
            stats['Sys::Performance Throughput']['Throughput(bits)']
        assert(perf_tp_bits['In']['current'] == 16995)
        assert(perf_tp_bits['In']['average'] == 14108)
        assert(perf_tp_bits['In']['max'] == 52077)
        assert(perf_tp_bits['Out']['current'] == 7825)
        assert(perf_tp_bits['Out']['average'] == 2782)
        assert(perf_tp_bits['Out']['max'] == 197391)

        perf_tp_ssl =\
            stats['Sys::Performance Throughput']['SSL Transactions']
        assert(perf_tp_ssl['SSL TPS']['current'] == 0)
        assert(perf_tp_ssl['SSL TPS']['average'] == 0)
        assert(perf_tp_ssl['SSL TPS']['max'] == 0)

        perf_tp_pkts =\
            stats['Sys::Performance Throughput']['Throughput(packets)']
        assert(perf_tp_pkts['In']['current'] == 20)
        assert(perf_tp_pkts['In']['average'] == 18)
        assert(perf_tp_pkts['In']['max'] == 43)
        assert(perf_tp_pkts['Out']['current'] == 3)
        assert(perf_tp_pkts['Out']['average'] == 1)
        assert(perf_tp_pkts['Out']['max'] == 26)

        # The input has 'nan' for these values so they should be cast as 0
        perf_ram_util =\
            stats['Sys::Performance Ramcache']['RAM Cache Utilization']
        assert(perf_ram_util['Hit Rate']['current'] == 0)
        assert(perf_ram_util['Hit Rate']['average'] == 0)
        assert(perf_ram_util['Hit Rate']['max'] == 0)
        assert(perf_ram_util['Byte Rate']['current'] == 0)
        assert(perf_ram_util['Byte Rate']['average'] == 0)
        assert(perf_ram_util['Byte Rate']['max'] == 0)
        assert(perf_ram_util['Eviction Rate']['current'] == 0)
        assert(perf_ram_util['Eviction Rate']['average'] == 0)
        assert(perf_ram_util['Eviction Rate']['max'] == 0)

    def test_get_global_statistics_non_integer(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1

        sh = StatHelper()
        stats = sh.get_global_statistics(bigip)
        rc_util = stats['Sys::Performance Ramcache']['RAM Cache Utilization']
        assert isinstance(rc_util['Hit Rate']['current'], int)
        assert isinstance(rc_util['Hit Rate']['average'], int)
        assert isinstance(rc_util['Hit Rate']['max'], int)

    def test_get_active_connection_count_gs(self):
        bigip = mock.MagicMock()
        gs = {
            'Sys::Performance Connections': {
                'Active Connections': {
                    'Connections': {
                        'current': 100
                    }
                }
            }
        }

        sh = StatHelper()
        conns = sh.get_active_connection_count(bigip, global_stats=gs)
        assert(conns == 100)

    def test_get_active_connection_count_bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1
        sh = StatHelper()
        conns = sh.get_active_connection_count(bigip)
        assert(conns == 0)

    def test_get_active_SSL_TPS_gs(self):
        bigip = mock.MagicMock()
        gs = {
            'Sys::Performance Throughput': {
                'SSL Transactions': {
                    'SSL TPS': {
                        'current': 100
                    }
                }
            }
        }

        sh = StatHelper()
        conns = sh.get_active_SSL_TPS(bigip, global_stats=gs)
        assert(conns == 100)

    def test_get_active_SSL_TPS_bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1
        sh = StatHelper()
        conns = sh.get_active_SSL_TPS(bigip)
        assert(conns == 0)

    def test_get_inbound_throughput_gs(self):
        bigip = mock.MagicMock()
        gs = {
            'Sys::Performance Throughput': {
                'Throughput(bits)': {
                    'In': {
                        'current': 100
                    }
                }
            }
        }

        sh = StatHelper()
        conns = sh.get_inbound_throughput(bigip, global_stats=gs)
        assert(conns == 100)

    def test_get_inbound_throughput_bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1
        sh = StatHelper()
        conns = sh.get_inbound_throughput(bigip)
        assert(conns == 16995)

    def test_get_outbound_throughput_gs(self):
        bigip = mock.MagicMock()
        gs = {
            'Sys::Performance Throughput': {
                'Throughput(bits)': {
                    'Out': {
                        'current': 100
                    }
                }
            }
        }

        sh = StatHelper()
        conns = sh.get_outbound_throughput(bigip, global_stats=gs)
        assert(conns == 100)

    def test_get_outbound_throughput_bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1
        sh = StatHelper()
        conns = sh.get_outbound_throughput(bigip)
        assert(conns == 7825)

    def test_get_throughput_gs(self):
        bigip = mock.MagicMock()
        gs = {
            'Sys::Performance Throughput': {
                'Throughput(bits)': {
                    'Out': {
                        'current': 1800
                    },
                    'In': {
                        'current': 1500
                    }

                }
            }
        }

        sh = StatHelper()
        conns = sh.get_throughput(bigip, global_stats=gs)
        assert(conns == 3300)

    def test_get_throughput_bigip(self):
        bigip = mock.MagicMock()
        bigip.tm.sys.performances.all_stats.load().__dict__ = ALL_STATS_1
        sh = StatHelper()
        conns = sh.get_throughput(bigip)
        assert(conns == 24820)
