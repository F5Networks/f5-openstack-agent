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

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType

LOG = logging.getLogger(__name__)


class SystemHelper(object):

    def __init__(self):
        self.exempt_folders = ['/', 'Common']

    def create_folder(self, bigip, folder):
        f = bigip.tm.sys.folders.folder
        f.create(**folder)

    def delete_folder(self, bigip, folder_name):
        f = bigip.tm.sys.folders.folder
        if f.exists(name=folder_name):
            obj = f.load(name=folder_name)
            obj.delete()

    def folder_exists(self, bigip, folder):
        if folder == 'Common':
            return True

        return bigip.tm.sys.folders.folder.exists(name=folder)

    def get_folders(self, bigip):
        f_collection = []
        folders = bigip.tm.sys.folders.get_collection()
        for folder in folders:
            f_collection.append(folder.name)

        return f_collection

    def get_major_version(self, bigip):
        version = self.get_version(bigip)
        if version:
            return version.split('.')[0]

        return version

    def get_minor_version(self, bigip):
        version = self.get_version(bigip)
        if version:
            return version.split('.')[1]

        return version

    def get_version(self, bigip):
        devices = bigip.tm.cm.devices.get_collection()
        for device in devices:
            if device.selfDevice == 'true':
                return device.version

        return ""

    def get_serial_number(self, bigip):
        devices = bigip.tm.cm.devices.get_collection()
        for device in devices:
            if device.selfDevice == 'true':
                return device.chassisId

        return None

    def get_platform(self, bigip):
        return ''

    def get_tunnel_sync(self, bigip):
        db = bigip.tm.sys.dbs.db.load(name='iptunnel.configsync')
        if hasattr(db, 'value'):
            return db.value

        return ''

    def set_tunnel_sync(self, bigip, enabled=False):

        if enabled:
            val = 'enable'
        else:
            val = 'disable'
        db = bigip.tm.sys.dbs.db.load(name='iptunnel.configsync')
        db.modify(value=val)

    def get_provision_extramb(self, bigip):
        db = bigip.tm.sys.dbs.db.load(name='provision.extramb')
        if hasattr(db, 'value'):
            return db.value

        return 0

    def get_mac_addresses(self, bigip):
        macs = []
        interfaces = bigip.tm.net.interfaces.get_collection()
        for interface in interfaces:
            macs.append(interface.macAddress)
        return macs

    def get_interface_macaddresses_dict(self, bigip):
        # Get dictionary of mac addresses keyed by their interface name
        mac_dict = {}
        interfaces = bigip.tm.net.interfaces.get_collection()
        for interface in interfaces:
            mac_dict[interface.name] = interface.macAddress
        return mac_dict

    def purge_orphaned_folders(self, bigip):
        LOG.error("method not implemented")

    def purge_orphaned_folders_contents(self, bigip, folders):
        LOG.error("method not implemented")

    def purge_folder_contents(self, bigip, folder):
        network_helper = NetworkHelper()

        if folder not in self.exempt_folders:

            # First remove all LTM resources.
            ltm_types = [
                ResourceType.virtual,
                ResourceType.pool,
                ResourceType.http_monitor,
                ResourceType.https_monitor,
                ResourceType.tcp_monitor,
                ResourceType.ping_monitor,
                ResourceType.node,
                ResourceType.snat,
                ResourceType.snatpool,
                ResourceType.snat_translation,
                ResourceType.rule
            ]
            for ltm_type in ltm_types:
                resource = BigIPResourceHelper(ltm_type)
                [r.delete() for r in resource.get_resources(bigip, folder)]

            # Remove all net resources
            net_types = [
                ResourceType.arp,
                ResourceType.selfip,
                ResourceType.vlan,
                ResourceType.route_domain
            ]
            for net_type in net_types:
                resource = BigIPResourceHelper(net_type)
                [r.delete() for r in resource.get_resources(bigip, folder)]

            # Tunnels and fdb's require some special attention.
            resource = BigIPResourceHelper(ResourceType.tunnel)
            tunnels = resource.get_resources(bigip, folder)
            for tunnel in tunnels:
                network_helper.delete_all_fdb_entries(
                    bigip, tunnel.name, folder)
                network_helper.delete_tunnel(
                    bigip, tunnel.name, folder)

    def purge_folder(self, bigip, folder):
        if folder not in self.exempt_folders:
            self.delete_folder(bigip, folder)
        else:
            LOG.error(
                ('Request to purge exempt folder %s ignored.' %
                 folder))

    def get_tenant_folder_count(self, bigip):
        folders = bigip.tm.sys.folders.get_collection()
        # ignore '/' and 'Common'
        tenants = [item for item in folders if item.name != '/' and
                   item.name != 'Common']
        return len(tenants)
