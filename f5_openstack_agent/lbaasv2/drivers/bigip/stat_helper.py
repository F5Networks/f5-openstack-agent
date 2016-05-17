# Copyright 2014-2016 F5 Networks Inc.
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

import re
import time

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as const

LOG = logging.getLogger(__name__)


class StatHelper(object):
    def get_global_statistics(self, bigip):
        allstats = bigip.tm.sys.performance.all_stats.load()
        if 'apiRawValues' in allstats:
            sr = {'Sys::Performance System': {
                'System CPU Usage': {
                    'Utilization': {
                        'current': 0,
                        'average': 0,
                        'max': 0
                    }
                },
                'Memory Used': {
                    'TMM Memory Used': {
                        'current': 0,
                        'average': 0,
                        'max': 0
                    },
                    'Other Memory Used': {
                        'current': 0,
                        'average': 0,
                        'max': 0
                    },
                    'Swap Memory Used': {
                        'current': 0,
                        'average': 0,
                        'max': 0
                    }
                }
            },
                'Sys::Performance Connections': {
                'Active Connections': {
                    'Connections': {
                        'current': 0,
                        'average': 0,
                        'max': 0
                    }
                },
                    'Total New Connections': {
                        'Client Connections': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        },
                        'Server Connections': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        }
                    },
                    'HTTP Requests': {
                        'HTTP Requests': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        }
                    }
                },
                'Sys::Performance Throughput': {
                    'Throughput(bits)': {
                        'In': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        },
                        'Out': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        }
                    },
                    'SSL Transactions': {
                        'SSL TPS': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        }
                    },
                    'Throughput(packets)': {
                        'In': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        },
                        'Out': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        }
                    }
                },
                'Sys::Performance Ramcache': {
                    'RAM Cache Utilization': {
                        'Hit Rate': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        },
                        'Byte Rate': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        },
                        'Eviction Rate': {
                            'current': 0,
                            'average': 0,
                            'max': 0
                        }
                    }
                }
            }
            stats_display = allstats['apiRawValues']['apiAnonymous']
            lines = str(stats_display).split('\n')
            sec = None
            div = None
            since = None
            for line in lines:
                if len(line) > 2:
                    for this_section in sr.keys():
                        if str(line).startswith(this_section):
                            if sec:
                                if not (sec == this_section):
                                    sec = this_section
                                    div = None
                            else:
                                sec = this_section
                    if sec:
                        for division in sr[sec].keys():
                            if str(line).startswith(division):
                                try:
                                    since_idx = line.index('since')
                                    end_since_idx = line.index(')',
                                                               since_idx)
                                    since = line[since_idx + 6:end_since_idx]
                                except ValueError:
                                    pass
                                div = division
                    if div:
                        for fields in sr[sec][div].keys():
                            for field in fields:
                                if str(line).startswith(field):
                                    values = re.split(r'\s{2,}', line)
                                    if len(values) == 4:
                                        if values[0] in fields:
                                            sr[sec][div][values[0]] = \
                                                {
                                                    'current': values[1],
                                                    'average': values[2],
                                                    'max': values[3]
                                                }
            sr['since'] = since
            return sr
        return None

    def get_composite_score(self, bigip):
        gs = self.get_global_statistics(bigip)
        cpu_score = self.get_cpu_health_score(bigip, gs) * \
            const.DEVICE_HEALTH_SCORE_CPU_WEIGHT
        mem_score = self.get_mem_health_score(bigip, gs) * \
            const.DEVICE_HEALTH_SCORE_MEM_WEIGHT
        cps_score = self.get_cps_health_score(bigip, gs) * \
            const.DEVICE_HEALTH_SCORE_CPS_WEIGHT

        total_weight = const.DEVICE_HEALTH_SCORE_CPU_WEIGHT + \
            const.DEVICE_HEALTH_SCORE_MEM_WEIGHT + \
            const.DEVICE_HEALTH_SCORE_CPS_WEIGHT

        return int((cpu_score + mem_score + cps_score) / total_weight)

    # returns percentage of TMM memory currently in use
    def get_mem_health_score(self, bigip, global_stats=None):
        # use TMM memory usage for memory health
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        tmm_mem = int(
            global_stats[
                'Sys::Performance System']['Memory Used'][
                'TMM Memory Used']['current']
        )
        other_mem = int(
            global_stats[
                'Sys::Performance System']['Memory Used'][
                'TMM Memory Used']['current']
        )
        if other_mem > 90:
            return other_mem
        else:
            return tmm_mem

    def get_cpu_health_score(self, bigip, global_stats=None):
        # Get cpu health score """
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        cpu_score = int(
            global_stats[
                'Sys::Performance System']['System CPU Usage'][
                'Utilization']['current']
        )
        return cpu_score

    def get_cps_health_score(self, bigip, global_stats=None):
        # Get cps health score """
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        count_init = int(
            global_stats['Sys::Performance Connections']['Active Connections'][
                'Connections']['current']
        )
        time.sleep(const.DEVICE_HEALTH_SCORE_CPS_PERIOD)
        global_stats = self.get_global_statistics(bigip)
        count_final = int(
            global_stats['Sys::Performance Connections']['Active Connections'][
                'Connections']['current']
        )
        cps = (count_final - count_init) / const.DEVICE_HEALTH_SCORE_CPS_PERIOD

        if cps >= const.DEVICE_HEALTH_SCORE_CPS_MAX:
            return 0
        else:
            score = int(100 - ((100 * float(cps)) /
                               float(const.DEVICE_HEALTH_SCORE_CPS_MAX)))
        return score

    def get_active_connection_count(self, bigip, global_stats=None):
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        return int(
            global_stats['Sys::Performance Connections'][
                'Active Connections'][
                'Connections']['current']
        )

    def get_active_SSL_TPS(self, bigip, global_stats=None):
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        return int(
            global_stats['Sys::Performance Throughput'][
                'SSL Transactions'][
                'SSL TPS']['current']
        )

    def get_inbound_throughput(self, bigip, global_stats=None):
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        return int(
            global_stats['Sys::Performance Throughput']
            ['Throughput(bits)']
            ['In']['current']
        )

    def get_outbound_throughput(self, bigip, global_stats=None):
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        return int(
            global_stats['Sys::Performance Throughput']
            ['Throughput(bits)']
            ['Out']['current']
        )

    def get_throughput(self, bigip, global_stats=None):
        if not global_stats:
            global_stats = self.get_global_statistics(bigip)
        inbound = int(
            global_stats['Sys::Performance Throughput']
            ['Throughput(bits)']
            ['In']['current']
        )
        outbound = int(
            global_stats['Sys::Performance Throughput']
            ['Throughput(bits)']
            ['Out']['current']
        )
        return inbound + outbound
