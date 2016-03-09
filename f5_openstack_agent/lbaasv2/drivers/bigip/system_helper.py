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

LOG = logging.getLogger(__name__)


class SystemHelper(object):

    def create_folder(self, bigip, folder):
        f = bigip.sys.folders.folder
        f.create(**folder)

    def delete_folder(self, bigip, folder_name):
        f = bigip.sys.folders.folder
        if f.exists(name=folder_name):
            f.load(name=folder_name)
            f.delete()

    def folder_exists(self, bigip, folder):
        if folder == 'Common':
            return True

        return bigip.sys.folders.folder.exists(name=folder)

    def get_folders(self, bigip):
        f_collection = []
        folders = bigip.sys.folders.get_collection()
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
        devices = bigip.cm.devices.get_collection()
        for device in devices:
            if device.selfDevice == 'true':
                return device.version

        return ""

    def get_serial_number(self, bigip):
        devices = bigip.cm.devices.get_collection()
        for device in devices:
            if device.selfDevice == 'true':
                return device.chassisId

        return None

    def get_platform(self, bigip):
        return ''

    def get_tunnel_sync(self, bigip):
        db = bigip.sys.dbs.db.load(name='iptunnel.configsync')
        if hasattr(db, 'value'):
            return db.value

        return ''

    def set_tunnel_sync(self, bigip, enabled=False):

        # if enabled:
        #    val = 'enable'
        # else:
        #    val = 'disable'
        # db = bigip.sys.dbs.db.load(name='iptunnel.configsync')
        # db.update(value=val)
        pass

    def get_provision_extramb(self, bigip):
        db = bigip.sys.dbs.db.load(name='provision.extramb')
        if hasattr(db, 'value'):
            return db.value

        return 0

    def get_mac_addresses(self, bigip):
        macs = []
        interfaces = bigip.net.interfaces.get_collection()
        for interface in interfaces:
            macs.append(interface.macAddress)
        return macs

    def get_interface_macaddresses_dict(self, bigip):
        # Get dictionary of mac addresses keyed by their interface name
        mac_dict = {}
        interfaces = bigip.net.interfaces.get_collection()
        for interface in interfaces:
            mac_dict[interface.name] = interface.macAddress
        return mac_dict

    # TODO(jl)
    def purge_orphaned_folders(self, bigip):
        pass

    def force_root_folder(self, bigip):
        pass

    def purge_orphaned_folders_contents(self, bigip, folders):
        pass

    def purge_folder_contents(self, bigip, folder):
        pass
