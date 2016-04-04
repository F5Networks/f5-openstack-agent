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

from f5.bigip import BigIP
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class VcmpManager(object):
    def __init__(self, driver):
        self.driver = driver
        self.__vcmp_hosts = []
        self._init_vcmp_hosts()

    def get_vcmp_guest(self, vcmp_host, bigip):
        # Get vCMP Guest associated with bigip (if any)
        for vcmp_guest in vcmp_host['guests']:
            if vcmp_guest['mgmt_addr'] == bigip.icontrol.hostname:
                return vcmp_guest
        return None

    def get_vcmp_host(self, bigip):
        # Get vCMP Host associated with bigip (if any)
        for vcmp_host in self.__vcmp_hosts:
            for vcmp_guest in vcmp_host['guests']:
                if vcmp_guest['mgmt_addr'] == bigip.icontrol.hostname:
                    return vcmp_host
        return None

    def _init_vcmp_hosts(self):
        # Initialize vCMP Hosts.
        # Includes establishing a bigip connection
        # to the vCMP host and determining associated vCMP Guests.
        if not self.driver.conf.icontrol_vcmp_hostname:
            # No vCMP Hosts. Check if any vCMP Guests exist.
            # Flag issue in log.
            self.check_vcmp_host_assignments()
            return

        vcmp_hostnames = self.driver.conf.icontrol_vcmp_hostname.split(',')
        for vcmp_hostname in vcmp_hostnames:
            # vCMP Host Attributes
            vcmp_host = {}
            vcmp_host['bigip'] = BigIP(
                vcmp_hostname,
                self.driver.conf.icontrol_username,
                self.driver.conf.icontrol_password)
            vcmp_host['guests'] = []

            # vCMP Guest Attributes
            guest_names = vcmp_host['bigip'].system.sys_vcmp.get_list()
            guest_mgmts = vcmp_host['bigip'].\
                system.sys_vcmp.get_management_address(guest_names)

            for guest_name, guest_mgmt in zip(guest_names, guest_mgmts):
                # Only add vCMP Guests with BIG-IP® that has been registered
                if guest_mgmt.address in self.driver.get_bigip_hosts():
                    vcmp_guest = {}
                    vcmp_guest['name'] = guest_name
                    vcmp_guest['mgmt_addr'] = guest_mgmt.address
                    vcmp_host['guests'].append(vcmp_guest)

            self.__vcmp_hosts.append(vcmp_host)

        self.check_vcmp_host_assignments()

        # Output vCMP Hosts/Guests in log
        for vcmp_host in self.__vcmp_hosts:
            for vcmp_guest in vcmp_host['guests']:
                LOG.debug(('vCMPHost[%s] vCMPGuest[%s] - mgmt: %s' %
                          (vcmp_host['bigip'].icontrol.hostname,
                           vcmp_guest['name'], vcmp_guest['mgmt_addr'])))

    def check_vcmp_host_assignments(self):
        # Check that all vCMP Guest bigips have a host assignment
        LOG.debug(('Check registered bigips to ensure vCMP Guests '
                   'have a vCMP host assignment'))

        for bigip in self.driver.get_all_bigips():
            system_info = bigip.system.sys_info.get_system_information()
            if system_info.platform == 'Z101':
                if self.get_vcmp_host(bigip):
                    LOG.debug(('vCMP host found for vCMP Guest %s' %
                               bigip.icontrol.hostname))
                else:
                    LOG.error(('vCMP host not found for vCMP Guest %s' %
                               bigip.icontrol.hostname))
            else:
                LOG.debug(('BIG-IP %s is not a vCMP Guest' %
                           bigip.icontrol.hostname))

    def get_vlan_use_count(self, vcmp_host, vlan_name):
        # Determine the number of vCMP guests with access to vCMP host VLAN
        use_count = 0
        for vcmp_guest in vcmp_host['guests']:
            vlan_list = vcmp_host['bigip'].system.sys_vcmp.get_vlan(
                [vcmp_guest['name']])
            full_path_vlan_name = '/Common/' + vlan_name
            if full_path_vlan_name in vlan_list[0]:
                LOG.debug(('VLAN %s associated with guest %s' %
                          (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
                use_count += 1
            else:
                LOG.debug(('VLAN %s is not associated with guest %s' %
                          (full_path_vlan_name, vcmp_guest['mgmt_addr'])))
        return use_count
