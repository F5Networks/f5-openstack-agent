# coding=utf-8
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

import json

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class VLANBindingBase(object):
    """Base Class for device interface to port binding """
    def __init__(self, conf, driver):
        self.conf = conf
        self.driver = driver
        self.interface_binding_mappings = {}
        self.__initialized__bigip_ports = False

        LOG.debug('reading static device interface port bindings')
        if self.conf.interface_port_static_mappings:
            LOG.debug('bindings: %s '
                      % self.conf.interface_port_static_mappings)
            interface_binding_static_mappings = \
                json.loads(self.conf.interface_port_static_mappings)
            if isinstance(interface_binding_static_mappings, dict):
                for device in interface_binding_static_mappings:
                    if isinstance(device, dict):
                        self.interface_binding_mappings[device] = \
                            interface_binding_static_mappings[device]
        else:
            LOG.debug('interface_port_static_mappings not configured')

    def register_bigip_interfaces(self):
        # Delayed binding BIG-IP® ports will be called
        # after BIG-IP® endpoints are registered.
        if not self.__initialized__bigip_ports:
            for bigip in self.driver.get_all_bigips():

                LOG.debug('Request Port information for MACs: %s'
                          % bigip.device_interfaces)
                if self.driver.plugin_rpc:
                    ports = self.driver.plugin_rpc.get_ports_for_mac_addresses(
                        mac_addresses=bigip.mac_addresses)
                    LOG.debug('Neutron returned Port Info: %s' % ports)
                    for port in ports:
                        for interface in bigip.device_interfaces:
                            if not interface == 'mgmt':
                                if bigip.device_interfaces[interface] == \
                                        port['mac_address']:
                                    mapping = {interface: port['id']}
                                    self.interface_binding_mappings[
                                        bigip.device_name] = mapping
                                LOG.debug('adding mapping information device'
                                          '%s interface %s to port: %s'
                                          % (bigip.device_name,
                                             interface,
                                             port['id']))
            self.__initialized__bigip_ports = True
            LOG.debug('interface bindings after initialization are: %s'
                      % self.interface_binding_mappings)
            for bigip in self.driver.get_all_bigips():
                if bigip.device_name not in self.interface_binding_mappings:
                    example = {bigip.device_name: {}}
                    for interface in bigip.device_interfaces:
                        example[bigip.device_name][interface] = \
                            "port_id_for_%s" % interface
                    json_example = json.loads(example)
                    LOG.warning(
                        'The device %s at %s does not have interface bindings'
                        % (bigip.device_name, bigip.hostname),
                        ' even though VLAN binding has been requested',
                    )
                    LOG.warning(
                        'An example static mapping would be: %s' % json_example
                    )

    def allow_vlan(self, device_name=None, interface=None, vlanid=0):
        raise NotImplementedError(
            "An VLAN binding class must implement allow_vlan"
        )

    def prune_vlan(self, device_name=None, interface=None, vlanid=0):
        raise NotImplementedError(
            "An VLAN binding class must implement prune_vlan"
        )


class NullBinding(VLANBindingBase):
    # Class for configuring VLAN lists on ports.
    def __init__(self, conf, driver):
        super(NullBinding, self).__init__(conf, driver)

    def allow_vlan(self, device_name=None, interface=None, vlanid=0):
        if not device_name:
            return
        if not interface:
            return
        if vlanid == 0:
            return
        LOG.debug('checking for port bindings '
                  'device_name: %s interface %s'
                  % (device_name, interface))
        if device_name in self.interface_binding_mappings:
            if interface in self.interface_binding_mappings[device_name]:
                LOG.debug(
                    'allowing VLAN %s on port %s'
                    % (vlanid,
                       self.interface_binding_mappings[device_name][interface])
                )

    def prune_vlan(self, device_name=None, interface=None, vlanid=None):
        if not device_name:
            return
        if not interface:
            return
        if vlanid == 0:
            return
        LOG.debug('checking for port bindings '
                  'device_name: %s interface %s'
                  % (device_name, interface))
        if device_name in self.interface_binding_mappings:
            if interface in self.interface_binding_mappings[device_name]:
                LOG.debug(
                    'pruning VLAN %s from port %s'
                    % (vlanid,
                       self.interface_binding_mappings[device_name][interface])
                )
