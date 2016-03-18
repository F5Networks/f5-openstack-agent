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

from neutron.common import constants as q_const

from oslo_log import log as logging

from fdb_connector import FDBConnector

LOG = logging.getLogger(__name__)


class FDBConnectorML2(FDBConnector):

    def __init__(self, conf):
        super(FDBConnectorML2, self).__init__(conf)
        self._tunnel_types = self.conf.advertised_tunnel_types
        self._context = None
        self._tunnel_rpc = None
        self._l2pop_rpc = None

    def set_context(self, context):
        # database context
        self._context = context

    def set_tunnel_rpc(self, tunnel_rpc):
        # Tunnel rpc interface
        self._tunnel_rpc = tunnel_rpc

    def set_l2pop_rpc(self, l2pop_rpc):
        # L2 Population rpc interface
        self._l2pop_rpc = l2pop_rpc

    def advertise_tunnel_ips(self, tunnel_ips):
        # Advertise tunnel ips
        if not self._tunnel_rpc:
            return

        for tunnel_ip in tunnel_ips:
            self._advertise_tunnel_ip(tunnel_ip)

    def _advertise_tunnel_ip(self, tunnel_ip):
        # Advertise one tunnel ips
        try:
            for tunnel_type in self._tunnel_types:
                self._tunnel_rpc.tunnel_sync(self._context,
                                             tunnel_ip,
                                             tunnel_type)
        except Exception as exc:
            LOG.error(
                "Unable to sync tunnel IP %(local_ip)s: %(e)s",
                {'local_ip': tunnel_ip, 'e': exc})

    def notify_vtep_added(self, network, vtep_ip_address):
        # notify all the compute nodes we are VTEPs for this network now.
        if self.conf.l2_population and self._l2pop_rpc:
            fdb_entries = {network['id']:
                           {'ports':
                            {vtep_ip_address: [q_const.FLOODING_ENTRY]},
                            'network_type': network['provider:network_type'],
                            'segment_id': network['provider:segmentation_id']}}
            self._l2pop_rpc.add_fdb_entries(self._context, fdb_entries)

    def notify_vtep_removed(self, network, vtep_ip_address):
        # notify all the compute nodes we no longer have
        # VTEPs for this network now.
        if self.conf.l2_population and self._l2pop_rpc:
            fdb_entries = {network['id']:
                           {'ports':
                            {vtep_ip_address: [q_const.FLOODING_ENTRY]},
                            'network_type': network['provider:network_type'],
                            'segment_id': network['provider:segmentation_id']}}
            self._l2pop_rpc.remove_fdb_entries(self._context, fdb_entries)
