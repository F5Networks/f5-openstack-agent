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

import constants_v2
import random
from time import time

from oslo_log import log as logging
from oslo_utils import importutils

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.vcmp import VcmpManager

LOG = logging.getLogger(__name__)


def _get_tunnel_name(network):
    # BIG-IP object name for a tunnel
    tunnel_type = network['provider:network_type']
    tunnel_id = network['provider:segmentation_id']
    return 'tunnel-' + str(tunnel_type) + '-' + str(tunnel_id)


def get_tunnel_fake_mac(network, local_ip):
    # create a fake mac for l2 records for tunnels
    network_id = str(network['provider:segmentation_id']).rjust(4, '0')
    mac_prefix = '02:' + network_id[:2] + ':' + network_id[2:4] + ':'
    ip_parts = local_ip.split('.')
    if len(ip_parts) > 3:
        mac = [int(ip_parts[-3]),
               int(ip_parts[-2]),
               int(ip_parts[-1])]
    else:
        ip_parts = local_ip.split(':')
        if len(ip_parts) > 3:
            mac = [int('0x' + ip_parts[-3], 16),
                   int('0x' + ip_parts[-2], 16),
                   int('0x' + ip_parts[-1], 16)]
        else:
            mac = [random.randint(0x00, 0x7f),
                   random.randint(0x00, 0xff),
                   random.randint(0x00, 0xff)]
    return mac_prefix + ':'.join("%02x" % octet for octet in mac)


def _get_vteps(network, vtep_source):
    net_type = network['provider:network_type']
    vtep_type = net_type + '_vteps'
    return vtep_source.get(vtep_type, list())


