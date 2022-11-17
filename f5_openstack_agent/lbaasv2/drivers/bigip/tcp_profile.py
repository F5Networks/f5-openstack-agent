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


class TCPProfileHelper(object):
    """A tool class for all tcp profile process"""

    def __init__(self):
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.tcp_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.tcp_profile
        )
        self.delete_profile = False
        self.allowed_protocols = ["TCP", "FTP", "HTTPS"]
        self.keepalive_allowed_protocols = \
            ["TCP", "HTTP", "HTTPS", "TERMINATED_HTTPS"]

    def enable_tcp(self, service):
        # pzhang: do not check ipProtocol TCP for further requirements,
        # which may require to change tcp profile in higher level protocol
        # such as FTP

        listener = service.get('listener')
        if listener is None:
            return False

        if listener.get('transparent'):
            protocol = listener.get('protocol')
            if protocol not in self.allowed_protocols:
                return False
            return True
        else:
            return False

    def need_delete_tcp(self, service):
        # pzhang: allow to delete any type listener with 'transparent'

        listener = service.get('listener')
        if listener is None:
            return False

        return listener.get('transparent')

    def need_update_tcp(self, old_listener, listener):
        # pzhang: in case of other resource update without listener dict.
        if old_listener is None or listener is None:
            return False

        if old_listener['transparent'] != listener['transparent']:
            protocol = listener.get('protocol')
            if protocol not in self.allowed_protocols:
                return False
            return True
        else:
            return False

    def add_profile(self, service, vip, bigip, **kwargs):
        side = kwargs.get("side")
        tcp_options = kwargs.get("tcp_options")

        if tcp_options:
            first_option = tcp_options
            tcp_options = "{%s first}" % first_option

        partition = vip['partition']
        profile_name = self.get_profile_name(service, side)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.tcp_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )

        if not profile_exists:
            payload = dict(
                name=profile_name,
                partition=partition,
                tcpOptions=tcp_options
            )
            LOG.info(
                "Add customized TCP profile: {} for "
                "BIGIP: {} ".format(
                    profile, bigip.hostname
                )
            )
            self.tcp_helper.create(bigip, payload)

        if side == "client":
            # pzhang: coustomerized clientside, serverside is /common/tcp
            client_profile_body = {
                "name": profile_name,
                "partition": partition,
                "context": "clientside"
            }
            server_profile_body = {
                "name": "tcp",
                "partition": "Common",
                "context": "serverside"
            }
        elif side == "server":
            # pzhang: coustomerized serverside, clientside is /common/tcp
            server_profile_body = {
                "name": profile_name,
                "partition": partition,
                "context": "serverside"
            }
            client_profile_body = {
                "name": "tcp",
                "partition": "Common",
                "context": "clientside"
            }
        else:
            # pzhang: coustomerized both serverside and clientside
            server_profile_body = {
                "name": profile_name,
                "partition": partition,
                "context": "serverside"
            }
            client_profile_body = {
                "name": profile_name,
                "partition": partition,
                "context": "clientside"
            }

        # pzhang tcp profile can not in fastL4 mode
        delete_fastL4s = vip['profiles'].count("/Common/fastL4")
        for _ in range(delete_fastL4s):
            vip['profiles'].remove("/Common/fastL4")

        # pzhang: be careful, if we connect multiple
        # bigips
        if server_profile_body not in vip['profiles']:
            vip['profiles'].append(server_profile_body)
        if client_profile_body not in vip['profiles']:
            vip['profiles'].append(client_profile_body)

        self.delete_profile = False

    def update_profile(self, service, vip, bigip, **kwargs):
        side = kwargs.get("side")
        tcp_options = kwargs.get("tcp_options")
        new_listener = service.get('listener')
        transparent = new_listener.get('transparent')

        if tcp_options:
            first_option = tcp_options
            tcp_options = "{%s first}" % first_option

        vs_name = vip['name']
        partition = vip['partition']
        profile_name = self.get_profile_name(service, side)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.tcp_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )

        if transparent:
            if not profile_exists:
                # pzhang: if not exist, we create tcp_options
                # be caution we change fastl4 to standard,
                # since original TCP is fastl4 mode
                payload = dict(
                    name=profile_name,
                    partition=partition,
                    tcpOptions=tcp_options
                )
                LOG.info(
                    "Updating to create a non-exist customized TCP profile: {}"
                    " for BIGIP: {} ".format(
                        profile, bigip.hostname
                    )
                )
                self.tcp_helper.create(bigip, payload)

            if side == "client":
                # pzhang: coustomerized clientside, serverside is /common/tcp
                client_profile_body = {
                    "name": profile_name,
                    "partition": partition,
                    "context": "clientside"
                }
                server_profile_body = {
                    "name": "tcp",
                    "partition": "Common",
                    "context": "serverside"
                }
            elif side == "server":
                # pzhang: coustomerized serverside, clientside is /common/tcp
                server_profile_body = {
                    "name": profile_name,
                    "partition": partition,
                    "context": "serverside"
                }
                client_profile_body = {
                    "name": "tcp",
                    "partition": "Common",
                    "context": "clientside"
                }
            else:
                # pzhang: coustomerized both serverside and clientside
                server_profile_body = {
                    "name": profile_name,
                    "partition": partition,
                    "context": "serverside"
                }
                client_profile_body = {
                    "name": profile_name,
                    "partition": partition,
                    "context": "clientside"
                }

            vs_all_profiles = self.get_vs_all_profiles(
                bigip, partition, vs_name)

            vip['profiles'] = self.replace_profiles(
                vs_all_profiles,
                client_profile_body,
                server_profile_body)

            self.delete_profile = False
        else:
            # pzhang: if exist, here just delete tcp_options profile.
            # do not consider to updating tcp_options number here,
            # if update tcp_options number, it should be donw by updating
            # to delete profile, then updating to create new profile
            # be caution here: we do not change standard mode back to fastl4

            all_profile_body = {
                "name": "tcp",
                "fullPath": "/Common/tcp",
                "partition": "Common",
                "context": "all"
            }

            vs_all_profiles = self.get_vs_all_profiles(
                bigip, partition, vs_name)

            vip['profiles'] = self.replace_profiles(
                vs_all_profiles,
                all_profile_body
            )

            profile_name = TCPProfileHelper.get_profile_name(
                service, side)
            profile = "/" + partition + "/" + profile_name
            LOG.info(
                "Updating to unbind a exist customized TCP profile: {} for "
                "BIGIP: {} ".format(
                    profile, bigip.hostname
                )
            )
            self.delete_profile = True

    def remove_profile(self, service, vip, bigip, **kwargs):
        # this function should be called after its
        # corresponding listener deleted, we do not need
        # to unbind profile first.

        side = kwargs.get("side")
        partition = vip['partition']

        profile_name = TCPProfileHelper.get_profile_name(
            service, side)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.tcp_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )
        if profile_exists:
            LOG.info(
                "Remove customized TCP profile: {} from "
                "BIGIP: {}".format(
                    profile, bigip.hostname
                )
            )

            self.tcp_helper.delete(
                bigip,
                name=profile_name,
                partition=partition
            )

    @staticmethod
    def get_profile_name(service, side):
        prefix = "tcp_profile_"
        if side:
            prefix = side + "_" + prefix
        listener_id = service.get('listener').get('id')
        profile_name = prefix + listener_id
        return profile_name

    def get_vs_all_profiles(self, bigip, partition, vs_name):
        # pzhang: it may cause races problem
        profile_objs = self.vs_helper.get_resources(
            bigip, partition, expand_subcollections=True
        )
        vs_obj = filter(lambda x: x.name == vs_name, profile_objs)[0]
        vs_profiles = vs_obj.profilesReference.get('items')

        if not vs_profiles:
            return list()
        return vs_profiles

    @staticmethod
    def replace_profiles(profiles_list, *args):
        # pzhang remove old tcp profiles and fastl4 profiles
        new_profiles = [
            p for p in profiles_list
            if "mgmt/tm/ltm/profile/tcp" not in p['nameReference']['link']
            and "mgmt/tm/ltm/profile/fastl4" not in p['nameReference']['link']
        ]
        for pf in args:
            new_profiles.append(pf)
        return new_profiles

    def enable_keepalive(self, service):
        listener = service.get('listener')
        if listener is None:
            return False

        if listener.get('keepalive_timeout') != -1:
            protocol = listener.get('protocol')
            if protocol not in self.keepalive_allowed_protocols:
                return False
            return True
        else:
            return False

    def need_update_keepalive(self, old_listener, listener):
        if old_listener is None or listener is None:
            return False
        protocol = listener.get('protocol')
        if protocol not in self.keepalive_allowed_protocols:
            return False

        old_t = old_listener['keepalive_timeout']
        new_t = listener['keepalive_timeout']
        LOG.debug("keepalive_timeout old_t is {}, new_t is {}"
                  .format(old_t, new_t))
        if old_t == -1 and new_t == -1:
            return False
        else:
            return True

    def get_keepalive_timeout(self, old_listener, listener):
        old_t = old_listener['keepalive_timeout']
        new_t = listener['keepalive_timeout']
        if new_t == -1:
            return old_t
        else:
            return new_t

    def need_delete_keepalive(self, service):
        listener = service.get('listener')
        if listener is None:
            return False
        k_t = listener.get('keepalive_timeout')
        return True if k_t != -1 else False

    def delete_keepalive_profile(self, service, vip, bigip):
        listener = service.get('listener')
        k_t = listener.get('keepalive_timeout')
        if listener is not None and k_t != -1:
            self.remove_profile(service, vip, bigip, side="server")

    def add_keepalive_tcp_profile(self, service, vip, bigip, **kwargs):
        keepalive_timeout = kwargs.get('keepalive_timeout')
        side = kwargs.get("side")
        tcp_options = kwargs.get("tcp_options")
        tcp_options = "{%s first}" % tcp_options if tcp_options else None

        partition = vip['partition']
        profile_name = self.get_profile_name(service, side)
        profile = "/" + partition + "/" + profile_name

        profile_exists = self.tcp_helper.exists(
            bigip,
            name=profile_name,
            partition=partition
        )

        if not profile_exists:
            payload = dict(
                name=profile_name,
                partition=partition,
                tcpOptions=tcp_options,
                idleTimeout=keepalive_timeout,
            )
            LOG.info(
                "Add customized keepalive TCP profile: {} for "
                "BIGIP: {} ".format(
                    profile, bigip.hostname
                )
            )
            self.tcp_helper.create(bigip, payload)
        else:
            profile = self.tcp_helper.load(bigip, name=profile_name,
                                           partition=partition)
            profile.modify(idleTimeout=keepalive_timeout)

        server_profile_body = {
            "name": profile_name,
            "partition": partition,
            "context": "serverside"
        }
        client_profile_body = {
            "name": "tcp",
            "partition": "Common",
            "context": "clientside"
        }
        if vip.get('profiles'):
            delete_fastL4s = vip['profiles'].count("/Common/fastL4")
            for _ in range(delete_fastL4s):
                vip['profiles'].remove("/Common/fastL4")

            if server_profile_body not in vip['profiles']:
                vip['profiles'].append(server_profile_body)
            if client_profile_body not in vip['profiles']:
                vip['profiles'].append(client_profile_body)
        else:
            profiles = [server_profile_body, client_profile_body]
            vip['profiles'] = profiles

        self.delete_profile = False
