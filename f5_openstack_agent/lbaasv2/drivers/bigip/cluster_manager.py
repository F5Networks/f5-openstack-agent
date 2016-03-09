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


class ClusterManager(object):

    def devices(self, bigip):
        return bigip.cm.devices.get_collection()

    def disable_auto_sync(self, device_group_name, bigip, partition='Common'):
        dg = bigip.cm.device_groups.device_group.load(name=device_group_name,
                                                      partition=partition)
        dg.update(autoSync='disabled')

    def enable_auto_sync(self, device_group_name, bigip, partition='Common'):
        dg = bigip.cm.device_groups.device_group.load(name=device_group_name,
                                                      partition=partition)
        dg.update(autoSync='enabled')

    def get_sync_status(self, bigip):
        # need bigip.cm.sync-status
        return ''

    def get_traffic_groups(self, bigip):
        traffic_groups = []
        groups = bigip.cm.traffic_groups.get_collection()
        for group in groups:
            traffic_groups.append(group.name)

        return traffic_groups

    def sync(self, bigip, name, force_now=False):
        # force_now=True is typically used for initial sync.
        # In order to avoid sync problems, you should wait until devices
        # in the group are connected.
        pass

    def sync_local_device_to_group(self, device_group_name):
        pass

    def save_config(self, bigip):
        # need bigip.sys.config
        pass

    def get_device_group(self, bigip):
        dgs = bigip.cm.device_groups.get_collection()
        for dg in dgs:
            if dg.type == 'sync-failover':
                return dg.name

        return None

    def get_device_name(self, bigip):
        devices = self.devices(bigip)
        for device in devices:
            if device.selfDevice == 'true':
                return device.name

        return None

    def get_mgmt_addr_by_device(self, bigip, device_name):
        devices = self.devices(bigip)
        for device in devices:
            if device.name == device_name:
                return device.managementIp

        return None
