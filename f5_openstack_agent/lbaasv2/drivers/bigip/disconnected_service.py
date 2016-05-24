# Copyright 2016 F5 Networks Inc.
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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from eventlet import greenthread
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper

LOG = logging.getLogger(__name__)


class DisconnectedService(object):
    network_name = 'disconnected_network'

    def __init__(self, driver=None):
        self.driver = driver
        self.name = DisconnectedService.network_name
        if driver:
            self.spawn_polling_thread()
        self.network_helper = NetworkHelper()

    # Tailor this method to poll the appropriate field based on your ML2 driver.
    # In a hierarchical network deployment, this code presumes that the
    # segmentation_id will not exist upon creation of the loadbalancer and/or
    # listener.
    def is_service_connected(self, service):
        from pprint import pformat
        LOG.debug("service: %s" % pformat(service))
        networks = service['networks']
        network_id = service['loadbalancer']['network_id']
        segmentation_id = networks[network_id]['provider:segmentation_id']
        return segmentation_id

    def is_virtual_connected(self, virtual, bigips):
        # check if virtual_server is not connected on any of our bigips
        connected = True
        for bigip in bigips:
            vs = bigip.ltm.virtuals.virtual
            if vs.exists(name=virtual['name'], partition=virtual['partition']):
                vs.load(name=virtual['name'], partition=virtual['partition'])
                if (getattr(vs, 'vlansDisabled', False) or
                        not getattr(vs, 'vlansEnabled', True)):
                    # accommodate quick of how big-ip returns virtual server
                    # if vlans are disabled OR vlans are not enabled, then we're
                    # connected
                    continue
                network_path = "/%s/%s" % (virtual['partition'],
                                           DisconnectedService.network_name)
                if network_path in getattr(vs, 'vlans', []):
                    connected = False
                    break
        return connected

    def polling_thread(self):
        while True:
            LOG.debug("scanning disconnected networks")
            # find active loadbalancers for this agent to see which virtual
            # servers have become un-disconnected.
            if self.driver.plugin_rpc:
                loadbalancer_ids = \
                    self.driver.plugin_rpc.get_all_loadbalancers()
                for lb in loadbalancer_ids:
                    service = \
                        self.driver.plugin_rpc.get_service_by_loadbalancer_id(
                            lb['lb_id'])
                    listeners = service.get('listeners', None)
                    if not listeners:
                        # there are no virtual server to move
                        continue
                    service.pop('listeners', None)
                    for listener in listeners:
                        service['listener'] = listener
                        sa = self.driver.service_adapter
                        virtual = sa.get_virtual_name(service)
                        bigips = self.driver.get_all_bigips()
                        if (self.is_service_connected(service) and
                                not self.is_virtual_connected(virtual, bigips)):
                            # swing the virtual server to its final network
                            LOG.debug("connecting %s to a real network" %
                                      virtual['name'])
                            lb_builder = self.driver.lbaas_builder
                            lb_builder.listener_builder.update_listener(
                                service, bigips)
            greenthread.sleep(
                self.driver.conf.disconnected_network_polling_interval)

    def spawn_polling_thread(self):
        obj = greenthread.spawn(self.polling_thread)
        print obj

    def network_exists(self, bigip, partition):
        t = bigip.net.tunnels_s.tunnels.tunnel
        return t.exists(name=self.name, partition=partition)

    @log_helpers.log_method_call
    def create_network(self, bigip, partition):
        model = {'name': self.name,
                 'partition': partition,
                 'profile': 'ppp',
                 'description': 'Tenant disconnected network'}
        t = self.network_helper.create_tunnel(bigip, model)
        return t

    @log_helpers.log_method_call
    def delete_network(self, bigip, partition):
        t = bigip.net.tunnels_s.tunnels.tunnel
        if t.exists(name=self.name, partition=partition):
            t.load(name=self.name, partition=partition)
            t.delete()
