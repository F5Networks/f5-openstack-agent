# coding=utf-8
# Copyright 2014 F5 Networks Inc.
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

# pylint: disable=no-self-use

import json

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class L3BindingBase(object):
    """Base Class for L3 address bindings to L3 port."""

    def __init__(self, conf, driver):
        self.conf = conf
        self.driver = driver
        self.l3_binding_mappings = {}
        self.__initialized__bigip_ports = False

        LOG.debug('reading static L3 address bindings')
        if self.conf.l3_binding_static_mappings:
            LOG.debug('bindings: %s '
                      % self.conf.l3_binding_static_mappings)
            # FIXME(RB): need to do some error handling here if the user
            # specifies the static mappings incorrectly.
            l3_binding_static_mappings = \
                json.loads(self.conf.l3_binding_static_mappings)
            for subnet_id in l3_binding_static_mappings:
                binding_list = l3_binding_static_mappings[subnet_id]
                if isinstance(binding_list, list):
                    for (port_id, device_id) in binding_list:
                        if port_id:
                            if subnet_id in self.l3_binding_mappings:
                                self.l3_binding_mappings[subnet_id] = \
                                    self.l3_binding_mappings[subnet_id] + \
                                    binding_list
                            else:
                                self.l3_binding_mappings[subnet_id] = \
                                    binding_list
                            LOG.debug('bind subnet %s to port: %s, device %s'
                                      % (subnet_id, port_id, device_id))
        else:
            LOG.debug('l3_binding_static_mappings not configured')

    def register_bigip_mac_addresses(self):
        # Delayed binding BIG-IP® ports will be called
        # after BIG-IP® endpoints are registered.
        if not self.__initialized__bigip_ports:
            for bigip in self.driver.get_all_bigips():
                LOG.debug('Request Port information for MACs: %s'
                          % bigip.mac_addresses)
                if self.driver.plugin_rpc:
                    ports = self.driver.plugin_rpc.get_ports_for_mac_addresses(
                        mac_addresses=bigip.mac_addresses)
                    LOG.debug('Neutron returned Port Info: %s' % ports)
                    for port in ports:
                        port_id = port['id']
                        device_id = port['device_id']
                        if 'fixed_ips' in port:
                            fixed_ips = port['fixed_ips']
                            for fi in fixed_ips:
                                subnet_id = fi['subnet_id']
                                if subnet_id in self.l3_binding_mappings:
                                    self.l3_binding_mappings[subnet_id] = \
                                        self.l3_binding_mappings[subnet_id] + \
                                        [(port_id, device_id)]
                                else:
                                    self.l3_binding_mappings[subnet_id] = \
                                        [(port_id, device_id)]
                                LOG.debug('adding mapping information '
                                          'subnet %s to port: %s, device %s'
                                          % (subnet_id, port_id, device_id))
            self.__initialized__bigip_ports = True

    def bind_address(self, subnet_id=None, ip_address=None):
        raise NotImplementedError(
            "An L3 address binding class must implement bind_address"
        )

    def unbind_address(self, subnet_id=None, ip_address=None):
        raise NotImplementedError(
            "An L3 address binding class must implement unbind_address"
        )


class AllowedAddressPairs(L3BindingBase):
    """Class for configuring L3 address bindings to L2 ports."""

    def __init__(self, conf, driver):
        super(AllowedAddressPairs, self).__init__(conf, driver)

    def bind_address(self, subnet_id=None, ip_address=None):
        LOG.debug('checking for required port bindings '
                  'subnet_id: %s ip_address %s'
                  % (subnet_id, ip_address))
        if subnet_id in self.l3_binding_mappings:
            binding_list = self.l3_binding_mappings[subnet_id]
            for (port_id, device_id) in binding_list:
                if port_id:
                    LOG.debug('adding allowed address pair '
                              'address: %s port: %s device: %s'
                              % (ip_address, port_id, device_id))
                    if self.driver.plugin_rpc:
                        self.driver.plugin_rpc.add_allowed_address(
                            port_id=port_id,
                            ip_address=ip_address
                        )
                    else:
                        LOG.error(
                            'No RPC to plugin available to add '
                            'allowed address %s to port: %s.'
                            % (ip_address, port_id)
                        )

    def unbind_address(self, subnet_id=None, ip_address=None):
        LOG.debug('checking for removal of port bindings '
                  'subnet_id: %s ip_address %s'
                  % (subnet_id, ip_address))
        if subnet_id in self.l3_binding_mappings:
            binding_list = self.l3_binding_mappings[subnet_id]
            for (port_id, device_id) in binding_list:
                if port_id:
                    LOG.debug('removing allowed address pair '
                              'address: %s port: %s device: %s'
                              % (ip_address, port_id, device_id))
                    if self.driver.plugin_rpc:
                        self.driver.plugin_rpc.remove_allowed_address(
                            port_id=port_id,
                            ip_address=ip_address
                        )
                    else:
                        LOG.error(
                            'No RPC to plugin available to remove '
                            'allowed address %s to port: %s.'
                            % (ip_address, port_id)
                        )
