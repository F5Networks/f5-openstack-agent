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

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions import \
    BigIPNotLicensedForVcmp
from f5_openstack_agent.lbaasv2.drivers.bigip import utils
from icontrol.exceptions import iControlUnexpectedHTTPError
from oslo_log import log
import time

LOG = log.getLogger(__name__)


class VcmpManager(object):
    def __init__(self, driver):
        '''Initialize the VcmpManager with vCMP hosts and guests.

        :param driver: iControlDriver object -- driver
        '''

        self.driver = driver
        self.vcmp_hosts = []
        if not self.driver.conf.icontrol_vcmp_hostname:
            self._check_vcmp_host_assignments()
            return
        self._init_vcmp_hosts()

    def get_vcmp_guest(self, vcmp_host, bigip):
        '''Find the appropriate guest object for a given bigip.

        :param vcmp_host: dict -- dict of vCMP host and guests
        :param bigip: ManagementRoot object -- bigip object to find in guests
        :returns: ManagementRoot object or None
        '''

        for vcmp_guest in vcmp_host['guests']:
            if utils.strip_cidr_netmask(
                    vcmp_guest.managementIp) == bigip.hostname:
                vcmp_guest.refresh()
                return vcmp_guest
        return None

    def get_vcmp_host(self, bigip):
        '''Find host for a particular bigip

        :param bigip: ManagementRoot object -- bigip to find in guests
        :returns: dict or None
        '''

        for vcmp_host in self.vcmp_hosts:
            for vcmp_guest in vcmp_host['guests']:
                if utils.strip_cidr_netmask(
                        vcmp_guest.managementIp) == bigip.hostname:
                    vcmp_host['bigip'].tm.refresh()
                    return vcmp_host
        return None

    def _init_vcmp_hosts(self):
        '''Initialize the data structures for vCMP Hosts and their Guests.'''

        vcmp_hostnames = self.driver.conf.icontrol_vcmp_hostname.split(',')

        for vcmp_hostname in vcmp_hostnames:
            vcmp_host = {}
            vcmp_host['bigip'] = ManagementRoot(
                vcmp_hostname,
                self.driver.conf.icontrol_username,
                self.driver.conf.icontrol_password)
            vcmp_host['guests'] = []

            try:
                guests = list(
                    vcmp_host['bigip'].tm.vcmp.guests.get_collection())
            except iControlUnexpectedHTTPError as ex:
                if ex.response.status_code == 400 and \
                        'One of the following features must be licensed/' \
                        'provisioned for the URI vcmp : vcmp' in ex.message:
                    msg = 'VcmpManager::_init_vcmp_hosts: Given vCMP host {0} ' \
                        'is not licensed for vCMP. Device returned exception: ' \
                        '{1}'.format(vcmp_hostname, ex)
                    raise BigIPNotLicensedForVcmp(msg)
                else:
                    raise(ex)
            except Exception as ex:
                raise(ex)

            for guest in guests:
                if utils.strip_cidr_netmask(
                        guest.managementIp) in self.driver.get_bigip_hosts():
                    vcmp_host['guests'].append(guest)

            self.vcmp_hosts.append(vcmp_host)

        self._check_vcmp_host_assignments()

        for vcmp_host in self.vcmp_hosts:
            for vcmp_guest in vcmp_host['guests']:
                LOG.debug(('VcmpManager::_init_vcmp_hosts: vCMPHost[%s] '
                           'vCMPGuest[%s] - mgmt: %s' % (
                               vcmp_host['bigip'].hostname, vcmp_guest.name,
                               utils.strip_cidr_netmask(
                                   vcmp_guest.managementIp))))

    def _check_vcmp_host_assignments(self):
        '''Check that all vCMP Guest bigips have a host assignment.'''

        log_prefix = 'VcmpManager::_check_vcmp_host_assignments'
        LOG.debug(('{} Check registered bigips to ensure vCMP Guests '
                   'have a vCMP host assignment'.format(log_prefix)))

        for bigip in self.driver.get_all_bigips():
            system_info = utils.get_device_info(bigip)
            if system_info.platformId == 'Z101':
                if self.get_vcmp_host(bigip):
                    LOG.debug(('{0} vCMP host found for Guest {1}'.format(
                        log_prefix, bigip.hostname)))
                else:
                    LOG.error(('{0} vCMP host not found for Guest {1}'.format(
                        log_prefix, bigip.hostname)))
            else:
                LOG.debug(('{0} BIG-IP {1} is not a vCMP Guest'.format(
                    log_prefix, bigip.hostname)))

    def _get_vlan_use_count(self, vcmp_host, vlan_name):
        '''Check vCMP guests with access to vCMP host VLAN.

        :param vcmp_host: dict -- dict of host connection and guests
        :param vlan_name: str -- name of vlan
        :returns: int -- number of guests with this VLAN
        '''

        use_count = 0
        for guest in vcmp_host['guests']:
            is_assoc = self._check_guest_vlans(guest, '/Common/' + vlan_name)
            if is_assoc:
                use_count += 1
        return use_count

    def _check_guest_vlans(self, guest, full_path_vlan_name):
        '''Check if a guest has a vlan associated with it.

        :param guest: MangementRoot object -- guest device
        :param full_path_vlan_name: str -- full path name of vlan
        :returns: bool -- True is guest has VLAN, False otherwise
        '''

        if hasattr(guest, 'vlans') and full_path_vlan_name in guest.vlans:
            LOG.debug(('VcmpManager::_check_guest_vlans: VLAN {0} is '
                       'associated with guest {1}'.format(
                           full_path_vlan_name, guest.hostname)))
            return True
        LOG.debug(('VcmpManager::_check_guest_vlans: VLAN {0} is '
                   'not associated with guest {1}'.format(
                       full_path_vlan_name, guest.hostname)))
        return False

    def _is_vlan_assoc_with_vcmp_guest(self, bigip, vlan):
        '''Check if VLAN is associated with guest

        :param bigip: ManagementRoot object -- guest object to check
        :param vlan: dict -- dict of vlan
        :returns: bool -- True if guest has VLAN, False otherwise
        '''

        try:
            vcmp_host = self.get_vcmp_host(bigip)
            vcmp_guest = self.get_vcmp_guest(vcmp_host, bigip)
            return self._check_guest_vlans(
                vcmp_guest, '/Common/' + vlan['name'])
        except Exception as exc:
            LOG.error(('VcmpManager::is_vlan_assoc_with_vcmp_guest: '
                       'Exception checking association of VLAN %s to vCMP '
                       'Guest %s: %s ' % (vlan['name'], bigip.hostname, exc)))
        return False

    def assoc_vlan_with_vcmp_guest(self, bigip, vlan):
        '''Set VLAN on vCMP Host for a particular Guest.

        :param vcmp_host: dict -- dict of vCMP Host object and guests
        :param bigip: ManagementRoot object -- vCMP Guest object
        :param vlan: dict -- VLAN dict
        '''

        log_prefix = 'VcmpManager::assoc_vlan_with_vcmp_guest:'
        if self._is_vlan_assoc_with_vcmp_guest(bigip, vlan):
            return

        vcmp_host = self.get_vcmp_host(bigip)
        vcmp_guest = self.get_vcmp_guest(vcmp_host, bigip)
        if not hasattr(vcmp_guest, 'vlans'):
            guest_vlans = []
        else:
            guest_vlans = vcmp_guest.vlans
        try:
            guest_vlans.append(vlan['name'])
            vcmp_guest.modify(vlans=guest_vlans)
            LOG.debug(('{0} Associated VLAN {1} with vCMP Guest {2}'.format(
                       log_prefix, vlan['name'], vcmp_guest.hostname)))
        except Exception as exc:
            LOG.error(('{0} Exception associating VLAN {1} to vCMP Guest {2}: '
                       '{3}'.format(
                           log_prefix, vlan['name'],
                           vcmp_guest.hostname, exc)))
        # Wait for the VLAN to propagate to /Common on vCMP Guest
        full_path_vlan_name = '/Common/' + vlan['name']
        vlan_created = False
        vf = bigip.tm.net.vlans.vlan
        try:
            for _ in range(0, 30):
                time.sleep(1)
                if vf.exists(name=vlan['name'], partition='Common'):
                    v = vf.load(name=vlan['name'], partition='Common')
                    vlan_created = True
                    break
                LOG.debug(('{0} Wait for VLAN {1} to be created on vCMP '
                           'Guest {2}.'.format(
                               log_prefix, full_path_vlan_name,
                               vcmp_guest.hostname)))

            if vlan_created:
                LOG.debug(('{0} VLAN {1} exists on vCMP Guest {2}.'.format(
                    log_prefix, full_path_vlan_name, vcmp_guest.hostname)))
            else:
                LOG.error(('{0} VLAN {1} does not exist on vCMP Guest '
                           '{2}.'.format(
                               log_prefix, full_path_vlan_name,
                               vcmp_guest.hostname)))
        except Exception as exc:
            LOG.error(('{0} Exception waiting for vCMP Host VLAN {1} to '
                       'be created on vCMP Guest {2}: {3}'.format(
                           log_prefix, vlan['name'],
                           vcmp_guest.hostname, exc)))

        # Delete the VLAN from the /Common folder on the vCMP Guest
        if vlan_created:
            try:
                v.delete()
                LOG.debug(('{0} Deleted VLAN {1} from vCMP Guest {2}'.format(
                    log_prefix, full_path_vlan_name, vcmp_guest.hostname)))
            except Exception as exc:
                LOG.error(
                    ('{0} Exception deleting VLAN {1} from vCMP Guest '
                     '{2}: {3}'.format(
                         log_prefix, full_path_vlan_name,
                         vcmp_guest.hostname, exc)))

    def disassoc_vlan_with_vcmp_guest(self, bigip, vlan_name):
        '''Remove VLAN association from vCMP guest.

        :param vcmp_host: dict -- dict of vcmp_host connection and guests
        :param bigip: ManagementRoot object -- bigip guest
        :param vlan_name: str -- name of vlan
        '''

        log_prefix = 'VcmpManager::disassoc_vlan_with_vcmp_guest'
        vcmp_host = self.get_vcmp_host(bigip)
        vcmp_guest = self.get_vcmp_guest(vcmp_host, bigip)
        try:
            vcmp_guest.modify(
                vlans=vcmp_guest.vlans.remove('/Common/' + vlan_name))
            LOG.debug(('{0} Removed VLAN {1} association from vCMP '
                       'Guest {2}'.format(
                           log_prefix, vlan_name, vcmp_guest.hostname)))
        except Exception as exc:
            LOG.error(('{0} Exception removing VLAN {1} association from vCMP '
                       'Guest {2}: {3}'.format(
                           log_prefix, vlan_name, vcmp_guest.hostname, exc)))

        # Only delete VLAN if it is not in use by other vCMP Guests
        if self._get_vlan_use_count(vcmp_host, vlan_name):
            LOG.debug(('{0} VLAN {1} in use by other vCMP Guests on vCMP '
                       'Host {2}'.format(
                           log_prefix, vlan_name,
                           vcmp_host['bigip'].hostname)))
        else:
            try:
                vlan = vcmp_host['bigip'].tm.net.vlans.vlan.load(
                    name=vlan_name, partition='Common')
                vlan.delete()
                LOG.debug(('{0} Deleted VLAN {1} from vCMP Host {2}'.format(
                    log_prefix, vlan_name, vcmp_host['bigip'].hostname)))
            except Exception as exc:
                LOG.error(('{0} Exception deleting VLAN {1} from vCMP Host '
                           '{2}:{3}'.format(
                               log_prefix, vlan_name,
                               vcmp_host['bigip'].icontrol.hostname, exc)))
