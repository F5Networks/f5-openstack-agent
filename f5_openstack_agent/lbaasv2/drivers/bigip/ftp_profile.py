# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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


class FTPProfileHelper(object):
    """A tool class for all FTP profile process"""

    def __init__(self):
        self.ftp_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.ftp_profile
        )

    @staticmethod
    def enable_ftp(service):
        listener = service.get('listener')
        if listener and listener.get('protocol') == 'FTP':
            return True
        return False

    def add_profile(self, service, vip, bigip):
        control_port = service.get('listener').get('protocol_port')
        partition = vip['partition']

        profile_name = self.get_profile_name(service)
        data_port = self.get_data_port(control_port)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.ftp_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )

        if not profile_exists:
            payload = dict(
                name=profile_name,
                partition=partition,
                port=data_port
            )
            LOG.info(
                "Add customized FTP profile: {} for "
                "BIGIP: {} ".format(
                    profile, bigip.hostname
                )
            )
            self.ftp_helper.create(bigip, payload)

        vip['profiles'] = [profile]

    def remove_profile(self, service, vip, bigip):
        # this function should be called after its
        # corresponding listener deleted

        partition = vip['partition']
        profile_name = FTPProfileHelper.get_profile_name(
            service)
        profile = "/" + partition + "/" + profile_name

        LOG.info(
            "Remove customized FTP profile: {} from "
            "BIGIP: {}".format(
                profile, bigip.hostname
            )
        )
        self.ftp_helper.delete(
            bigip,
            name=profile_name,
            partition=partition
        )

    @staticmethod
    def get_profile_name(service):
        listener_id = service.get('listener').get('id')
        prefix = "ftp_profile_"
        profile_name = prefix + listener_id
        return profile_name

    @staticmethod
    def get_data_port(control_port):
        data_port = control_port - 1
        return data_port
