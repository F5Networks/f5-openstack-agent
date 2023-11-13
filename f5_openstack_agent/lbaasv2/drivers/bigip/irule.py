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
        self.delete_xff_irule = False

    @staticmethod
    def create_v4_iRule_content(tcp_options):
        template = """when SERVER_INIT {
            scan [getfield [IP::client_addr] "%%" 1] {%%d.%%d.%%d.%%d} a b c d
            set port [TCP::client_port]
            TCP::option set %s [binary format Scccc $port $a $b $c $d] all
          }""" % tcp_options

        return template

    @staticmethod
    def create_v6_iRule_content(tcp_options):
        template =\
          """
          when SERVER_INIT {
            set client_port [TCP::client_port]
            TCP::option set %s \
[binary format SH* $client_port [call expand_ipv6_addr [IP::client_addr]]] all
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
          """ % tcp_options

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

    def get_irule_full_path(self, service, vip, prefix):
        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, prefix)
        irule_fullPath = "/" + irule_partition + "/" + irule_name
        return irule_fullPath

    def create_specific_irule(self, service, vip, bigip, prefix=None,
                              apiAnonymous=None, delete=False):
        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, prefix)
        irule_fullPath = "/" + irule_partition + "/" + irule_name

        irule_exists = self.irule_helper.exists(
            bigip,
            name=irule_name,
            partition=irule_partition
        )

        # NOTE(xxx) the 'delete' arguement and this odd snippet for
        # leftover TOA irule campatibility. it will update leftover TOA irule
        # to new form. Maybe delete this snippet in futrue.
        if delete and irule_exists:
            self.irule_helper.delete(
                partition=irule_partition,
                name=irule_name
            )

        if not irule_exists:
            payload = dict(
                name=irule_name,
                partition=irule_partition,
                apiAnonymous=apiAnonymous
            )
            LOG.info(
                "Create iRule: {} for "
                "BIGIP: {} ".format(
                    irule_fullPath, bigip.hostname
                )
            )
            self.irule_helper.create(bigip, payload)
        return irule_fullPath

    def create_iRule(self, service, vip, bigip, **kwargs):
        tcp_options = kwargs.get("tcp_options")
        # pzhang we need to create iRule content for IPv6 and IPv4
        ip_version = kwargs.get("ip_version")

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

        irule_fullPath = self.create_specific_irule(
            service, vip, bigip, prefix="TOA",
            apiAnonymous=irule_apiAnonymous, delete=True)
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

        if ip_version == 4:
            irule_apiAnonymous = self.create_v4_iRule_content(
                tcp_options)
        else:
            irule_apiAnonymous = self.create_v6_iRule_content(
                tcp_options)

        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, "TOA")
        irule_fullPath = "/" + irule_partition + "/" + irule_name
        vs = self.vs_helper.load(bigip, name=vip['name'],
                                 partition=irule_partition)

        if transparent:
            self.create_specific_irule(service, vip, bigip, prefix="TOA",
                                       apiAnonymous=irule_apiAnonymous)
            vip_rules = [irule_fullPath]
            vip_rules += vs.rules if vs.rules is not None else list()
            vip['rules'] = vip_rules

            self.delete_iRule = False
        else:
            self.unbind_specific_irule(vip, vs, bigip, irule_fullPath)
            self.delete_iRule = True

    def unbind_specific_irule(self, vip, vs, bigip, irule_fullPath):
        vip_rules = vs.rules if vs.rules is not None else list()

        if vip_rules and irule_fullPath in vip_rules:
            num = vip_rules.count(irule_fullPath)
            for _ in range(num):
                vip_rules.remove(irule_fullPath)

        vip['rules'] = vip_rules

        LOG.info(
            "Updating to unbind iRule: {} for "
            "BIGIP: {} ".format(
                irule_fullPath, bigip.hostname
            )
        )

    def remove_iRule(self, service, vip, bigip, prefix=None):
        # pzhang: the listener is removed, before the irule is removed.

        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, prefix)

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
        ip_version = kwargs.get("ip_version")
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
            if ip_version == 4:
                irule_apiAnonymous = self.create_v4_iRule_content(
                    tcp_options)
            else:
                irule_apiAnonymous = self.create_v6_iRule_content(
                    tcp_options)
            LOG.info("Update TOA iRule: {} for BIGIP: {}"
                     .format(irule_fullPath, bigip.hostname))

        irule.modify(apiAnonymous=irule_apiAnonymous)

    def enable_rewrite_xff(self, service):
        listener = service.get('listener')
        if listener is None:
            return False
        if listener.get('rewrite_xff'):
            protocol = listener.get('protocol')
            if protocol not in ['HTTP', 'TERMINATED_HTTPS']:
                return False
            return True
        else:
            return False

    def need_update_rewrite_xff(self, old_listener, listener):
        if old_listener is None or listener is None:
            return False

        if listener['protocol'] in ['HTTP', 'TERMINATED_HTTPS']:
            if old_listener['rewrite_xff'] != listener['rewrite_xff']:
                return True
        return False

    @staticmethod
    def rewrite_xff_irule_content():
        template = \
            """
            when HTTP_REQUEST {
    HTTP::header replace X-Forwarded-For [getfield \
[HTTP::header X-Forwarded-For] "," 1]
}"""
        return template

    def create_rewrite_xff(self, service, vip, bigip):
        content = self.rewrite_xff_irule_content()

        irule_fullPath = self.create_specific_irule(service, vip, bigip,
                                                    prefix="rewrite_xff",
                                                    apiAnonymous=content)
        if vip['rules']:
            if irule_fullPath not in vip['rules']:
                vip['rules'].append(irule_fullPath)
        else:
            vip['rules'] = [irule_fullPath]

    def update_rewrite_xff_irule(self, service, vip, bigip):
        new_listener = service.get("listener")
        rewrite_xff = new_listener.get("rewrite_xff")
        irule_partition = vip['partition']
        irule_name = self.get_irule_name(service, "rewrite_xff")
        irule_fullPath = "/" + irule_partition + "/" + irule_name
        vs = self.vs_helper.load(bigip, name=vip['name'],
                                 partition=irule_partition)
        if rewrite_xff:
            content = self.rewrite_xff_irule_content()
            self.create_specific_irule(service, vip, bigip,
                                       prefix="rewrite_xff",
                                       apiAnonymous=content)
            vip_rules = [irule_fullPath]
            vip_rules += vs.rules if vs.rules is not None else list()
            vip['rules'] = vip_rules

            self.delete_xff_irule = False
        else:
            self.unbind_specific_irule(vip, vs, bigip, irule_fullPath)

            self.delete_xff_irule = True
