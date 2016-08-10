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
from requests.exceptions import HTTPError

import time

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as const

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
            c = bigip.tm.sys.config
            c.save()
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

    def sync(self, bigip, name, force_now=False):
        state = ''
        sync_start_time = time.time()
        dev_name = self.get_device_name(bigip)
        sleep_delay = const.SYNC_DELAY

        attempts = 0
        if force_now:
            bigip.tm.cm.sync(name)
            time.sleep(sleep_delay)
            attempts += 1

        while attempts < const.MAX_SYNC_ATTEMPTS:
            state = self.get_sync_status(bigip)
            if state in ['Standalone', 'In Sync']:
                break

            elif state == 'Awaiting Initial Sync':
                attempts += 1
                LOG.info(
                    'Cluster',
                    "Device %s - Synchronizing initial config to group %s"
                    % (dev_name, name))
                bigip.tm.cm.sync(name)
                time.sleep(sleep_delay)

            elif state in ['Disconnected',
                           'Not All Devices Synced',
                           'Changes Pending']:
                attempts += 1

                last_log_time = 0
                now = time.time()
                wait_start_time = now
                # Keep checking the sync state in a quick loop.
                # We want to detect In Sync as quickly as possible.
                while now - wait_start_time < sleep_delay:
                    # Only log once per second
                    if now - last_log_time >= 1:
                        LOG.info(
                            'Cluster',
                            'Device %s, Group %s not synced. '
                            % (dev_name, name) +
                            'Waiting. State is: %s'
                            % state)
                        last_log_time = now
                    state = self.get_sync_status(bigip)
                    if state in ['Standalone', 'In Sync']:
                        break
                    time.sleep(.5)
                    now = time.time()
                else:
                    # if we didn't break out due to the group being in sync
                    # then attempt to force a sync.
                    bigip.tm.cm.sync(name)
                    sleep_delay += const.SYNC_DELAY
                    # no need to sleep here because we already spent the sleep
                    # interval checking status.
                    continue

                # Only a break from the inner while loop due to Standalone or
                # In Sync will reach here.
                # Normal exit of the while loop reach the else statement
                # above which continues the outer loop
                break

            elif state == 'Sync Failure':
                LOG.info('Cluster',
                         "Device %s - Synchronization failed for %s"
                         % (dev_name, name))
                LOG.debug('Cluster', 'SYNC SECONDS (Sync Failure): ' +
                          str(time.time() - sync_start_time))
                raise BigIPClusterSyncFailure(
                    'Device service group %s' % name +
                    ' failed after ' +
                    '%s attempts.' % const.MAX_SYNC_ATTEMPTS +
                    ' Correct sync problem manually' +
                    ' according to sol13946 on ' +
                    ' support.f5.com.')
            else:
                attempts += 1
                LOG.info('Cluster',
                         "Device %s " % dev_name +
                         "Synchronizing config attempt %s to group %s:"
                         % (attempts, name) + " current state: %s" % state)
                bigip.tm.cm.sync(name)
                time.sleep(sleep_delay)
                sleep_delay += const.SYNC_DELAY
        else:
            if state == 'Disconnected':
                LOG.debug('Cluster',
                          'SYNC SECONDS(Disconnected): ' +
                          str(time.time() - sync_start_time))
                raise BigIPClusterSyncFailure(
                    'Device service group %s' % name +
                    ' could not reach a sync state' +
                    ' because they can not communicate' +
                    ' over the sync network. Please' +
                    ' check connectivity.')
            else:
                LOG.debug('Cluster', 'SYNC SECONDS(Timeout): ' +
                          str(time.time() - sync_start_time))
                raise BigIPClusterSyncFailure(
                    'Device service group %s' % name +
                    ' could not reach a sync state after ' +
                    '%s attempts.' % const.MAX_SYNC_ATTEMPTS +
                    ' It is in %s state currently.' % state +
                    ' Correct sync problem manually' +
                    ' according to sol13946 on ' +
                    ' support.f5.com.')

        LOG.debug('Cluster', 'SYNC SECONDS(Success): ' +
                  str(time.time() - sync_start_time))