class L2ServiceBuilder(object):

    def __init__(self, driver, f5_global_routed_mode):
        self.conf = driver.conf
        self.driver = driver
        self.f5_global_routed_mode = f5_global_routed_mode
        self.vlan_binding = None
        self.interface_mapping = {}
        self.tagging_mapping = {}
        self.system_helper = SystemHelper()
        self.network_helper = NetworkHelper()
        self.service_adapter = ServiceModelAdapter(self.conf)

        if self.conf.vlan_binding_driver:
            try:
                self.vlan_binding = importutils.import_object(
                    self.conf.vlan_binding_driver, self.conf, self)
            except ImportError:
                LOG.error('Failed to import VLAN binding driver: %s'
                          % self.conf.vlan_binding_driver)
                raise

        # map format is  phynet:interface:tagged
        for maps in self.conf.f5_external_physical_mappings:
            intmap = maps.split(':')
            net_key = str(intmap[0]).strip()
            if len(intmap) > 3:
                net_key = net_key + ':' + str(intmap[3]).strip()
            self.interface_mapping[net_key] = str(intmap[1]).strip()
            self.tagging_mapping[net_key] = str(intmap[2]).strip()
            LOG.debug('physical_network %s = interface %s, tagged %s'
                      % (net_key, intmap[1], intmap[2]))

    def initialize_vcmp_manager(self):
        '''Intialize the vCMP manager when the driver is ready.'''

        self.vcmp_manager = VcmpManager(self.driver)

    def post_init(self):
        if self.vlan_binding:
            LOG.debug(
                'Getting BIG-IP device interface for VLAN Binding')
            self.vlan_binding.register_bigip_interfaces()

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access
        if self.fdb_connector:
            self.fdb_connector.set_l2pop_rpc(l2pop_rpc)

    def is_common_network(self, network):
        """Returns True if this belongs in the /Common folder

        This object method will return positive if the L2ServiceBuilder object
        should be stored under the Common partition on the BIG-IP.
        """
        return network['shared'] or \
            self.conf.f5_common_networks or \
            (network['id'] in self.conf.common_network_ids) or \
            ('router:external' in network and
             network['router:external'] and
             self.conf.f5_common_external_networks)

    def get_vlan_name(self, network, hostname):
        # Construct a consistent vlan name
        net_key = network['provider:physical_network']
        net_type = network['provider:network_type']

        # look for host specific interface mapping
        if net_key and net_key + ':' + hostname in self.interface_mapping:
            interface = self.interface_mapping[net_key + ':' + hostname]
            tagged = self.tagging_mapping[net_key + ':' + hostname]
        elif net_key and net_key in self.interface_mapping:
            interface = self.interface_mapping[net_key]
            tagged = self.tagging_mapping[net_key]
        else:
            interface = self.interface_mapping['default']
            tagged = self.tagging_mapping['default']

        if tagged:
            vlanid = network['provider:segmentation_id']
        else:
            vlanid = 0

        if net_type == "flat":
            interface_name = str(interface).replace(".", "-")
            if (len(interface_name) > 15):
                LOG.warn(
                    "Interface name is greater than 15 chars in length")
            vlan_name = "flat-%s" % (interface_name)
        else:
            vlan_name = "vlan-%d" % (vlanid)

        return vlan_name

    def assure_bigip_network(self, bigip, network):
        # Ensure bigip has configured network object
        if not network:
            LOG.error('assure_bigip_network: '
                      'Attempted to assure a network with no id..skipping.')
            return

        if network['id'] in bigip.assured_networks:
            return

        if network['id'] in self.conf.common_network_ids:
            LOG.debug('assure_bigip_network: '
                      'Network is a common global network... skipping.')
            return

        LOG.debug("assure_bigip_network network: %s" % str(network))
        start_time = time()
        if self.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = self.service_adapter.get_folder_name(
                network['tenant_id']
            )

        # setup all needed L2 network segments
        if network['provider:network_type'] == 'flat':
            network_name = self._assure_device_network_flat(
                network, bigip, network_folder)
        elif network['provider:network_type'] == 'vlan':
            network_name = self._assure_device_network_vlan(
                network, bigip, network_folder)
        elif network['provider:network_type'] == 'vxlan':
            network_name = self._assure_device_network_vxlan(
                network, bigip, network_folder)
        elif network['provider:network_type'] == 'gre':
            network_name = self._assure_device_network_gre(
                network, bigip, network_folder)
        elif network['provider:network_type'] == 'opflex':
            raise f5_ex.NetworkNotReady(
                "Opflex network segment definition required")
        else:
            error_message = 'Unsupported network type %s.' \
                            % network['provider:network_type'] + \
                            ' Cannot setup network.'
            LOG.error(error_message)
            raise f5_ex.InvalidNetworkType(error_message)
        bigip.assured_networks[network['id']] = network_name

        if time() - start_time > .001:
            LOG.debug("        assure bigip network took %.5f secs" %
                      (time() - start_time))

    def _assure_device_network_flat(self, network, bigip, network_folder):
        # Ensure bigip has configured flat vlan (untagged)
        vlan_name = ""
        interface = self.interface_mapping['default']
        vlanid = 0

        # Do we have host specific mappings?
        net_key = network['provider:physical_network']
        if net_key and net_key + ':' + bigip.hostname in \
                self.interface_mapping:
            interface = self.interface_mapping[
                net_key + ':' + bigip.hostname]
        # Do we have a mapping for this network
        elif net_key and net_key in self.interface_mapping:
            interface = self.interface_mapping[net_key]

        vlan_name = self.get_vlan_name(network,
                                       bigip.hostname)

        self._assure_vcmp_device_network(bigip,
                                         vlan={'name': vlan_name,
                                               'folder': network_folder,
                                               'id': vlanid,
                                               'interface': interface,
                                               'network': network})

        if self.vcmp_manager and self.vcmp_manager.get_vcmp_host(bigip):
            interface = None
        try:
            model = {'name': vlan_name,
                     'interface': interface,
                     'partition': network_folder,
                     'description': network['id'],
                     'route_domain_id': network['route_domain_id']}
            self.network_helper.create_vlan(bigip, model)
        except Exception as err:
            LOG.exception("%s", err.message)
            raise f5_ex.VLANCreationException("Failed to create flat network")

        return vlan_name

    def _assure_device_network_vlan(self, network, bigip, network_folder):
        # Ensure bigip has configured tagged vlan
        # VLAN names are limited to 64 characters including
        # the folder name, so we name them foolish things.
        vlan_name = ""
        interface = self.interface_mapping['default']
        tagged = self.tagging_mapping['default']

        # Do we have host specific mappings?
        net_key = network['provider:physical_network']
        if net_key and net_key + ':' + bigip.hostname in \
                self.interface_mapping:
            interface = self.interface_mapping[
                net_key + ':' + bigip.hostname]
            tagged = self.tagging_mapping[
                net_key + ':' + bigip.hostname]
        # Do we have a mapping for this network
        elif net_key and net_key in self.interface_mapping:
            interface = self.interface_mapping[net_key]
            tagged = self.tagging_mapping[net_key]

        if tagged:
            vlanid = network['provider:segmentation_id']
        else:
            vlanid = 0

        vlan_name = self.get_vlan_name(network,
                                       bigip.hostname)

        self._assure_vcmp_device_network(bigip,
                                         vlan={'name': vlan_name,
                                               'folder': network_folder,
                                               'id': vlanid,
                                               'interface': interface,
                                               'network': network})

        if self.vcmp_manager and self.vcmp_manager.get_vcmp_host(bigip):
            interface = None
        try:
            model = {'name': vlan_name,
                     'interface': interface,
                     'tag': vlanid,
                     'partition': network_folder,
                     'description': network['id'],
                     'route_domain_id': network['route_domain_id']}
            self.network_helper.create_vlan(bigip, model)
        except Exception as err:
            LOG.exception("%s", err.message)
            raise f5_ex.VLANCreationException(
                "Failed to create vlan: %s" % vlan_name
            )

        if self.vlan_binding:
            self.vlan_binding.allow_vlan(
                device_name=bigip.device_name,
                interface=interface,
                vlanid=vlanid
            )

        return vlan_name

    def _assure_device_network_vxlan(self, network, bigip, partition):
        # Ensure bigip has configured vxlan
        tunnel_name = ""

        if not bigip.local_ip:
            error_message = 'Cannot create tunnel %s on %s' \
                % (network['id'], bigip.hostname)
            error_message += ' no VTEP SelfIP defined.'
            LOG.error('VXLAN:' + error_message)
            raise f5_ex.MissingVTEPAddress('VXLAN:' + error_message)

        tunnel_name = _get_tunnel_name(network)
        # create the main tunnel entry for the fdb records
        payload = {'name': tunnel_name,
                   'partition': partition,
                   'profile': 'vxlan_ovs',
                   'key': network['provider:segmentation_id'],
                   'localAddress': bigip.local_ip,
                   'network_id': network['id'],
                   'route_domain_id': network['route_domain_id']}
        try:
            self.driver.tunnel_handler.create_multipoint_tunnel(
                bigip, payload)
            if payload['partition'] != constants_v2.DEFAULT_PARTITION:
                self.network_helper.add_vlan_to_domain_by_id(
                    bigip, payload['name'], payload['partition'],
                    payload['route_domain_id'])
        except Exception as err:
            LOG.error("%s", err.message)
            raise f5_ex.VXLANCreationException(
                "Failed to create vxlan tunnel: %s" % tunnel_name
            )

        return tunnel_name

    def _assure_device_network_gre(self, network, bigip, partition):
        tunnel_name = ""

        # Ensure bigip has configured gre tunnel
        if not bigip.local_ip:
            error_message = 'Cannot create tunnel %s on %s' \
                % (network['id'], bigip.hostname)
            error_message += ' no VTEP SelfIP defined.'
            LOG.error('L2GRE:' + error_message)
            raise f5_ex.MissingVTEPAddress('L2GRE:' + error_message)

        tunnel_name = _get_tunnel_name(network)
        payload = {'name': tunnel_name,
                   'partition': partition,
                   'profile': 'gre_ovs',
                   'key': network['provider:segmentation_id'],
                   'localAddress': bigip.local_ip,
                   'network_id': network['id'],
                   'route_domain_id': network['route_domain_id']}
        try:
            self.driver.tunnel_handler.create_multipoint_tunnel(
                bigip, payload)
            if payload['partition'] != constants_v2.DEFAULT_PARTITION:
                self.network_helper.add_vlan_to_domain_by_id(
                    bigip, payload['name'], payload['partition'],
                    payload['route_domain_id'])
        except Exception as err:
            LOG.error("%s", err.message)
            raise f5_ex.VXLANCreationException(
                "Failed to create gre tunnel: %s" % tunnel_name
            )

        return tunnel_name

    def _assure_vcmp_device_network(self, bigip, vlan):
        if not self.vcmp_manager:
            return

        vcmp_host = self.vcmp_manager.get_vcmp_host(bigip)
        if not vcmp_host:
            return

        # Create the VLAN on the vCMP Host
        model = {'name': vlan['name'],
                 'partition': 'Common',
                 'tag': vlan['id'],
                 'interface': vlan['interface'],
                 'description': vlan['network']['id'],
                 'route_domain_id': vlan['network']['route_domain_id']}
        try:
            self.network_helper.create_vlan(vcmp_host['bigip'], model)
            LOG.debug(('Created VLAN %s on vCMP Host %s' %
                       (vlan['name'], vcmp_host['bigip'].hostname)))
        except Exception as exc:
            LOG.error(
                ('Exception creating VLAN %s on vCMP Host %s:%s' %
                 (vlan['name'], vcmp_host['bigip'].hostname, exc)))

        # Associate the VLAN with the vCMP Guest, if necessary
        self.vcmp_manager.assoc_vlan_with_vcmp_guest(bigip, vlan)

    def delete_bigip_network(self, bigip, network):
        # Delete network on bigip
        if network['id'] in self.conf.common_network_ids:
            LOG.debug('skipping delete of common network %s'
                      % network['id'])
            return
        if self.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = self.service_adapter.get_folder_name(
                network['tenant_id'])
        if network['provider:network_type'] == 'vlan':
            self._delete_device_vlan(bigip, network, network_folder)
        elif network['provider:network_type'] == 'flat':
            self._delete_device_flat(bigip, network, network_folder)
        elif network['provider:network_type'] == 'vxlan':
            self._delete_device_vxlan(bigip, network, network_folder)
        elif network['provider:network_type'] == 'gre':
            self._delete_device_gre(bigip, network, network_folder)
        elif network['provider:network_type'] == 'opflex':
            raise f5_ex.NetworkNotReady(
                "Opflex network segment definition required")
        else:
            LOG.error('Unsupported network type %s. Can not delete.'
                      % network['provider:network_type'])
        if network['id'] in bigip.assured_networks:
            del bigip.assured_networks[network['id']]

    def _delete_device_vlan(self, bigip, network, network_folder):
        # Delete tagged vlan on specific bigip
        vlan_name = self.get_vlan_name(network,
                                       bigip.hostname)
        try:
            self.network_helper.delete_vlan(
                bigip,
                vlan_name,
                partition=network_folder
            )
        except Exception as err:
            LOG.exception(err)
            LOG.error(
                "Failed to delete vlan: %s" % vlan_name)

        if self.vlan_binding:
            interface = self.interface_mapping['default']
            tagged = self.tagging_mapping['default']
            vlanid = 0
            # Do we have host specific mappings?
            net_key = network['provider:physical_network']
            if net_key and net_key + ':' + bigip.hostname in \
                    self.interface_mapping:
                interface = self.interface_mapping[
                    net_key + ':' + bigip.hostname]
                tagged = self.tagging_mapping[
                    net_key + ':' + bigip.hostname]
            # Do we have a mapping for this network
            elif net_key and net_key in self.interface_mapping:
                interface = self.interface_mapping[net_key]
                tagged = self.tagging_mapping[net_key]
            if tagged:
                vlanid = network['provider:segmentation_id']
            else:
                vlanid = 0

            self.vlan_binding.prune_vlan(
                device_name=bigip.device_name,
                interface=interface,
                vlanid=vlanid
            )

        self._delete_vcmp_device_network(bigip, vlan_name)

    def _delete_device_flat(self, bigip, network, network_folder):
        # Delete untagged vlan on specific bigip
        vlan_name = self.get_vlan_name(network,
                                       bigip.hostname)
        try:
            self.network_helper.delete_vlan(
                bigip,
                vlan_name,
                partition=network_folder
            )
        except Exception as err:
            LOG.exception(err)
            LOG.error(
                "Failed to delete vlan: %s" % vlan_name)

        self._delete_vcmp_device_network(bigip, vlan_name)

    def _delete_device_vxlan(self, bigip, network, network_folder):
        # Delete vxlan tunnel on specific bigip
        tunnel_name = _get_tunnel_name(network)

        try:
            self.driver.tunnel_handler.remove_multipoint_tunnel(
                bigip,
                tunnel_name,
                partition=network_folder)
        except Exception:
            # Just log the exception, we want to continue cleanup
            LOG.error(
                "Failed to delete vxlan tunnel: %s" % tunnel_name)

    def _delete_device_gre(self, bigip, network, network_folder):
        # Delete gre tunnel on specific bigip
        tunnel_name = _get_tunnel_name(network)

        try:
            self.driver.tunnel_handler.remove_multipoint_tunnel(
                bigip,
                tunnel_name,
                partition=network_folder)

        except Exception:
            # Just log the exception, we want to continue cleanup
            LOG.error(
                "Failed to delete gre tunnel: %s" % tunnel_name)

    def _delete_vcmp_device_network(self, bigip, vlan_name):
        '''Disassociated VLAN with vCMP Guest, then delete it from vCMP Host

        :param bigip: ManagementRoot object -- vCMP guest
        :param vlan_name: str -- name of vlan
        '''

        if not self.vcmp_manager:
            return
        vcmp_host = self.vcmp_manager.get_vcmp_host(bigip)
        if not vcmp_host:
            return
        self.vcmp_manager.disassoc_vlan_with_vcmp_guest(bigip, vlan_name)

    # Utilities
    def get_network_name(self, bigip, network):
        # This constructs a name for a tunnel or vlan interface
        preserve_network_name = False
        if network['id'] in self.conf.common_network_ids:
            network_name = self.conf.common_network_ids[network['id']]
            preserve_network_name = True
        elif network['provider:network_type'] == 'vlan':
            network_name = self.get_vlan_name(network,
                                              bigip.hostname)
        elif network['provider:network_type'] == 'flat':
            network_name = self.get_vlan_name(network,
                                              bigip.hostname)
        elif network['provider:network_type'] == 'vxlan':
            network_name = _get_tunnel_name(network)
        elif network['provider:network_type'] == 'gre':
            network_name = _get_tunnel_name(network)
        else:
            error_message = 'Unsupported network type %s.' \
                            % network['provider:network_type'] + \
                            ' Cannot setup selfip or snat.'
            LOG.error(error_message)
            raise f5_ex.InvalidNetworkType(error_message)
        return network_name, preserve_network_name

    def _get_network_folder(self, network):
        if self.is_common_network(network):
            return 'Common'
        else:
            return self.service_adapter.get_folder_name(network['tenant_id'])
