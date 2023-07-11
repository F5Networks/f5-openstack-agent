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

import random
from requests import HTTPError
from time import sleep
from time import time

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.confd import Vlan
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.fdb_connector_ml2 \
    import FDBConnectorML2
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper
from f5_openstack_agent.lbaasv2.drivers.bigip import utils as f5_utils

LOG = logging.getLogger(__name__)


def _get_tunnel_name(network):
    # BIG-IP object name for a tunnel
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


def _get_vteps(network, vtep_source):
    net_type = network['provider:network_type']
    vtep_type = net_type + '_vteps'
    return vtep_source.get(vtep_type, list())


class L2ServiceBuilder(object):

    def __init__(self, driver, f5_global_routed_mode):
        self.conf = driver.conf
        self.driver = driver
        self.f5_global_routed_mode = f5_global_routed_mode
        self.fdb_connector = None
        self.system_helper = SystemHelper()
        self.network_helper = NetworkHelper()
        self.service_adapter = ServiceModelAdapter(self.conf)

        if not f5_global_routed_mode:
            self.fdb_connector = FDBConnectorML2(self.conf)

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

    def get_vlan_name(self, network, interface_mapping,
                      vtep_node_ip="default"):
        # Construct a consistent vlan name
        net_key = network['provider:physical_network']
        net_type = network['provider:network_type']

        # look for host specific interface mapping
        if net_key and net_key in interface_mapping:
            interface = interface_mapping[net_key]
        else:
            interface = interface_mapping['default']

        # TODO(clean) if flat is never use, get_vlan_name never use
        # interface_mapping
        if net_type == "flat":
            interface_name = str(interface).replace(".", "-")
            if (len(interface_name) > 15):
                LOG.warn(
                    "Interface name is greater than 15 chars in length")
            vlan_name = "flat-%s" % (interface_name)
        else:
            # vlan_name cannot be longer than 64 characters.
            vlanid = f5_utils.get_vtep_vlan(network, vtep_node_ip)
            vlan_name = "vlan-%d" % (vlanid)

        return vlan_name

    def assure_bigip_network(self, bigip, network, device):
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
                network, bigip, network_folder, device)
        elif network['provider:network_type'] == 'vlan':
            network_name = self._assure_device_network_vlan(
                network, bigip, network_folder, device)
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
        # bigip.assured_networks[network['id']] = network_name
        LOG.debug("assured_network: %s" % network_name)

        if time() - start_time > .001:
            LOG.debug("        assure bigip network took %.5f secs" %
                      (time() - start_time))

    def _assure_device_network_flat(self, network, bigip, network_folder,
                                    device):
        # Ensure bigip has configured flat vlan (untagged)
        vlan_name = ""
        interface_mapping = device['bigip'][bigip.hostname][
            'device_info']['external_physical_mappings']
        LOG.info(
            "Create flat netowrk base on mapping %s." %
            interface_mapping
        )

        interface = f5_utils.get_net_iface(
            interface_mapping, network
        )
        LOG.info(
            "Get Flat interface %s for netowrk %s "
            "base on mapping %s." %
            (interface, network, interface_mapping)
        )

        vlan_name = self.get_vlan_name(
            network, interface_mapping)
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

    def _assure_device_network_vlan(self, network, bigip, network_folder,
                                    device):
        # TODO(nik) to check this function
        if bigip.f5os_client:
            vlan_name = ""
            interface = None

            if network.get('provider:segmentation_id'):
                vlanid = network['provider:segmentation_id']
            else:
                vlanid = 0
            # TODO(nik) to decide this part
            # vlan_name = self.get_vlan_name(network, bigip.hostname)
            vlan_name = "vlan-%d" % (vlanid)

            self._assure_f5os_vlan_network(vlanid, vlan_name, bigip)
            # If vlan is not in tenant partition, need to wait for F5OS to sync
            # it to /Common, delete it and then create it in tenant partition.
            interval = 1
            max_retries = 15
            while max_retries > 0:
                try:
                    self.network_helper.get_vlan_id(bigip, vlan_name,
                                                    network_folder)
                    break
                except HTTPError as ex:
                    if ex.response.status_code != 404:
                        raise ex

                try:
                    self.network_helper.get_vlan_id(bigip, vlan_name)
                    self.network_helper.delete_vlan(bigip, vlan_name)
                    break
                except HTTPError as ex:
                    if ex.response.status_code == 404:
                        LOG.debug("Vlan %s hasn't been synced from F5OS",
                                  vlan_name)
                        max_retries = max_retries - 1
                        if max_retries == 0:
                            raise ex
                        sleep(interval)
                        continue
                    else:
                        LOG.error("Vlan %s isn't synced from F5OS", vlan_name)
                        raise ex
        else:
            # Ensure bigip has configured tagged vlan
            # VLAN names are limited to 64 characters including
            # the folder name, so we name them foolish things.
            vlan_name = ""
            interface_mapping = device['bigip'][bigip.hostname][
                'device_info']['external_physical_mappings']

            LOG.info(
                "Create vlan network base on mapping %s." %
                interface_mapping
            )

            interface = f5_utils.get_net_iface(
                interface_mapping, network
            )
            LOG.info(
                "Get Vlan interface %s for netowrk %s "
                "base on mapping %s." %
                (interface, network, interface_mapping)
            )

            vtep_node_ip = f5_utils.get_node_vtep(device)
            LOG.info(
                "Get vtep_node_ip %s." % vtep_node_ip
            )

            vlanid = f5_utils.get_vtep_vlan(network, vtep_node_ip)
            vlan_name = self.get_vlan_name(
                network, interface_mapping, vtep_node_ip)

        try:
            model = {'name': vlan_name,
                     'interface': interface,
                     'tag': vlanid,
                     'partition': network_folder,
                     'description': network['id'],
                     'route_domain_id': network['route_domain_id']}
            self.network_helper.create_vlan(bigip, model)
        except Exception:
            raise f5_ex.VLANCreationException(
                "Failed to create vlan: %s" % vlan_name
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

    def _assure_f5os_vlan_network(self, vlan_id, vlan_name, bigip):
        if not bigip.f5os_client or not bigip.lag or not bigip.ve_tenant:
            return

        vlan = Vlan(bigip.f5os_client)
        vlan.create(vlan_id, vlan_name)
        bigip.lag.associateVlan(vlan_id)
        bigip.ve_tenant.associateVlan(vlan_id)

    def delete_bigip_network(self, bigip, network, device):
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
            self._delete_device_vlan(bigip, network, network_folder,
                                     device)
        elif network['provider:network_type'] == 'flat':
            self._delete_device_flat(bigip, network, network_folder,
                                     device)
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

    def _delete_device_vlan(self, bigip, network, network_folder,
                            device):
        # Delete tagged vlan on specific bigip
        interface_mapping = device['bigip'][bigip.hostname][
            'device_info']['external_physical_mappings']
        LOG.info(
            "Delete vlan network base on mapping %s." %
            interface_mapping
        )

        vtep_node_ip = f5_utils.get_node_vtep(device)
        LOG.info(
            "Get vtep_node_ip %s." % vtep_node_ip
        )

        vlan_name = self.get_vlan_name(
            network, interface_mapping, vtep_node_ip
        )
        try:
            self.network_helper.delete_vlan(
                bigip,
                vlan_name,
                partition=network_folder
            )
            # Delete vlan in F5OS after deleting it in BIGIP
            vlan_id = network["provider:segmentation_id"]
            self._delete_f5os_vlan_network(vlan_id, bigip)
        except HTTPError as err:
            if err.response.status_code == 404:
                LOG.info("vlan %s is not exist: %s, ignored.." % (
                        vlan_name, err.message))
        except Exception as err:
            LOG.exception(err)
            LOG.error(
                "Failed to delete vlan: %s" % vlan_name)

    def _delete_device_flat(self, bigip, network, network_folder,
                            device):
        # Delete untagged vlan on specific bigip
        interface_mapping = device['bigip'][bigip.hostname][
            'device_info']['external_physical_mappings']
        LOG.info(
            "Delete flat network base on mapping %s." %
            interface_mapping
        )
        vlan_name = self.get_vlan_name(
            network, interface_mapping)
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

    def _delete_f5os_vlan_network(self, vlan_id, bigip):
        '''Disassociated VLAN with Tenant, then delete it from F5OS

        :param vlan_id: -- id of vlan
        '''

        if not bigip.f5os_client or not bigip.ve_tenant or not bigip.lag:
            return

        LOG.debug("disassociating vlan %d with Tenant", vlan_id)
        bigip.ve_tenant.dissociateVlan(vlan_id)

        LOG.debug("disassociating vlan %d with lag", vlan_id)
        bigip.lag.dissociateVlan(vlan_id)

        LOG.debug("deleting vlan %d", vlan_id)
        # F5OS API may return 400, if deleting vlan immediately after
        # dissociating vlan from tenant or lag
        interval = 1
        max_retries = 15
        vlan = Vlan(bigip.f5os_client, vlan_id)
        while max_retries > 0:
            try:
                vlan.delete()
                break
            except HTTPError as ex:
                if ex.response.status_code == 400:
                    LOG.debug("Deleting vlan in F5OS: %s", ex.message)
                    max_retries = max_retries - 1
                    if max_retries == 0:
                        raise ex
                    sleep(interval)
                    continue
                else:
                    LOG.debug("Fail to delete vlan in F5OS: %s", ex.message)
                    raise ex

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
                    fdb_method(bigip, fdb_entries=fdbs)

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
    def get_network_name(self, bigip, network, device):
        # This constructs a name for a tunnel or vlan interface
        interface_mapping = device['bigip'][bigip.hostname][
            'device_info']['external_physical_mappings']
        vtep_node_ip = f5_utils.get_node_vtep(device)

        LOG.info(
            "Get netowrk name base on mapping %s."
            "Get vtep_node_ip %s." % (
                interface_mapping, vtep_node_ip
            )
        )
        preserve_network_name = False
        if network['id'] in self.conf.common_network_ids:
            network_name = self.conf.common_network_ids[network['id']]
            preserve_network_name = True
        elif network['provider:network_type'] == 'vlan':
            network_name = self.get_vlan_name(
                network, interface_mapping, vtep_node_ip)
        elif network['provider:network_type'] == 'flat':
            network_name = self.get_vlan_name(
                network, interface_mapping)
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

    def get_network_folder(self, network):
        if self.is_common_network(network):
            return 'Common'
        else:
            return self.service_adapter.get_folder_name(network['tenant_id'])

    def add_fdb_entries(self, bigips, loadbalancer, members):
        """Update fdb entries for loadbalancer and member VTEPs.

        :param bigips: one or more BIG-IPs to update.
        :param loadbalancer: Loadbalancer with VTEPs to update. Can be None.
        :param members: List of members. Can be emtpy ([]).
        """
        tunnel_records = self.create_fdb_records(loadbalancer, members)
        if tunnel_records:
            for bigip in bigips:
                self.network_helper.add_fdb_entries(bigip,
                                                    fdb_entries=tunnel_records)

    def delete_fdb_entries(self, bigips, loadbalancer, members):
        """Remove fdb entries for loadbalancer and member VTEPs.

        :param bigips: one or more BIG-IPs to update.
        :param loadbalancer: Loadbalancer with VTEPs to remove. Can be None.
        :param members: List of members. Can be emtpy ([]).
        """
        tunnel_records = self.create_fdb_records(loadbalancer, members)
        if tunnel_records:
            for bigip in bigips:
                self.network_helper.delete_fdb_entries(
                    bigip,
                    fdb_entries=tunnel_records)

    def create_fdb_records(self, loadbalancer, members):
        fdbs = dict()

        if loadbalancer:
            network = loadbalancer['network']
            tunnel_name = _get_tunnel_name(network)
            fdbs[tunnel_name] = dict()
            fdbs[tunnel_name]['folder'] = self.get_network_folder(network)
            records = dict()
            fdbs[tunnel_name]['records'] = records
            self.append_loadbalancer_fdb_records(
                network, loadbalancer, records)

        for member in members:
            network = member['network']
            tunnel_name = _get_tunnel_name(network)
            if tunnel_name not in fdbs:
                fdbs[tunnel_name] = dict()
                fdbs[tunnel_name]['folder'] = self.get_network_folder(network)
                fdbs[tunnel_name]['records'] = dict()

            records = fdbs[tunnel_name]['records']
            if 'port' in member and 'mac_address' in member['port']:
                mac_addr = member['port']['mac_address']
                self.append_member_fdb_records(network,
                                               member,
                                               records,
                                               mac_addr,
                                               ip_address=member['address'])

        return fdbs

    def append_loadbalancer_fdb_records(self, network, loadbalancer, records):
        vteps = _get_vteps(network, loadbalancer)
        for vtep in vteps:
            # create an arbitrary MAC address for VTEP
            mac_addr = _get_tunnel_fake_mac(network, vtep)
            records[mac_addr] = {'endpoint': vtep, 'ip_address': ''}

    def append_member_fdb_records(self, network, member, records,
                                  mac_addr, ip_address=''):
        vteps = _get_vteps(network, member)
        for vtep in vteps:
            records[mac_addr] = {'endpoint': vtep,
                                 'ip_address': ip_address}
