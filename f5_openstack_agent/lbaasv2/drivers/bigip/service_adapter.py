# coding=utf-8
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

import netaddr

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip.lbaas_service import \
    LbaasServiceObject
from f5_openstack_agent.lbaasv2.drivers.bigip import utils

LOG = logging.getLogger(__name__)


class UnsupportedProtocolException(Exception):
    pass


class ServiceModelAdapter(object):
    """Class to translate LBaaS service objects to BIG-IP model objects.

    Creates BIG-IP model objects (dictionary of resource attributes) given
    an LBaaS service objet.
    """

    def __init__(self, conf):
        """Initialize the service model adapter with config."""
        self.conf = conf
        if self.conf.environment_prefix:
            self.prefix = self.conf.environment_prefix + '_'
        else:
            self.prefix = utils.OBJ_PREFIX + '_'

    def _get_pool_monitor(self, pool, service):
        """Return a reference to the pool monitor definition."""
        pool_monitor_id = pool.get('healthmonitor_id', "")
        if not pool_monitor_id:
            return None

        monitors = service.get("healthmonitors", list())
        for monitor in monitors:
            if monitor.get('id', "") == pool_monitor_id:
                return monitor

        return None

    def get_pool(self, service):
        pool = service["pool"]
        members = service.get('members', list())
        loadbalancer = service["loadbalancer"]
        healthmonitor = self._get_pool_monitor(pool, service)

        return self._map_pool(loadbalancer, pool, healthmonitor, members)

    def snat_mode(self):
        return self.conf.f5_snat_mode

    def snat_count(self, loadbalancer):
        if self.conf.f5_global_routed_mode:
            return 0

        addr = loadbalancer['vip_address'].split('%')[0]
        ip_version = netaddr.IPAddress(addr).version

        return constants_v2.FLAVOR_SNAT_MAP[ip_version][
            loadbalancer['flavor']
        ]

    def vip_on_common_network(self, service):
        loadbalancer = service.get('loadbalancer', {})
        network_id = loadbalancer.get('network_id', "")
        return (network_id in self.conf.common_network_ids)

    def init_pool_name(self, loadbalancer, pool):
        """Return a barebones pool object with name and partition."""
        partition = self.get_folder_name(loadbalancer['tenant_id'])
        name = self.prefix + pool["id"] if pool else ''

        return {"name": name,
                "partition": partition}

    def get_resource_description(self, resource):
        if not isinstance(resource, dict):
            raise ValueError

        full_description = resource.get('name', "")
        description = resource.get('description', "")
        if full_description:
            full_description += ":"
            if description:
                full_description += (" %s" % (description))
        elif description:
            full_description = description
        else:
            full_description = ""

        return full_description

    def get_virtual(self, service):
        listener = service["listener"]
        loadbalancer = service["loadbalancer"]

        listener["use_snat"] = self.snat_mode()

        if listener["use_snat"] and self.snat_count(loadbalancer) > 0:
            listener["snat_pool_name"] = self.get_folder_name(
                loadbalancer["id"])

        pool = self.get_vip_default_pool(service)

        # here it replaced the sp with pool's sp.
        if pool and "session_persistence" in pool:
            listener["session_persistence"] = pool["session_persistence"]

        listener_policies = self.get_listener_policies(service)
        listener_irules = self.get_listener_irules(service)

        vip = self._map_virtual(loadbalancer, listener, pool=pool,
                                policies=listener_policies,
                                irules=list(listener_irules))

        return vip

    def get_listener_irules(self, service):
        return [r["name"] for r in service.get("irules", [])]

    def get_listener_policies(self, service):
        """Return a map of listener L7 policy ids to a list of L7 rules."""
        lbaas_service = LbaasServiceObject(service)
        listener_policies = list()

        listener = service.get('listener', None)
        if not listener:
            return listener_policies

        listener_l7policy_ids = listener.get('l7_policies', list())
        LOG.debug("L7 debug: listener policies: %s", listener_l7policy_ids)
        for policy in listener_l7policy_ids:
            listener_policy = lbaas_service.get_l7policy(policy['id'])
            LOG.debug("L7 debug: listener policy: %s", listener_policy)
            if not listener_policy:
                LOG.warning("Referenced L7 policy %s for listener %s not "
                            "found in service.", policy['id'], listener['id'])
                continue

            listener_l7policy_rules = list()
            rules = listener_policy.get('rules', list())
            for rule in rules:
                l7policy_rule = lbaas_service.get_l7rule(rule['id'])
                if not l7policy_rule:
                    LOG.warning("Referenced L7 rule %s for policy %s not "
                                "found in service.", rule['id'], policy['id'])
                    continue

                if l7policy_rule['provisioning_status'] != "PENDING_DELETE":
                    listener_l7policy_rules.append(l7policy_rule)

            listener_policy['l7policy_rules'] = listener_l7policy_rules
            listener_policies.append(listener_policy)

        return listener_policies

    def get_virtual_name(self, service):
        vs_name = None
        if "listener" in service:
            listener = service["listener"]
            loadbalancer = service["loadbalancer"]
            vs_name = self._init_virtual_name(loadbalancer, listener)
        return vs_name

    def _init_virtual_name(self, loadbalancer, listener):
        name = self.prefix + listener["id"]
        partition = self.get_folder_name(loadbalancer['tenant_id'])

        return dict(name=name, partition=partition)

    @staticmethod
    def _pending_delete(resource):
        return (
            resource.get('provisioning_status', "") == "PENDING_DELETE"
        )

    def get_vip_default_pool(self, service):
        listener = service["listener"]
        pools = service.get("pools", list())

        default_pool = None
        if "default_pool_id" in listener:
            for pool in pools:
                if listener['default_pool_id'] == pool['id']:
                    if not self._pending_delete(pool):
                        default_pool = pool
                    break

        return default_pool

    def get_member(self, service):
        loadbalancer = service["loadbalancer"]
        member = service["member"]
        return self._map_member(loadbalancer, member)

    def get_member_node(self, service):
        loadbalancer = service["loadbalancer"]
        member = service["member"]
        return self._map_node(loadbalancer, member)

    def get_healthmonitor(self, service):
        healthmonitor = service["healthmonitor"]
        loadbalancer = service["loadbalancer"]
        return self._map_healthmonitor(loadbalancer,
                                       healthmonitor)

    def get_folder(self, service):
        loadbalancer = service["loadbalancer"]
        # XXX maybe ServiceModelAdapter should get the data it needs on
        # __init__?
        folder = None

        if "tenant_id" in loadbalancer:
            tenant_id = loadbalancer["tenant_id"]
            folder_name = self.get_folder_name(tenant_id)
            folder = {"name": folder_name,
                      "subPath": "/",
                      "fullPath": "/" + folder_name,
                      "hidden": False,
                      "inheritedDevicegroup": True}
            if "traffic_group" in loadbalancer:
                folder['trafficGroup'] = loadbalancer["traffic_group"]
                folder['inheritedTrafficGroup'] = False
            else:
                folder['inheritedTrafficGroup'] = True

        return folder

    def get_folder_name(self, tenant_id):
        # XXX Use of getter questionable move to @property?
        if tenant_id is not None:
            name = self.prefix + \
                tenant_id.replace('/', '')
        else:
            name = "Common"

        return name

    def _map_healthmonitor(self, loadbalancer, lbaas_healthmonitor):
        healthmonitor = self.init_monitor_name(loadbalancer,
                                               lbaas_healthmonitor)

        healthmonitor["description"] = " "

        # type
        if "type" in lbaas_healthmonitor:
            # healthmonitor["type"] = lbaas_healthmonitor["type"].lower()
            if (lbaas_healthmonitor["type"] == "HTTP" or
                    lbaas_healthmonitor["type"] == "HTTPS"):

                # http_method
                if lbaas_healthmonitor.get('http_method') == 'HEAD':
                    http_method = 'HEAD'
                    LOG.info('using http_method HEAD')
                else:
                    http_method = 'GET'
                    LOG.info('using http_method GET')

                # url path
                if "url_path" in lbaas_healthmonitor:
                    healthmonitor["send"] = (http_method + " " +
                                             lbaas_healthmonitor["url_path"] +
                                             " HTTP/1.0\\r\\n\\r\\n")
                    LOG.debug('healthmonitor["send"] is ')
                    LOG.debug(healthmonitor["send"])
                else:
                    healthmonitor["send"] = (
                        http_method + " / HTTP/1.0\\r\\n\\r\\n"
                    )
                    LOG.debug('healthmonitor["send"] is ')
                    LOG.debug(healthmonitor["send"])

                # expected codes
                healthmonitor["recv"] = self._get_recv_text(
                    lbaas_healthmonitor)

        # interval - delay
        if "delay" in lbaas_healthmonitor:
            healthmonitor["interval"] = lbaas_healthmonitor["delay"]
            LOG.info('using interval:')
            LOG.info(healthmonitor["interval"])

        # timeout
        if "timeout" in lbaas_healthmonitor:
            if "max_retries" in lbaas_healthmonitor:
                if "delay" in lbaas_healthmonitor:
                    # timeout = (int(lbaas_healthmonitor["max_retries"]) *
                    #            int(lbaas_healthmonitor["timeout"]))
                    timeout = (
                        int(lbaas_healthmonitor["delay"]) *
                        (int(lbaas_healthmonitor["max_retries"]) - 1) +
                        int(lbaas_healthmonitor["timeout"])
                    )
                    healthmonitor["timeout"] = timeout
                    LOG.info('using timeout:')
                    LOG.info(healthmonitor["timeout"])

        return healthmonitor

    def init_monitor_name(self, loadbalancer, monitor):
        name = self.prefix + monitor["id"]

        return {"name": name,
                "partition": self.get_folder_name(loadbalancer['tenant_id'])}

    def _get_recv_text(self, lbaas_healthmonitor):
        if "expected_codes" in lbaas_healthmonitor:
            try:
                if lbaas_healthmonitor['expected_codes'].find(",") > 0:
                    status_codes = (
                        lbaas_healthmonitor['expected_codes'].split(','))
                    recv_text = "HTTP/1.(0|1) ("
                    for status in status_codes:
                        int(status)
                        recv_text += status + "|"
                    recv_text = recv_text[:-1]
                    recv_text += ")"
                elif lbaas_healthmonitor['expected_codes'].find("-") > 0:
                    status_range = (
                        lbaas_healthmonitor['expected_codes'].split('-'))
                    start_range = status_range[0]
                    int(start_range)
                    stop_range = status_range[1]
                    int(stop_range)
                    recv_text = (
                        "HTTP/1.(0|1) [" +
                        start_range + "-" +
                        stop_range + "]"
                    )
                else:
                    int(lbaas_healthmonitor['expected_codes'])
                    recv_text = "HTTP/1.(0|1) " +\
                        lbaas_healthmonitor['expected_codes']
            except Exception as exc:
                LOG.error(
                    "invalid monitor: %s, expected_codes %s, setting to 200"
                    % (exc, lbaas_healthmonitor['expected_codes']))
                recv_text = "HTTP/1.(0|1) 200"
        else:
            recv_text = "HTTP/1.(0|1) 200"

        return recv_text

    def get_monitor_type(self, service):
        monitor_type = None
        lbaas_healthmonitor = service["healthmonitor"]
        if "type" in lbaas_healthmonitor:
            monitor_type = lbaas_healthmonitor["type"]
        return monitor_type

    def _map_pool(self, loadbalancer, lbaas_pool, lbaas_hm, lbaas_members):
        pool = self.init_pool_name(loadbalancer, lbaas_pool)
        pool["description"] = " "

        if "lb_algorithm" in lbaas_pool:
            lbaas_lb_method = lbaas_pool['lb_algorithm'].upper()
            pool['loadBalancingMode'] = \
                self._set_lb_method(lbaas_lb_method, lbaas_members)

            # If source_ip lb method, add SOURCE_IP persistence to ensure
            # source IP loadbalancing. See issue #344 for details.
            if lbaas_pool['lb_algorithm'].upper() == 'SOURCE_IP':
                # SOURCE_IP lb algorithm use source-ip persist profile
                # not replace this for CALL_ID
                if lbaas_pool.get('session_persistence', None) and lbaas_pool['session_persistence'].get('type') == 'CALL_ID': # noqa
                    LOG.debug('not replace for call_id')
                else:
                    lbaas_pool['session_persistence'] = {'type': 'SOURCE_IP'}

        if lbaas_hm:
            hm = self.init_monitor_name(loadbalancer, lbaas_hm)
            pool["monitor"] = hm["name"]
        else:
            pool["monitor"] = ""

        members = list()
        for member in lbaas_members:
            provisioning_status = member.get('provisioning_status', "")
            if provisioning_status != "PENDING_DELETE":
                members.append(self._map_member(loadbalancer, member))

        pool["members"] = members

        return pool

    def _set_lb_method(self, lbaas_lb_method, lbaas_members):
        """Set pool lb method depending on member attributes."""
        lb_method = self._get_lb_method(lbaas_lb_method)

        if lbaas_lb_method == 'SOURCE_IP':
            return lb_method

        member_has_weight = False
        for member in lbaas_members:
            if 'weight' in member and member['weight'] > 1 and \
                    member['provisioning_status'] != 'PENDING_DELETE':
                member_has_weight = True
                break
        if member_has_weight:
            if lbaas_lb_method == 'LEAST_CONNECTIONS':
                return self._get_lb_method('RATIO_LEAST_CONNECTIONS')
            return self._get_lb_method('RATIO')
        return lb_method

    def _get_lb_method(self, method):
        lb_method = method.upper()

        if lb_method == 'LEAST_CONNECTIONS':
            return 'least-connections-member'
        elif lb_method == 'RATIO_LEAST_CONNECTIONS':
            return 'ratio-least-connections-member'
        elif lb_method == 'SOURCE_IP':
            return 'least-connections-member'
        elif lb_method == 'OBSERVED_MEMBER':
            return 'observed-member'
        elif lb_method == 'PREDICTIVE_MEMBER':
            return 'predictive-member'
        elif lb_method == 'RATIO':
            return 'ratio-member'
        else:
            return 'round-robin'

    def _map_virtual(self, loadbalancer, listener,
                     pool=None, policies=None, irules=[]):
        if policies:
            LOG.debug("L7_debug: policies: %s", policies)
        vip = self._init_virtual_name(loadbalancer, listener)
        vip["description"] = " "

        if pool:
            pool_name = self.init_pool_name(loadbalancer, pool)
            vip['pool'] = pool_name.get('name', "")
        else:
            vip['pool'] = ""

        port = listener.get("protocol_port", None)
        ip_address = loadbalancer.get("vip_address", None)
        if ip_address and port >= 0:
            if str(ip_address).endswith('%0'):
                ip_address = ip_address[:-2]

            if ':' in ip_address:
                vip['destination'] = ip_address + "." + str(port)
            else:
                vip['destination'] = ip_address + ":" + str(port)
        else:
            LOG.error("No VIP address or port specified")

        # differeniate the ipv4 and ipv6 cases
        pure_ip_address = ip_address.split("%")[0]
        ip_version = netaddr.IPAddress(pure_ip_address)
        if ip_version.version == 4:
            vip["mask"] = '255.255.255.255'
        elif ip_version.version == 6:
            vip["mask"] = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'
        else:
            LOG.error("Not a validate ip address")

        if "admin_state_up" in listener:
            if listener["admin_state_up"]:
                vip["enabled"] = True
            else:
                vip["disabled"] = True

        self._add_vlan_and_snat(listener, vip)
        self._add_profiles_session_persistence(listener, pool, vip)

        # Set bandwidth controller
        if 'bwcPolicy' in listener:
            vip['bwcPolicy'] = listener.get("bwcPolicy")

        existed_irules = vip.get('rules', [])
        irules += existed_irules
        vip['rules'] = irules
        vip['policies'] = list()

        if self.conf.connection_rate_limit_ratio and \
                loadbalancer.get('flavor') is not None:
            ratio = self.conf.connection_rate_limit_ratio
            flavor_id = loadbalancer['flavor']

            if flavor_id == 0:
                listener_rate_limit = 0
            else:
                # predefined table is not using 1024 etc. seems fine though.
                # convenient to be divided by 5, by default.
                flavor_dict = constants_v2.FLAVOR_CONN_MAP

                try:
                    limit_value = flavor_dict[str(flavor_id)]
                except KeyError:
                    LOG.error("Flavor is invalid. Skip to configure limit.")
                    return vip

                rate_limit = limit_value['rate_limit']
                # Overwrite the default value for flavor 21 only
                if flavor_id == 21:
                    rate_limit = loadbalancer.get("new_connection", rate_limit)
                listener_rate_limit = rate_limit / ratio

                vip["rateLimit"] = listener_rate_limit

                vip['rateLimitMode'] = 'destination'
                if ip_version.version == 4:
                    vip['rateLimitDstMask'] = 32
                else:
                    vip['rateLimitDstMask'] = 128

        else:
            LOG.info('limit part is not run this time.')

        vip['connectionLimit'] = 0

        return vip

    def _add_profiles_session_persistence(self, listener, pool, vip):

        protocol = listener.get('protocol', "")
        if protocol not in ["HTTP", "HTTPS", "TCP", 'FTP',
                            "TERMINATED_HTTPS", "UDP", "SIP"]:
            LOG.warning("Listener protocol unrecognized: %s",
                        listener["protocol"])

        if protocol in ['TCP', 'UDP']:
            virtual_type = 'fastl4'
        else:
            virtual_type = 'standard'

        if protocol == "UDP" or protocol == "SIP":
            vip["ipProtocol"] = "udp"
        else:
            vip["ipProtocol"] = "tcp"

        if virtual_type == 'fastl4':
            vip['profiles'] = ['/Common/fastL4']
        elif virtual_type == 'standard' and protocol == 'TCP':
            vip['profiles'] = ['/Common/tcp']
        elif virtual_type == 'standard' and protocol in ('UDP', 'SIP'):
            vip['profiles'] = ['/Common/udp']
        elif virtual_type == 'mr' and protocol == 'TCP':
            vip['profiles'] = ['/Common/tcp']
        else:
            # add profiles for HTTP, TERMINATED_HTTPS protocols
            vip['profiles'] = ['/Common/http', '/Common/oneconnect']

        vip['fallbackPersistence'] = ''
        vip['persist'] = []

        persistence = None
        if pool:
            persistence = pool.get('session_persistence', None)
            lb_algorithm = pool.get('lb_algorithm', 'ROUND_ROBIN')

        valid_persist_types = ['SOURCE_IP', 'APP_COOKIE', 'HTTP_COOKIE', 'SOURCE_IP_PORT', 'CALL_ID'] # noqa
        if persistence:
            persistence_type = persistence.get('type', "")
            if persistence_type not in valid_persist_types:
                LOG.warning("Invalid peristence type: %s",
                            persistence_type)
                return

            if persistence_type == 'APP_COOKIE':
                vip['persist'] = [{'name': 'app_cookie_' + vip['name']}]

            if persistence_type == 'SOURCE_IP_PORT':
                vip['persist'] = [{'name': 'source_ip_port_' + vip['name']}]

            elif persistence_type == 'SOURCE_IP':
                vip['persist'] = [{'name': '/Common/source_addr'}]

            elif persistence_type == 'CALL_ID':
                LOG.debug('CALL_ID here')
                vip['persist'] = [{'name': 'sip_' + vip['name']}]

            elif persistence_type == 'HTTP_COOKIE':
                vip['persist'] = [{'name': '/Common/cookie'}]

            if persistence_type != 'SOURCE_IP':
                if lb_algorithm == 'SOURCE_IP':
                    vip['fallbackPersistence'] = '/Common/source_addr'

            if persistence_type in ['HTTP_COOKIE', 'APP_COOKIE']:
                vip['profiles'] = ['/Common/http', '/Common/oneconnect']

        if protocol == 'SIP':
            LOG.debug('adding sip profile')
            if '/Common/sip' not in vip['profiles']:
                vip['profiles'].append('/Common/sip')

    def get_vlan(self, vip, bigip, network_id):
        if network_id in bigip.assured_networks:
            vip['vlans'].append(
                bigip.assured_networks[network_id])
            vip['vlansEnabled'] = True
            vip.pop('vlansDisabled', None)
        elif network_id in self.conf.common_network_ids:
            vip['vlans'].append(
                self.conf.common_network_ids[network_id])
            vip['vlansEnabled'] = True
            vip.pop('vlansDisabled', None)

    def _add_vlan_and_snat(self, listener, vip):

        # snat
        if "use_snat" in listener and listener["use_snat"]:
            vip['sourceAddressTranslation'] = {}
            if "snat_pool_name" in listener:
                vip['sourceAddressTranslation']['type'] = 'snat'
                vip['sourceAddressTranslation']['pool'] = \
                    listener["snat_pool_name"]
            else:
                vip['sourceAddressTranslation']['type'] = 'automap'
        else:
            vip['sourceAddressTranslation'] = {}
            vip['sourceAddressTranslation']['type'] = None
            vip['sourceAddressTranslation']['pool'] = None

        # default values for pinning the VS to a specific VLAN set
        vip['vlansDisabled'] = True
        vip['vlans'] = []

    def _map_member(self, loadbalancer, lbaas_member):
        member = {}
        port = lbaas_member["protocol_port"]
        ip_address = lbaas_member["address"]
        id_des = str(lbaas_member["id"])

        if lbaas_member["admin_state_up"]:
            member["session"] = "user-enabled"
        else:
            member["session"] = "user-disabled"

        if lbaas_member["weight"] == 0:
            member["ratio"] = 1
            member["session"] = "user-disabled"
        else:
            member["ratio"] = lbaas_member["weight"]

        if ':' in ip_address:
            member['name'] = ip_address + '.' + str(port)
        else:
            member['name'] = ip_address + ':' + str(port)
        member["partition"] = self.get_folder_name(loadbalancer["tenant_id"])
        member["address"] = ip_address
        member["description"] = self.prefix + id_des

        return member

    def _map_node(self, loadbalancer, lbaas_member):
        member = {}
        member["name"] = lbaas_member["address"]
        member["partition"] = self.get_folder_name(loadbalancer["tenant_id"])

        return member

    def get_network_from_service(self, service, network_id):
        if 'networks' in service:
            return service['networks'][network_id]

    def get_subnet_from_service(self, service, subnet_id):
        if 'subnets' in service:
            return service['subnets'][subnet_id]

    def get_tls(self, service):
        tls = {}
        listener = service['listener']
        if listener['protocol'] == 'TERMINATED_HTTPS':
            for tls_key in [
                'default_tls_container_id',
                'sni_containers',
                # client auth parameters
                'mutual_authentication_up',
                'ca_container_id',
                # cipher parameters
                'tls_protocols',
                'cipher_suites',
                'cipher_policy',
                'http2'
            ]:
                if tls_key in listener and listener[tls_key]:
                    tls[tls_key] = listener[tls_key]
        return tls

    def get_name(self, uuid):
        return self.prefix + str(uuid)
