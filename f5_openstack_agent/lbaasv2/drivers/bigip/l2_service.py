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

import random
from time import time

from oslo_log import log as logging
from oslo_utils import importutils

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.fdb_connector_ml2 \
    import FDBConnectorML2
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper

LOG = logging.getLogger(__name__)


# TODO(jl) resolve use of prefixed
def prefixed(name):
    return name


def _get_tunnel_name(network):
    # BIG-IP® object name for a tunnel
    tunnel_type = network['provider:network_type']
    tunnel_id = network['provider:segmentation_id']
    return 'tunnel-' + str(tunnel_type) + '-' + str(tunnel_id)


def _get_tunnel_fake_mac(network, local_ip):
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


class L2ServiceBuilder(object):

    def __init__(self, conf, f5_global_routed_mode):
        self.conf = conf
        self.f5_global_routed_mode = f5_global_routed_mode
        self.vlan_binding = None
        self.fdb_connector = None
        self.vcmp_manager = None
        self.interface_mapping = {}
        self.tagging_mapping = {}
        self.system_helper = SystemHelper()
        self.network_helper = NetworkHelper()
        self.service_adapter = ServiceModelAdapter(conf)

        if not f5_global_routed_mode:
            self.fdb_connector = FDBConnectorML2(conf)

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

    def post_init(self):
        if self.vlan_binding:
            LOG.debug(
                'Getting BIG-IP device interface for VLAN Binding')
            self.vlan_binding.register_bigip_interfaces()

    def tunnel_sync(self, tunnel_ips):
        if self.fdb_connector:
            self.fdb_connector.advertise_tunnel_ips(tunnel_ips)

    def set_tunnel_rpc(self, tunnel_rpc):
        # Provide FDB Connector with ML2 RPC access
        if self.fdb_connector:
            self.fdb_connector.set_tunnel_rpc(tunnel_rpc)

    def set_l2pop_rpc(self, l2pop_rpc):
        # Provide FDB Connector with ML2 RPC access
        if self.fdb_connector:
            self.fdb_connector.set_l2pop_rpc(l2pop_rpc)

    def set_context(self, context):
        if self.fdb_connector:
            self.fdb_connector.set_context(context)

    def is_common_network(self, network):
        # Does this network belong in the /Common folder?
        return network['shared'] or \
            (network['id'] in self.conf.common_network_ids) or \
            ('router:external' in network and
             network['router:external'] and
             self.conf.f5_common_external_networks)

    def get_vlan_name(self, network, hostname):
        # Construct a consistent vlan name
        net_key = network['provider:physical_network']
        # look for host specific interface mapping
        if net_key + ':' + hostname in self.interface_mapping:
            interface = self.interface_mapping[net_key + ':' + hostname]
            tagged = self.tagging_mapping[net_key + ':' + hostname]
        # look for specific interface mapping
        elif net_key in self.interface_mapping:
            interface = self.interface_mapping[net_key]
            tagged = self.tagging_mapping[net_key]
        # use default mapping
        else:
            interface = self.interface_mapping['default']
            tagged = self.tagging_mapping['default']

        if tagged:
            vlanid = network['provider:segmentation_id']
        else:
            vlanid = 0

        vlan_name = "vlan-" + \
                    str(interface).replace(".", "-") + \
                    "-" + str(vlanid)
        if len(vlan_name) > 15:
            vlan_name = 'vlan-tr-' + str(vlanid)
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
        if net_key + ':' + bigip.hostname in \
                self.interface_mapping:
            interface = self.interface_mapping[
                net_key + ':' + bigip.hostname]
        # Do we have a mapping for this network
        elif net_key in self.interface_mapping:
            interface = self.interface_mapping[net_key]

        vlan_name = self.get_vlan_name(network,
                                       bigip.hostname)

        # TODO(Rich Browne): Implementation with VCMP
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
        if net_key + ':' + bigip.hostname in \
                self.interface_mapping:
            interface = self.interface_mapping[
                net_key + ':' + bigip.hostname]
            tagged = self.tagging_mapping[
                net_key + ':' + bigip.hostname]
        # Do we have a mapping for this network
        elif net_key in self.interface_mapping:
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
                   'description': network['id'],
                   'route_domain_id': network['route_domain_id']}
        try:
            self.network_helper.create_multipoint_tunnel(bigip, payload)
        except Exception as err:
            LOG.exception("%s", err.message)
            raise f5_ex.VXLANCreationException(
                "Failed to create vxlan tunnel: %s" % tunnel_name
            )

        if self.fdb_connector:
            self.fdb_connector.notify_vtep_added(network, bigip.local_ip)

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
                   'description': network['id'],
                   'route_domain_id': network['route_domain_id']}
        try:
            self.network_helper.create_multipoint_tunnel(bigip, payload)
        except Exception as err:
            LOG.exception("%s", err.message)
            raise f5_ex.VXLANCreationException(
                "Failed to create gre tunnel: %s" % tunnel_name
            )

        if self.fdb_connector:
            self.fdb_connector.notify_vtep_added(network, bigip.local_ip)

        return tunnel_name

    def _is_vlan_assoc_with_vcmp_guest(self, bigip, vlan):
        if not self.vcmp_manager:
            return False

        # Is a vlan associated with a vcmp_guest?
        try:
            vcmp_host = self.vcmp_manager.get_vcmp_host(bigip)
            vcmp_guest = self.vcmp_manager.get_vcmp_guest(vcmp_host, bigip)
            vlan_list = vcmp_host['bigip'].system.sys_vcmp.get_vlan(
                [vcmp_guest['name']])
            full_path_vlan_name = '/Common/' + prefixed(vlan['name'])
            if full_path_vlan_name in vlan_list[0]:
                LOG.debug(('VLAN %s is associated with guest %s' %
                           (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
                return True
        except Exception as exc:
            LOG.error(('Exception checking association of VLAN %s '
                       'to vCMP Guest %s: %s ' %
                       (vlan['name'], vcmp_guest['mgmt_addr'], exc)))
            return False
        LOG.debug(('VLAN %s is not associated with guest %s' %
                  (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
        return False

    def _assure_vcmp_device_network(self, bigip, vlan):
        # REVISIT FOR VCMP SUPPORT
        # For vCMP Guests, add VLAN to vCMP Host, associate VLAN with
        # vCMP Guest, and remove VLAN from /Common on vCMP Guest.
        if not self.vcmp_manager:
            return

        vcmp_host = self.vcmp_manager.get_vcmp_host(bigip)
        if not vcmp_host:
            return

        # Create the VLAN on the vCMP Host
        try:
            model = {'name': vlan['name'],
                     'partition': '/Common',
                     'tag': vlan['id'],
                     'interface': vlan['interface'],
                     'description': vlan['network']['id'],
                     'route_domain_id': vlan['network']['route_domain_id']}
            self.network_helper.create_vlan(bigip, model)
            LOG.debug(('Created VLAN %s on vCMP Host %s' %
                       (vlan['name'], vcmp_host['bigip'].hostname)))
        except Exception as exc:
            LOG.error(
                ('Exception creating VLAN %s on vCMP Host %s:%s' %
                 (vlan['name'], vcmp_host['bigip'].hostname, exc)))

        # Determine if the VLAN is already associated with the vCMP Guest
        if self._is_vlan_assoc_with_vcmp_guest(bigip, vlan):
            return

        # Associate the VLAN with the vCMP Guest
        # MSG: bigip.system does not exist
        vcmp_guest = self.vcmp_manager.get_vcmp_guest(vcmp_host, bigip)
        try:
            vlan_seq = vcmp_host['bigip'].system.sys_vcmp.typefactory.\
                create('Common.StringSequence')
            vlan_seq.values = prefixed(vlan['name'])
            vlan_seq_seq = vcmp_host['bigip'].system.sys_vcmp.typefactory.\
                create('Common.StringSequenceSequence')
            vlan_seq_seq.values = [vlan_seq]
            vcmp_host['bigip'].system.sys_vcmp.add_vlan([vcmp_guest['name']],
                                                        vlan_seq_seq)
            LOG.debug(('Associated VLAN %s with vCMP Guest %s' %
                       (vlan['name'], vcmp_guest['mgmt_addr'])))
        except Exception as exc:
            LOG.error(('Exception associating VLAN %s to vCMP Guest %s: %s '
                      % (vlan['name'], vcmp_guest['mgmt_addr'], exc)))

        # Wait for the VLAN to propagate to /Common on vCMP Guest
        full_path_vlan_name = '/Common/' + prefixed(vlan['name'])
        vlan_created = False
        vf = bigip.tm.net.vlans.vlan
        try:
            for _ in range(0, 30):
                if vf.exists(name=vlan['name'], partition='/Common'):
                    v = vf.load(name=vlan['name'], partition='/Common')
                    vlan_created = True
                    break
                LOG.debug(('Wait for VLAN %s to be created on vCMP Guest %s.'
                          % (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
                # sleep(1)

            if vlan_created:
                LOG.debug(('VLAN %s exists on vCMP Guest %s.' %
                          (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
            else:
                LOG.error(('VLAN %s does not exist on vCMP Guest %s.' %
                          (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
        except Exception as exc:
            LOG.error(('Exception waiting for vCMP Host VLAN %s to '
                       'be created on vCMP Guest %s: %s' %
                      (vlan['name'], vcmp_guest['mgmt_addr'], exc)))

        # Delete the VLAN from the /Common folder on the vCMP Guest
        if vlan_created:
            try:
                v.delete()
                LOG.debug(('Deleted VLAN %s from vCMP Guest %s' %
                          (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
            except Exception as exc:
                LOG.error(
                    ('Exception deleting VLAN %s from vCMP Guest %s: %s' %
                     (full_path_vlan_name, vcmp_guest['mgmt_addr'], exc)))

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
            if net_key + ':' + bigip.hostname in \
                    self.interface_mapping:
                interface = self.interface_mapping[
                    net_key + ':' + bigip.hostname]
                tagged = self.tagging_mapping[
                    net_key + ':' + bigip.hostname]
            # Do we have a mapping for this network
            elif net_key in self.interface_mapping:
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
            self.network_helper.delete_all_fdb_entries(
                bigip,
                tunnel_name,
                partition=network_folder)

            self.network_helper.delete_tunnel(
                bigip,
                tunnel_name,
                partition=network_folder)
        except Exception as err:
            # Just log the exception, we want to continue cleanup
            LOG.exception(err)
            LOG.error(
                "Failed to delete vxlan tunnel: %s" % tunnel_name)

        if self.fdb_connector:
            self.fdb_connector.notify_vtep_removed(network, bigip.local_ip)

    def _delete_device_gre(self, bigip, network, network_folder):
        # Delete gre tunnel on specific bigip
        tunnel_name = _get_tunnel_name(network)

        try:
            self.network_helper.delete_all_fdb_entries(
                bigip,
                tunnel_name,
                partition=network_folder)

            self.network_helper.delete_tunnel(
                bigip,
                tunnel_name,
                partition=network_folder)

        except Exception as err:
            # Just log the exception, we want to continue cleanup
            LOG.exception(err)
            LOG.error(
                "Failed to delete gre tunnel: %s" % tunnel_name)

        if self.fdb_connector:
            self.fdb_connector.notify_vtep_removed(network, bigip.local_ip)

    def _delete_vcmp_device_network(self, bigip, vlan_name):
        # For vCMP Guests, disassociate VLAN from vCMP Guest and
        # delete VLAN from vCMP Host.

        if not self.vcmp_manager:
            return

        vcmp_host = self.vcmp_manager.get_vcmp_host(bigip)
        if not vcmp_host:
            return

        # Remove VLAN association from the vCMP Guest
        vcmp_guest = self.vcmp_manager.get_vcmp_guest(vcmp_host, bigip)
        try:
            # REVISIT: the extra attributes in vcmp bigips need to be
            # worked on.
            vlan_seq = vcmp_host['bigip'].system.sys_vcmp.typefactory.\
                create('Common.StringSequence')
            vlan_seq.values = prefixed(vlan_name)
            vlan_seq_seq = vcmp_host['bigip'].system.sys_vcmp.typefactory.\
                create('Common.StringSequenceSequence')
            vlan_seq_seq.values = [vlan_seq]
            vcmp_host['bigip'].system.sys_vcmp.remove_vlan(
                [vcmp_guest['name']], vlan_seq_seq)
            LOG.debug(('Removed VLAN %s association from vCMP Guest %s' %
                      (vlan_name, vcmp_guest['mgmt_addr'])))
        except Exception as exc:
            LOG.error(('Exception removing VLAN %s association from vCMP '
                       'Guest %s:%s' %
                       (vlan_name, vcmp_guest['mgmt_addr'], exc)))

        # Only delete VLAN if it is not in use by other vCMP Guests
        if self.vcmp_manager.get_vlan_use_count(vcmp_host, vlan_name):
            LOG.debug(('VLAN %s in use by other vCMP Guests on vCMP Host %s' %
                      (vlan_name, vcmp_host['bigip'].hostname)))
            return

        # Delete VLAN from vCMP Host.  This will fail if any other vCMP Guest
        # is using this VLAN
        try:
            self.network_helper.delete_vlan(
                vcmp_host['bigip'],
                vlan_name)
            LOG.debug(('Deleted VLAN %s from vCMP Host %s' %
                      (vlan_name, vcmp_host['bigip'].hostname)))
        except Exception as exc:
            LOG.error(('Exception deleting VLAN %s from vCMP Host %s:%s' %
                      (vlan_name, vcmp_host['bigip'].icontrol.hostname, exc)))

    def add_bigip_fdbs(self, bigip, net_folder, fdb_info, vteps_by_type):
        # Add fdb records for a mac/ip with specified vteps
        network = fdb_info['network']
        net_type = network['provider:network_type']
        vteps_key = net_type + '_vteps'
        if vteps_key in vteps_by_type:
            vteps = vteps_by_type[vteps_key]
            if net_type == 'gre':
                self.add_gre_fdbs(bigip, net_folder, fdb_info, vteps)
            elif net_type == 'vxlan':
                self.add_vxlan_fdbs(bigip, net_folder, fdb_info, vteps)

    def add_gre_fdbs(self, bigip, net_folder, fdb_info, vteps):
        # Add gre fdb records
        network = fdb_info['network']
        ip_address = fdb_info['ip_address']
        mac_address = fdb_info['mac_address']
        tunnel_name = _get_tunnel_name(network)
        for vtep in vteps:
            if mac_address:
                mac_addr = mac_address
            else:
                mac_addr = _get_tunnel_fake_mac(network, vtep)
            self.network_helper.add_fdb_entry(
                bigip,
                tunnel_name=tunnel_name,
                partition=net_folder,
                mac_address=mac_addr,
                vtep_ip_address=vtep,
                arp_ip_address=ip_address)

    def add_vxlan_fdbs(self, bigip, net_folder, fdb_info, vteps):
        # Add vxlan fdb records
        network = fdb_info['network']
        ip_address = fdb_info['ip_address']
        mac_address = fdb_info['mac_address']
        tunnel_name = _get_tunnel_name(network)
        for vtep in vteps:
            if mac_address:
                mac_addr = mac_address
            else:
                mac_addr = _get_tunnel_fake_mac(network, vtep)

            self.network_helper.add_fdb_entry(
                bigip,
                tunnel_name=tunnel_name,
                partition=net_folder,
                mac_address=mac_addr,
                vtep_ip_address=vtep,
                arp_ip_address=ip_address)

    def delete_bigip_fdbs(self, bigip, net_folder, fdb_info, vteps_by_type):
        # Delete fdb records for a mac/ip with specified vteps
        network = fdb_info['network']
        net_type = network['provider:network_type']
        vteps_key = net_type + '_vteps'
        if vteps_key in vteps_by_type:
            vteps = vteps_by_type[vteps_key]
            if net_type == 'gre':
                self.delete_gre_fdbs(bigip, net_folder, fdb_info, vteps)
            elif net_type == 'vxlan':
                self.delete_vxlan_fdbs(bigip, net_folder, fdb_info, vteps)

    def delete_gre_fdbs(self, bigip, net_folder, fdb_info, vteps):
        # delete gre fdb records
        network = fdb_info['network']
        ip_address = fdb_info['ip_address']
        mac_address = fdb_info['mac_address']
        tunnel_name = _get_tunnel_name(network)
        for vtep in vteps:
            if mac_address:
                mac_addr = mac_address
            else:
                mac_addr = _get_tunnel_fake_mac(network, vtep)

            self.network_helper.delete_fdb_entry(
                bigip,
                tunnel_name=tunnel_name,
                mac_address=mac_addr,
                arp_ip_address=ip_address,
                partition=net_folder)

    def delete_vxlan_fdbs(self, bigip, net_folder, fdb_info, vteps):
        # delete vxlan fdb records
        network = fdb_info['network']
        ip_address = fdb_info['ip_address']
        mac_address = fdb_info['mac_address']
        tunnel_name = _get_tunnel_name(network)
        for vtep in vteps:
            if mac_address:
                mac_addr = mac_address
            else:
                mac_addr = _get_tunnel_fake_mac(network, vtep)
            self.network_helper.delete_fdb_entry(
                bigip,
                tunnel_name=tunnel_name,
                mac_address=mac_addr,
                arp_ip_address=ip_address,
                partition=net_folder)

    def add_bigip_fdb(self, bigip, fdb):
        # Add entries from the fdb relevant to the bigip
        for fdb_operation in \
            [{'network_type': 'vxlan',
              'get_tunnel_folder': self.network_helper.get_tunnel_folder,
              'fdb_method': self.network_helper.add_fdb_entries},

             {'network_type': 'gre',
              'get_tunnel_folder': self.network_helper.get_tunnel_folder,
              'fdb_method': self.network_helper.add_fdb_entries}]:
            self._operate_bigip_fdb(bigip, fdb, fdb_operation)

    def _operate_bigip_fdb(self, bigip, fdb, fdb_operation):
        """Add L2 records for MAC addresses behind tunnel endpoints.

            Description of fdb structure:
            {'<network_id>':
                'segment_id': <int>
                'ports': [ '<vtep>': ['<mac_address>': '<ip_address>'] ]
             '<network_id>':
                'segment_id':
                'ports': [ '<vtep>': ['<mac_address>': '<ip_address>'] ] }

            Sample real fdb structure:
            {u'45bbbce1-191b-4f7b-84c5-54c6c8243bd2':
                {u'segment_id': 1008,
                 u'ports':
                     {u'10.30.30.2': [[u'00:00:00:00:00:00', u'0.0.0.0'],
                                      [u'fa:16:3e:3d:7b:7f', u'10.10.1.4']]},
                 u'network_type': u'vxlan'}}
        """
        network_type = fdb_operation['network_type']
        get_tunnel_folder = fdb_operation['get_tunnel_folder']
        fdb_method = fdb_operation['fdb_method']

        for network in fdb:
            net_fdb = fdb[network]
            if net_fdb['network_type'] == network_type:
                net = {'name': network,
                       'provider:network_type': net_fdb['network_type'],
                       'provider:segmentation_id': net_fdb['segment_id']}
                tunnel_name = _get_tunnel_name(net)
                folder = get_tunnel_folder(bigip, tunnel_name=tunnel_name)
                net_info = {'network': network,
                            'folder': folder,
                            'tunnel_name': tunnel_name,
                            'net_fdb': net_fdb}
                fdbs = self._get_bigip_network_fdbs(bigip, net_info)
                if len(fdbs) > 0:
                    fdb_method(fdb_entries=fdbs)

    def _get_bigip_network_fdbs(self, bigip, net_info):
        # Get network fdb entries to add to a bigip
        if not net_info['folder']:
            return {}
        net_fdb = net_info['net_fdb']
        fdbs = {}
        for vtep in net_fdb['ports']:
            # bigip does not need to set fdb entries for local addresses
            if vtep == bigip.local_ip:
                continue

            # most net_info applies to the vtep
            vtep_info = dict(net_info)
            # but the network fdb is too broad so delete it
            del vtep_info['net_fdb']
            # use a slice of the fdb for the vtep instead
            vtep_info['vtep'] = vtep
            vtep_info['fdb_entries'] = net_fdb['ports'][vtep]

            self._merge_vtep_fdbs(vtep_info, fdbs)
        return fdbs

    def _merge_vtep_fdbs(self, vtep_info, fdbs):
        # Add L2 records for a specific network+vtep
        folder = vtep_info['folder']
        tunnel_name = vtep_info['tunnel_name']
        for entry in vtep_info['fdb_entries']:
            mac_address = entry[0]
            if mac_address == '00:00:00:00:00:00':
                continue
            ip_address = entry[1]

            # create/get tunnel data
            if tunnel_name not in fdbs:
                fdbs[tunnel_name] = {}
            tunnel_fdbs = fdbs[tunnel_name]
            # update tunnel folder
            tunnel_fdbs['folder'] = folder

            # maybe create records for tunnel
            if 'records' not in tunnel_fdbs:
                tunnel_fdbs['records'] = {}

            # add entry to records map keyed by mac address
            tunnel_fdbs['records'][mac_address] = \
                {'endpoint': vtep_info['vtep'], 'ip_address': ip_address}

    def update_bigip_fdb(self, bigip, fdb):
        # Update l2 records
        self.add_bigip_fdb(bigip, fdb)

    def remove_bigip_fdb(self, bigip, fdb):
        # Add L2 records for MAC addresses behind tunnel endpoints
        for fdb_operation in \
            [{'network_type': 'vxlan',
              'get_tunnel_folder': self.network_helper.get_tunnel_folder,
              'fdb_method': self.network_helper.delete_fdb_entries},
             {'network_type': 'gre',
              'get_tunnel_folder': self.network_helper.get_tunnel_folder,
              'fdb_method': self.network_helper.delete_fdb_entries}]:
            self._operate_bigip_fdb(bigip, fdb, fdb_operation)

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
