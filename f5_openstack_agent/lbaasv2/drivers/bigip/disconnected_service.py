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

from eventlet import greenthread
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from neutron.plugins.common import constants as plugin_const
from neutron_lbaas.services.loadbalancer import constants as lb_const
from os.path import basename
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import timeutils

LOG = logging.getLogger(__name__)


class DisconnectedServicePolling(object):
    def __init__(self, driver):
        self.driver = driver
        self.enabled = (True if self.get_physical_network() else False)
        if self.enabled:
            greenthread.spawn(self.polling_thread)
        self.timer = {}

    def get_physical_network(self):
        return self.driver.conf.f5_network_segment_physical_network

    def get_service_virtual_address(self, bigips, virtual):
        va_table = {}
        for bigip in bigips:
            vsf = bigip.tm.ltm.virtuals.virtual
            vs = vsf.load(
                name=virtual['name'], partition=virtual['partition'])
            destination = getattr(vs, 'destination', None)
            va_table[bigip] = destination
        return va_table

    def remove_obsolete_service_address(self, bigips, virtual,
                                        starting_dest, ending_dest):
        for bigip in bigips:
            if (starting_dest[bigip] != ending_dest[bigip] and
                    starting_dest[bigip]):
                vac = bigip.tm.ltm.virtual_address_s
                dest = basename(starting_dest[bigip])
                nh = self.driver.disconnected_service.network_helper
                (vip_addr, vip_port) = nh.split_addr_port(dest)
                if vac.virtual_address.exists(
                        name=vip_addr, partition=virtual['partition']):
                    va = vac.virtual_address.load(
                        name=vip_addr, partition=virtual['partition'])
                    va.delete()

    def scan(self):
        """Periodically scan for disconnected virtual servers.

        :return: Return the number of seconds to wait before invoking this
            method again.
        """

        LOG.debug("scanning disconnected networks")
        # find active loadbalancers for this agent to see which virtual
        # servers have become un-disconnected.
        d = self.driver
        if d.plugin_rpc:
            loadbalancer_ids = d.plugin_rpc.get_all_loadbalancers()
            for lb in loadbalancer_ids:
                id = lb['lb_id']
                if (id in self.timer and self.timer[id]['expired']):
                    # LB is in error state, no need to check further
                    continue
                service = d.plugin_rpc.get_service_by_loadbalancer_id(id)

                if (service['loadbalancer']['provisioning_status'].upper() !=
                        plugin_const.ACTIVE):
                    continue

                if not d.disconnected_service.is_service_connected(service):
                    if id in self.timer:
                        if not timeutils.is_older_than(
                                self.timer[id]['start'],
                                d.conf.f5_network_segment_gross_timeout):
                            continue
                        self.timer[id]['expired'] = True
                        LOG.error(
                            "TIMEOUT: failed to connect loadbalancer %s "
                            "to a real network after %d seconds" %
                            (id, d.conf.f5_network_segment_gross_timeout))
                        d.plugin_rpc.update_loadbalancer_status(
                            id, plugin_const.ERROR, lb_const.OFFLINE)
                        for listener in service['listeners']:
                            if (listener['provisioning_status'] !=
                                    plugin_const.PENDING_DELETE):
                                d.plugin_rpc.update_listener_status(
                                    listener['id'], plugin_const.ERROR,
                                    lb_const.OFFLINE)
                    else:
                        self.timer[id] = {
                            'start': timeutils.utcnow(),
                            'expired': False
                        }
                        d.plugin_rpc.update_loadbalancer_status(
                            id, plugin_const.ACTIVE, lb_const.OFFLINE)
                    continue
                # service is connected in neutron, move all listeners for this
                # loadbalancer onto a real network
                for listener in service['listeners']:
                    if (listener['provisioning_status'] ==
                            plugin_const.PENDING_DELETE):
                        continue
                    test_service = {
                        'listener': listener,
                        'loadbalancer': service['loadbalancer']
                    }
                    virtual = d.service_adapter.get_virtual_name(test_service)
                    bigips = d.get_all_bigips()
                    if not d.disconnected_service.is_virtual_connected(
                            virtual, bigips):
                        LOG.debug("connecting %s to a real network" %
                                  virtual['name'])
                        service['loadbalancer']['provisioning_status'] = \
                            plugin_const.PENDING_UPDATE
                        # Save existing list of virtual addresses in case
                        # a new one is created in the next step.  We need to
                        # remove obsolete entries
                        starting_dest = self.get_service_virtual_address(
                            bigips, virtual)
                        # if any virtual is not connected update the entire
                        # service, but only once since the handler will run
                        # through all listeners
                        d._common_service_handler(service)
                        ending_dest = self.get_service_virtual_address(
                            bigips, virtual)
                        self.remove_obsolete_service_address(
                            bigips, virtual, starting_dest, ending_dest)
                        break

    def polling_thread(self):
        while True:
            # Split out the actual scanning tech to accommodate migration
            # greeenthread to oslo periodic_task.
            try:
                self.scan()
            finally:
                greenthread.sleep(
                    self.driver.conf.f5_network_segment_polling_interval)


class DisconnectedService(object):
    network_name = 'disconnected_network'

    def __init__(self):
        self.network_name = DisconnectedService.network_name
        self.network_helper = NetworkHelper()

    # The following method presumes that the plugin driver is aware that we're
    # running in hierarchical mode or not and sets segmentation_id correctly.
    def is_service_connected(self, service):
        networks = service['networks']
        network_id = service['loadbalancer']['network_id']
        segmentation_id = networks[network_id]['provider:segmentation_id']
        return (segmentation_id)

    def is_virtual_connected(self, virtual, bigips):
        # check if virtual_server is connected on any of our bigips
        connected = True
        for bigip in bigips:
            vsf = bigip.tm.ltm.virtuals.virtual
            if vsf.exists(name=virtual['name'],
                          partition=virtual['partition']):
                vs = vsf.load(
                    name=virtual['name'], partition=virtual['partition'])
                if (getattr(vs, 'vlansDisabled', False) or
                        not getattr(vs, 'vlansEnabled', True)):
                    # accommodate quirk of how big-ip returns virtual server
                    # if vlans are disabled OR vlans are not enabled, then
                    # we're connected
                    continue
                network_path = "/%s/%s" % (virtual['partition'],
                                           self.network_name)
                if network_path in getattr(vs, 'vlans', []):
                    connected = False
                    break
        return connected

    def network_exists(self, bigip, partition):
        t = bigip.tm.net.tunnels.tunnels.tunnel
        return t.exists(name=self.network_name, partition=partition)

    @log_helpers.log_method_call
    def create_network(self, bigip, partition):
        model = {'name': self.network_name,
                 'partition': partition,
                 'profile': 'ppp',
                 'description': 'Tenant disconnected network'}
        t = self.network_helper.create_tunnel(bigip, model)
        return t

    @log_helpers.log_method_call
    def delete_network(self, bigip, partition):
        tf = bigip.tm.net.tunnels.tunnels.tunnel
        if tf.exists(name=self.network_name, partition=partition):
            tf.load(name=self.network_name, partition=partition).delete()
