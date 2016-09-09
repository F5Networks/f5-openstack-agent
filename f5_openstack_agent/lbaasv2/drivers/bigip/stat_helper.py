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


from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class StatHelper(object):
    def get_global_statistics(self, bigip):
        allstats = bigip.tm.sys.performances.all_stats.load().__dict__
        if 'apiRawValues' in allstats:
            sr = {
                'Sys::Performance System': {
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
                                            value = values[0]
                                            vdict = sr[sec][div][value]
                                            value_set = (
                                                (1, 'current'),
                                                (2, 'average'),
                                                (3, 'max'),
                                            )
                                            for i, k in value_set:
                                                try:
                                                    vdict[k] = int(values[i])
                                                except ValueError:
                                                    vdict[k] = 0
                                                    pass
                                            sr[sec][div][values[0]] = vdict
            sr['since'] = since
            return sr
        return None

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
