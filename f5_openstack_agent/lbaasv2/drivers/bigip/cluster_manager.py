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

from oslo_log import log as logging
from requests.exceptions import HTTPError

from f5.multi_device.device_group import DeviceGroup

LOG = logging.getLogger(__name__)


class BigIPClusterSyncFailure(Exception):
    pass


class ClusterManager(object):
    """Set of functions to help manage BIG-IP clusters."""

    def devices(self, bigip):
        return bigip.tm.cm.devices.get_collection()

    def disable_auto_sync(self, device_group_name, bigip, partition='Common'):
        dg = bigip.tm.cm.device_groups.device_group.load(
            name=device_group_name, partition=partition)
        dg.modify(autoSync='disabled')

    def enable_auto_sync(self, device_group_name, bigip, partition='Common'):
        dg = bigip.tm.cm.device_groups.device_group.load(
            name=device_group_name, partition=partition)
        dg.modify(autoSync='enabled')

    def get_sync_status(self, bigip):
        sync_status = bigip.tm.cm.sync_status
        sync_status.refresh()

        status = sync_status.entries[
            'https://localhost/mgmt/tm/cm/sync-status/0']
        return status['nestedStats']['entries']['status']['description']

    def get_traffic_groups(self, bigip):
        traffic_groups = []
        groups = bigip.tm.cm.traffic_groups.get_collection()
        for group in groups:
            traffic_groups.append(group.name)

        return traffic_groups

    def save_config(self, bigip):
        try:
            # invalid for the version of f5-sdk in requirements
            # c = bigip.tm.sys.config
            # c.save()
            bigip.tm.util.bash.exec_cmd(
                command='run',
                utilCmdArgs="-c 'tmsh save sys config'"
            )
        except HTTPError as err:
            LOG.error("Error saving config."
                      "Repsponse status code: %s. Response "
                      "message: %s." % (err.response.status_code,
                                        err.message))

    def get_device_group(self, bigip):
        dgs = bigip.tm.cm.device_groups.get_collection()
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

    def is_device_active(self, bigip):
        active = False
        try:
            device_name = self.get_device_name(bigip)
            act = bigip.tm.cm.devices.device.load(
                name=device_name, partition='Common')
            active = act.failoverState.lower() == 'active'
        except Exception as exc:
            LOG.error("Unable to get device info. %s", exc.message)

        return active

    def sync(self, bigips, name=None, partition=None):
        if not bigips and not isinstance(bigips, list):
            return False
        if not partition:
            partition = 'Common'
        device_group_type = None
        for bigip in bigips:
            validated_db_present = False
            dgs = bigip.tm.cm.device_groups.get_collection(partition=partition)
            for dg in dgs:
                if not name and dg.type == 'sync-failover':
                    name = dg.name
                if dg.name == name:
                    validated_db_present = True
                    device_group_type = dg.type
            if not validated_db_present:
                return False
        # This will attempt to sync and wait for sync state to be valid
        dg = DeviceGroup(devices=bigips,
                         device_group_name=name,
                         device_group_type=device_group_type,
                         device_group_partition=partition)
