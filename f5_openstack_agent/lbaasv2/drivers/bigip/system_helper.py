# Copyright (c) 2014-2023, F5 Networks, Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import Device
from f5_openstack_agent.lbaasv2.drivers.bigip.resource \
    import Folder

LOG = logging.getLogger(__name__)


class SystemHelper(object):

    def __init__(self):
        pass

    def create_folder(self, bigip, folder):
        f = Folder()
        f.create(bigip, folder)

    def delete_folder(self, bigip, folder_name):
        f = Folder()
        f.delete(bigip, name=folder_name)

    def folder_exists(self, bigip, folder):
        if folder == 'Common':
            return True

        f = Folder()
        return f.exists(bigip, name=folder)

    def get_folders(self, bigip):
        f_collection = []
        f = Folder()
        folders = f.get_resources(bigip)
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
        d = Device()
        devices = d.get_resources(bigip)
        for device in devices:
            if device.selfDevice == 'true':
                return device.version

        return ""

    def get_serial_number(self, bigip):
        d = Device()
        devices = d.get_resources(bigip)
        for device in devices:
            if device.selfDevice == 'true':
                return device.chassisId

        return None

    def get_platform(self, bigip):
        d = Device()
        devices = d.get_resources(bigip)
        for device in devices:
            if device.selfDevice == 'true':
                return device.platformId

        return ''

    def get_active_modules(self, bigip):
        d = Device()
        devices = d.get_resources(bigip)
        for device in devices:
            if device.selfDevice == 'true':
                return device.activeModules

        return []
