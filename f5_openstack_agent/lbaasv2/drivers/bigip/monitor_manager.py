"""Monitor manager to handle periodic tasks."""
# coding=utf-8
# Copyright (c) 2023, F5 Networks, Inc.
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

import datetime
import re
import sys

from f5.bigip import ManagementRoot
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
import oslo_messaging
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_utils import importutils

try:
    from neutron_lib import context as ncontext
except ImportError:
    from neutron import context as ncontext

from f5_openstack_agent.client.encrypt import decrypt_data
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import opts
from f5_openstack_agent.lbaasv2.drivers.bigip import plugin_rpc
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper

from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import \
    SystemHelper

from requests import HTTPError


LOG = logging.getLogger(__name__)

opts.register_f5_opts()


class LbaasMonitorManager(periodic_task.PeriodicTasks):
    """Periodic monitor task."""

    RPC_API_VERSION = '1.0'

    target = oslo_messaging.Target(version='1.0')

    def __init__(self, conf):
        """Initialize LbaasMonitorManager."""
        super(LbaasMonitorManager, self).__init__(conf)
        LOG.debug("Initializing LbaasMonitorManager")
        LOG.debug("runtime environment: %s" % sys.version)

        self.conf = conf
        self.context = ncontext.get_admin_context_without_session()

        self.last_member_update = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.needs_member_update = True
        self.member_update_base = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.member_update_mode = self.conf.member_update_mode
        self.member_update_number = self.conf.member_update_number
        self.member_update_interval = self.conf.member_update_interval
        self.member_update_agent_number = self.conf.member_update_agent_number
        self.member_update_agent_order = self.conf.member_update_agent_order
        self.plugin_rpc = None
        self.system_helper = None

        # Load the driver.
        self._load_driver(conf)

        # Set the agent ID
        if self.conf.agent_id:
            self.agent_host = self.conf.agent_id
            LOG.debug('setting agent host to %s' % self.agent_host)
        else:
            self.agent_host = conf.host
            LOG.debug('setting agent host to %s' % self.agent_host)

        # Setup RPC for communications to and from controller
        self._setup_rpc()

        # Allow the driver to make callbacks to the LBaaS driver plugin
        self.lbdriver.set_plugin_rpc(self.plugin_rpc)

        self.system_helper = SystemHelper()

        member_update_interval = self.conf.member_update_interval
        if member_update_interval > 0:
            LOG.debug('Starting the member status update task.')
            member_update_task = loopingcall.FixedIntervalLoopingCall(
                self.update_member_status_task)
            member_update_task.start(interval=member_update_interval)
        else:
            LOG.debug('The member update interval %d is negative.' %
                      member_update_interval)

        device_report_interval = self.conf.device_report_interval
        if device_report_interval > 0:
            LOG.debug('Starting the device status report task.')
            device_report_task = loopingcall.FixedIntervalLoopingCall(
                self.report_device_status_task)
            device_report_task.start(interval=device_report_interval)
        else:
            LOG.debug('The device report interval %d is negative.' %
                      device_report_interval)

    def _load_driver(self, conf):
        self.lbdriver = None

        LOG.debug('loading LBaaS driver %s' %
                  conf.f5_bigip_lbaas_device_driver)
        try:
            self.lbdriver = importutils.import_object(
                conf.f5_bigip_lbaas_device_driver,
                self.conf)
            return
        except ImportError as ie:
            msg = ('Error importing loadbalancer device driver: %s error %s'
                   % (conf.f5_bigip_lbaas_device_driver, repr(ie)))
            LOG.error(msg)
            raise SystemExit(msg)

    def _setup_rpc(self):
        # Setting up outbound (callbacks) communications from monitor
        # setup the topic to send oslo messages RPC calls
        # from this monitor to the controller
        topic = constants_v2.TOPIC_PROCESS_ON_HOST_V2
        if self.conf.environment_specific_plugin:
            topic = topic + '_' + self.conf.environment_prefix
            LOG.debug('monitor in %s environment will send callbacks to %s'
                      % (self.conf.environment_prefix, topic))

        # create our class we will use to send callbacks to the controller
        # for processing by the driver plugin
        self.plugin_rpc = plugin_rpc.LBaaSv2PluginRPC(
            topic,
            self.context,
            self.conf,
            self.agent_host
        )

    @staticmethod
    def calculate_member_status(member):
        member_status = None
        session = None
        status = None
        if 'state' in member:
            status = member['state']
        if 'session' in member:
            session = member['session']

        if status == 'unchecked':
            member_status = constants_v2.F5_NO_MONITOR
        elif status == 'down':
            if session == 'user-disabled':
                member_status = constants_v2.F5_DISABLED
            else:
                member_status = constants_v2.F5_OFFLINE
        elif status == 'up':
            if session == 'user-disabled':
                member_status = constants_v2.F5_DISABLED
            else:
                member_status = constants_v2.F5_ONLINE
        elif status == 'checking':
            if session == 'monitor-enabled':
                member_status = constants_v2.F5_CHECKING
        else:
            LOG.warning("Unexpected status %s and session %s",
                        status, session)
        return member_status

    def append_one_member(self, member, pool_id, all_members):
        """append one member """
        if not member:
            LOG.debug("member is empty.")
            return

        if 'name' in member:
            name = member['name']
            if not name:
                LOG.debug("member's name is empty.")
                return

            match_obj = re.match(r'(.*)[:|.][1-9]\d*', name, re.M | re.I)
            if match_obj:
                address = match_obj.group(1)
                if "%" in address:
                    address = address.split("%")[0]
            else:
                LOG.debug("name %s format is wrong.", name)
                return

            port = name[len(address):]

            if ":" in port:
                port = port.split(":")[1]
            elif "." in port:
                port = port.split(".")[1]
            else:
                LOG.debug("port format is invalid.")
                return

            member_info = {}
            member_info['pool_id'] = pool_id
            member_info['address'] = address
            member_info['protocol_port'] = int(port)
            member_info['state'] = \
                self.calculate_member_status(member)
            if member_info['state'] is not None and \
               member_info['state'] != constants_v2.F5_CHECKING:
                all_members.append(member_info)
        else:
            LOG.debug("member name doesn't exist.")
        return

    def append_members_one_pool(self, bigip, pool, all_members):
        """update the members' status in one pool """
        if not bigip:
            LOG.debug("bigip is empty.")
            return

        try:
            tenant_id = pool['tenant_id']
            pool_id = pool['id']
            pool_name = self.conf.environment_prefix + '_' + pool_id
            partition = self.conf.environment_prefix + '_' + tenant_id
            pool = resource_helper.BigIPResourceHelper(
                resource_helper.ResourceType.pool).load(
                   bigip, name=pool_name, partition=partition)
            members = pool.members_s.get_collection()
            # figure out the members in this pool and send
            # the members and their statuses to driver in batch
            LOG.debug("The member length is %d for pool %s.",
                      len(members), pool_name)
            for member in members:
                self.append_one_member(member.__dict__, pool_id,
                                       all_members)
        except HTTPError as err:
            if err.response.status_code == 404:
                LOG.debug('pool %s not on BIG-IP %s.'
                          % (pool_id, bigip.hostname))
        except Exception as exc:
            LOG.exception('Exception get members %s' % str(exc))

        return

    @log_helpers.log_method_call
    def update_all_member_status_by_folders(self, bigip, folders):
        """update the members in all pools """
        if not bigip:
            LOG.debug("bigip is empty.")
            return
        prefix_name = self.conf.environment_prefix
        batch_number = self.conf.member_update_number
        prefix_len = len(prefix_name)
        all_members = []
        member_number = 0
        folder_number = len(folders)
        for folder in folders:
            LOG.debug("The folder is %s." % folder)
            # tenant_id = folder[len(self.conf.environment_prefix):]
            try:
                if not str(folder).startswith(prefix_name):
                    LOG.debug("folder %s doesn't start with prefix.",
                              str(folder))
                    continue

                resource = resource_helper.BigIPResourceHelper(
                    resource_helper.ResourceType.pool)
                deployed_pools = resource.get_resources(bigip, folder, True)
                if deployed_pools:
                    LOG.debug("get %d pool(s) for %s.",
                              len(deployed_pools), str(folder))
                    for pool in deployed_pools:
                        # retrieve and append members in pool
                        reference = pool.membersReference
                        if 'items' not in reference:
                            LOG.debug("no items attribute for pool %s",
                                      pool.name)
                            continue

                        if not str(pool.name).startswith(prefix_name):
                            LOG.debug("folder %s doesn't start with prefix.",
                                      str(pool.name))
                            continue

                        members = reference['items']
                        pool_id = pool.name[prefix_len + 1:]
                        LOG.debug("Get %d members.", len(members))
                        for member in members:
                            self.append_one_member(
                                member,
                                pool_id,
                                all_members
                            )

                # check after one folder
                if batch_number > 0 and len(all_members) >= batch_number:
                    member_number += len(all_members)
                    LOG.debug("update member status in batch %d",
                              len(all_members))
                    self.plugin_rpc.update_member_status_in_batch(
                        all_members)
                    all_members[:] = []

            except Exception as e:
                all_members[:] = []
                LOG.error("Unable to update member state: %s" % e.message)

        if len(all_members) > 0:
            member_number += len(all_members)
            LOG.debug("last round update member status in batch %d",
                      len(all_members))
            self.plugin_rpc.update_member_status_in_batch(
                     all_members)
            all_members[:] = []

        LOG.debug("Totally update %u folders %u members",
                  folder_number, member_number)

        return

    @log_helpers.log_method_call
    def update_all_member_status_by_pools(self, bigip, pools):
        """update the members in all pools """
        if not bigip:
            LOG.debug("bigip is empty.")
            return

        batch_number = self.conf.member_update_number
        all_members = []
        pool_number = len(pools)
        member_number = 0

        for pool_id in pools:
            pool = pools.get(pool_id, None)
            if not pool:
                LOG.debug("couldn't find pool %s.", pool_id)
                continue

            self.append_members_one_pool(bigip, pool, all_members)
            if batch_number > 0 and len(all_members) >= batch_number:
                member_number += len(all_members)
                LOG.debug("update member status in batch %d",
                          len(all_members))
                self.plugin_rpc.update_member_status_in_batch(
                    all_members)
                all_members[:] = []

        if len(all_members):
            member_number += len(all_members)
            LOG.debug("update member status in batch %d",
                      len(all_members))
            self.plugin_rpc.update_member_status_in_batch(
                all_members)
            all_members[:] = []

        LOG.debug("Totally update %u pools %u members",
                  pool_number, member_number)

        return

    def update_member_status_task(self):
        """Update pool member operational status from devices to controller."""
        if not self.needs_member_update:
            LOG.debug("The previous task is still running.")
            return

        if self.member_update_interval < 0:
            LOG.debug('The interval is negative %d' %
                      self.member_update_interval)
            return

        if self.member_update_agent_order < 0:
            LOG.debug('Not update. The order is negative %d' %
                      self.member_update_agent_order)
            return

        now = datetime.datetime.now()
        time_delta = (now - self.last_member_update).seconds
        if time_delta < self.member_update_interval:
            LOG.debug('The interval %d (%d) is not met yet.',
                      time_delta, self.member_update_interval)
            return

        time_delta = (now - self.member_update_base).seconds
        order = time_delta % (self.member_update_agent_number *
                              self.member_update_interval)
        order /= self.member_update_interval

        if (order != self.member_update_agent_order):
            LOG.debug("Not the order %u for this monitor %u to be runnning",
                      order, self.member_update_agent_order)
            return

        """ we only update the member status when:
         1) the order is the right.
         2) the time passed since last update is no less than interval.
        """

        LOG.debug("Begin updating member status at %s." % now)
        self.last_member_update = now
        self.needs_member_update = False

        """ the logic is, we retrieve all the members from bigip directly
        and update the neutron server in batch with the members' statuses.

        two modes for the update. One is per pool and the other is
        per folder. """

        try:
            bigips = []
            # TODO(nik) to test if result desired when zones unconfigured
            zones = []
            if self.conf.availability_zone:
                zones = self.conf.availability_zone.split(",")
            az_devices = self.plugin_rpc.get_devices(
                availability_zone=zones
            )
            LOG.debug("az_devices: %s" % az_devices)
            for each in az_devices:
                device_info = each.get("device_info")
                members = device_info['members']

                for m in members:
                    if m['operating_status']['failover_state'] == 'active':
                        username = decrypt_data(
                            m['device_info']['serial_number'],
                            m['device_info']['username']
                        )
                        password = decrypt_data(
                            m['device_info']['serial_number'],
                            m['device_info']['password']
                        )

                        # TODO(nik) add v6 later when the config item is added
                        bigips.append({
                            'hostname': m['mgmt_ipv4'],
                            'username': username,
                            'password': password,
                            'port': m['device_info']['port'],
                        })

            LOG.debug("get %s active bigips" % len(bigips))
            for info in bigips:
                # origianl info logged the credentails
                LOG.debug("bigip : %s" % info['hostname'])
                bigip = ManagementRoot(info['hostname'],
                                       info['username'],
                                       info['password'],
                                       port=info['port'],
                                       token=True)

                if self.conf.member_update_mode == 1:
                    # logic of update member by pools
                    pools = self.lbdriver.get_all_pools_for_one_bigip(bigip)
                    if pools:
                        LOG.debug("%d pool(s) found", len(pools))
                        self.update_all_member_status_by_pools(bigip, pools)
                    else:
                        LOG.debug("no vailable pools")
                elif self.conf.member_update_mode == 2:
                    # logic of update member by folders
                    folders = self.system_helper.get_folders(bigip)
                    if folders:
                        LOG.debug("%d folder(s) found", len(folders))
                        self.update_all_member_status_by_folders(
                            bigip, folders)
                    else:
                        LOG.debug("no vailable folders")
                else:
                    LOG.debug("member update mode %d isnt' supported.",
                              self.conf.member_update_mode)
        except Exception as e:
            self.needs_member_update = True
            LOG.error("Unable to update member state: %s" % e.message)

        self.needs_member_update = True
        now = datetime.datetime.now()
        LOG.debug("End updating member status at %s." % now)

        return

    def report_device_status_task(self):
        LOG.debug("starts report_device_status_task.")
        try:
            zones = []
            if self.conf.availability_zone:
                zones = self.conf.availability_zone.split(",")
            az_devices = self.plugin_rpc.get_devices(
                availability_zone=zones
            )
            LOG.debug("az_devices: %s ." % az_devices)

            for each in az_devices:
                id = each['id']
                LOG.debug(id)

                device_info = each.get('device_info')
                members = device_info['members']

                for m in members:
                    member_id = m['id']
                    LOG.debug(member_id)
                    LOG.debug("operating_status: %s" % m['operating_status'])

                    member = {
                        "member": {"operating_status": {}}
                    }

                    username = decrypt_data(m['device_info']['serial_number'],
                                            m['device_info']['username'])
                    password = decrypt_data(m['device_info']['serial_number'],
                                            m['device_info']['password'])

                    try:
                        timestamp = datetime.datetime.utcnow().strftime(
                            '%Y-%m-%dT%H:%M:%S') + 'Z'
                        hostname = m['mgmt_ipv4']
                        bigip = ManagementRoot(hostname,
                                               username,
                                               password,
                                               port=m['device_info']['port'],
                                               token=True)

                        failover_state = bigip.tm.sys.dbs.db.load(
                            name='failover.state'
                        )
                        member = {
                            "member": {
                                "operating_status": {
                                    "status": "ONLINE",
                                    "timestamp": timestamp,
                                    "failover_state": failover_state.value,
                                    "error": ""
                                }
                            }
                        }

                    except Exception as e:
                        LOG.error('seems bigip %s has problem' % hostname)
                        member['member']['operating_status']['error'] = \
                            str(e)[:80]
                        member['member']['operating_status']['status'] = \
                            'OFFLINE'
                        member['member']['operating_status'][
                            'failover_state'] = 'unknown'
                        member['member']['operating_status']['timestamp'] = \
                            timestamp
                    finally:
                        self.plugin_rpc.update_device_member(member_id, member)

        except Exception as e:
            LOG.error("seems unable to report state: %s" % e.message)
        LOG.debug("ends report_device_status_task.")
