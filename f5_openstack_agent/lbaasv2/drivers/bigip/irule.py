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
import netaddr

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class iRuleHelper(object):
    """A tool class for tcp irule process"""

    def __init__(self):
        self.irule_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.rule
        )
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual
        )
        self.proxy_allowed = ["TCP"]
        self.delete_iRule = False

    @staticmethod
    def create_v4_iRule_content(tcp_options):
        template = """when SERVER_INIT {
            scan [getfield [IP::client_addr] "%%" 1] {%%d.%%d.%%d.%%d} a b c d
            TCP::option set %s [binary format cccc $a $b $c $d] all
            set string "[TCP::client_port] $a$b$c$d"
            log local0. "IPv4 set to tcp option %s $string"
          }""" % (tcp_options, tcp_options)

        return template

    @staticmethod
    def create_v6_iRule_content(tcp_options):
        template =\
          """
          when SERVER_INIT {
            TCP::option set %s \
[binary format H* [call expand_ipv6_addr [IP::client_addr]]] all
            set string \
[format %%04x [TCP::client_port]][call expand_ipv6_addr [IP::client_addr]]
            log local0. "IPv6 set to tcp option %s $string"
          }
          proc expand_ipv6_addr { addr } {
              if { [catch {
                  if { [set id [getfield $addr "%%" 2]] ne "" } then {
                      set id "%%$id"
                      set addr [getfield $addr "%%" 1]
                  }
                  set blk1 ""
                  foreach val [split [getfield $addr "::" 1] ":"] {
                      if { $val contains "." } then {
                              scan $val {%%d.%%d.%%d.%%d} oct1 oct2 oct3 oct4
                              append blk1 \
[format "%%02x%%02x%%02x%%02x" $oct1 $oct2 $oct3 $oct4]
                              unset -nocomplain oct1 oct2 oct3 oct4
                          } else {
                              append blk1 "[format %%04x 0x$val]"
                          }
                  }
                  set blk2 ""
                  foreach val [split [getfield $addr "::" 2] ":"] {
                      if { $val contains "." } then {
                              scan $val {%%d.%%d.%%d.%%d} oct1 oct2 oct3 oct4
                              append blk2 \
[format "%%02x%%02x%%02x%%02x" $oct1 $oct2 $oct3 $oct4]
                              unset -nocomplain oct1 oct2 oct3 oct4
                          } else {
                              append blk2 "[format %%04x 0x$val]"
                          }
                  }
                  set addr \
"$blk1[string repeat "0000" [expr {8 - [string length "$blk1$blk2"]/4}]]$blk2"
              }] } then {
                   log local0.debug "errorInfo: [subst \\$::errorInfo]"
                   return "errorInfo: [subst \\$::errorInfo]"
                  return ""
              }
              return "$addr"
          }
          """ % (tcp_options, tcp_options)

        return template

    @staticmethod
    def proxy_protocol_irule_content():
        template =\
            """
            when CLIENT_ACCEPTED {
    set proxyheader "PROXY TCP[IP::version] \
[getfield [IP::remote_addr] "%" 1] [getfield [IP::local_addr] "%" 1] \
[TCP::remote_port] [TCP::local_port]\\r\\n"
}
when SERVER_CONNECTED {
    TCP::respond $proxyheader
}"""
        return template

    def create_iRule(self, service, vip, bigip, **kwargs):
        tcp_options = kwargs.get("tcp_options")
        # pzhang we need to create iRule content for IPv6 and IPv4
        ip_version = kwargs.get("ip_version")
        payload = {}

        listener = service.get('listener')
        protocol = listener.get('protocol')
        if listener.get('proxy_protocol') and protocol in self.proxy_allowed:
            LOG.debug('create proxy protocol irule')
            irule_apiAnonymous = self.proxy_protocol_irule_content()
        else:
            if ip_version == 4:
                irule_apiAnonymous = self.create_v4_iRule_content(
                    tcp_options)
            else:
                irule_apiAnonymous = self.create_v6_iRule_content(
                    tcp_options)

        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, "TOA")
        irule_fullPath = "/" + irule_partition + "/" + irule_name

        irule_exists = self.irule_helper.exists(
            bigip,
            name=irule_name,
            partition=irule_partition
        )

        if not irule_exists:
            payload = dict(
                name=irule_name,
                partition=irule_partition,
                apiAnonymous=irule_apiAnonymous
            )
            LOG.info(
                "Create TOA iRule: {} for "
                "BIGIP: {} ".format(
                    irule_fullPath, bigip.hostname
                )
            )
            self.irule_helper.create(bigip, payload)

        if vip['rules']:
            if irule_fullPath not in vip['rules']:
                vip['rules'].append(irule_fullPath)
        else:
            vip['rules'] = [irule_fullPath]

        self.delete_iRule = False

    def update_iRule(self, service, vip, bigip, **kwargs):

        tcp_options = kwargs.get("tcp_options")
        ip_version = kwargs.get("ip_version")
        new_listener = service.get("listener")
        transparent = new_listener.get("transparent")

        payload = {}

        if ip_version == 4:
            irule_apiAnonymous = self.create_v4_iRule_content(
                tcp_options)
        else:
            irule_apiAnonymous = self.create_v6_iRule_content(
                tcp_options)

        vs_name = vip['name']
        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, "TOA")
        irule_fullPath = "/" + irule_partition + "/" + irule_name

        irule_exists = self.irule_helper.exists(
            bigip,
            name=irule_name,
            partition=irule_partition
        )

        vs = self.vs_helper.load(bigip, name=vs_name,
                                 partition=irule_partition)

        if transparent:
            if not irule_exists:
                payload = dict(
                    name=irule_name,
                    partition=irule_partition,
                    apiAnonymous=irule_apiAnonymous
                )

                LOG.info(
                    "Updating to create TOA iRule: {} for "
                    "BIGIP: {} ".format(
                        irule_fullPath, bigip.hostname
                    )
                )
                self.irule_helper.create(bigip, payload)

            vip_rules = [irule_fullPath]
            vip_rules += vs.rules if vs.rules is not None else list()
            vip['rules'] = vip_rules

            self.delete_iRule = False
        else:
            vip_rules = vs.rules if vs.rules is not None else list()

            if vip_rules and irule_fullPath in vip_rules:
                num = vip_rules.count(irule_fullPath)
                for _ in range(num):
                    vip_rules.remove(irule_fullPath)

            vip['rules'] = vip_rules

            LOG.info(
                "Updating to unbind TOA iRule: {} for "
                "BIGIP: {} ".format(
                    irule_fullPath, bigip.hostname
                )
            )

            self.delete_iRule = True

    def remove_iRule(self, service, vip, bigip):
        # pzhang: the listener is removed, before the irule is removed.

        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, "TOA")

        LOG.info(
            "Remove customized TCP irule: {} from "
            "BIGIP: {}".format(
                irule_name, bigip.hostname
            )
        )

        self.irule_helper.delete(
            bigip,
            name=irule_name,
            partition=irule_partition
        )

    @staticmethod
    def get_irule_name(service, prefix):
        prefix = prefix
        listener_id = service.get('listener').get('id')
        irule_name = prefix + '_' + listener_id
        return irule_name

    def need_update_proxy(self, old_listener, listener):
        if old_listener is None or listener is None:
            return False
        if listener['transparent'] is False:
            return False
        if old_listener['transparent'] is False \
                and listener['transparent'] is True:
            if listener.get('protocol') in self.proxy_allowed:
                return True
            else:
                return False

        if old_listener['proxy_protocol'] != listener['proxy_protocol']:
            protocol = listener.get('protocol')
            if protocol not in self.proxy_allowed:
                return False
            return True
        else:
            return False

    def update_proxy_protocol_irule(self, service, vip, bigip, **kwargs):
        tcp_options = kwargs.get("tcp_options")
        new_listener = service.get("listener")
        proxy_protocol = new_listener.get("proxy_protocol")
        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, "TOA")
        irule_fullPath = "/" + irule_partition + "/" + irule_name

        irule = self.irule_helper.load(bigip,
                                       name=irule_name,
                                       partition=irule_partition)
        if proxy_protocol:
            irule_apiAnonymous = self.proxy_protocol_irule_content()
            LOG.info("Update proxy protocol iRule: {} for BIGIP: {}"
                     .format(irule_fullPath, bigip.hostname))
        else:
            loadbalancer = service.get('loadbalancer', dict())
            ip_address = loadbalancer.get("vip_address", None)
            pure_ip_address = ip_address.split("%")[0]
            ip_version = netaddr.IPAddress(pure_ip_address).version

            if ip_version == 4:
                irule_apiAnonymous = self.create_v4_iRule_content(
                    tcp_options)
            else:
                irule_apiAnonymous = self.create_v6_iRule_content(
                    tcp_options)
            LOG.info("Update TOA iRule: {} for BIGIP: {}"
                     .format(irule_fullPath, bigip.hostname))

        irule.modify(apiAnonymous=irule_apiAnonymous)
