# coding=utf-8
# Copyright (c) 2016-2023, F5 Networks, Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class SIPProfileHelper(object):
    """A tool class for SIP profile process"""

    def __init__(self):
        self.sip_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.sip_profile
        )

    @staticmethod
    def enable_sip(service):
        listener = service.get('listener')
        if listener and listener.get('protocol') == 'SIP':
            return True
        return False

    def add_profile(self, service, vip, bigip):
        partition = vip['partition']

        profile_name = self.get_profile_name(vip)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.sip_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )

        destination = vip.get("destination", "")

        if '%' in destination:
            address = destination.split('%')[0]
            if ':' in destination:
                port = destination.split(':')[-1]
                destination = address + ":" + port

        userViaHeader = "SIP/2.0/UDP " + destination
        LOG.debug("userViaHeader is %s", userViaHeader)

        if not profile_exists:
            payload = dict(
                name=profile_name,
                partition=partition,
                insertViaHeader="enabled",
                userViaHeader=userViaHeader

            )
            LOG.debug(
                "Add new SIP profile: {} for "
                "BIGIP: {} ".format(
                    profile, bigip.hostname
                )
            )
            self.sip_helper.create(bigip, payload)

        vip['profiles'].append(profile)

    def remove_profile(self, service, vip, bigip):
        partition = vip['partition']
        profile_name = SIPProfileHelper.get_profile_name(
            vip)
        profile = "/" + partition + "/" + profile_name

        LOG.debug(
            "Remove SIP profile: {} from "
            "BIGIP: {}".format(
                profile, bigip.hostname
            )
        )
        self.sip_helper.delete(
            bigip,
            name=profile_name,
            partition=partition
        )

    @staticmethod
    def get_profile_name(vip):
        vip_name = vip.get('name', 'vip_name')
        prefix = "sip_"
        profile_name = prefix + vip_name
        return profile_name
