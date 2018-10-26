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

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import ssl_profile
from requests import HTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex

LOG = logging.getLogger(__name__)


class ListenerServiceBuilder(object):
    u"""Create LBaaS v2 Listener on BIG-IPs.

    Handles requests to create, update, delete LBaaS v2 listener
    objects on one or more BIG-IP systems. Maps LBaaS listener
    defined in service object to a BIG-IP virtual server.
    """

    def __init__(self, service_adapter, cert_manager, parent_ssl_profile=None):
        self.cert_manager = cert_manager
        self.parent_ssl_profile = parent_ssl_profile
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.service_adapter = service_adapter
        LOG.debug("ListenerServiceBuilder: using parent_ssl_profile %s ",
                  parent_ssl_profile)

    def create_listener(self, service, bigips, esd=None):
        u"""Create listener on set of BIG-IPs.

        Create a BIG-IP virtual server to represent an LBaaS
        Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create Listener.
        """
        loadbalancer = service.get('loadbalancer', dict())
        listener = service.get('listener', dict())
        network_id = loadbalancer.get('network_id', "")

        vip = self.service_adapter.get_virtual(service)
        tls = self.service_adapter.get_tls(service)
        if tls:
            tls['name'] = vip['name']
            tls['partition'] = vip['partition']

        persist = listener.get("session_persistence", None)
        error = None
        for bigip in bigips:

            self.service_adapter.get_vlan(vip, bigip, network_id)

            if tls:
                self.add_ssl_profile(tls, vip, bigip)

            if persist and persist.get('type', "") == "APP_COOKIE":
                self._add_cookie_persist_rule(vip, persist, bigip)

            try:
                if self.vs_helper.exists(bigip,
                                         name=vip['name'],
                                         partition=vip['partition']):
                    LOG.debug("Virtual server already exists...updating")
                    self.vs_helper.update(bigip, vip)
                else:
                    LOG.debug("Virtual server does not exist...creating")
                    self.vs_helper.create(bigip, vip)

            except Exception as err:
                error = f5_ex.VirtualServerCreationException(
                    err.message)
                LOG.error("Failed to create virtual server: %s" %
                          error.message)

            if not persist:
                try:
                    self._remove_cookie_persist_rule(vip, bigip)
                except HTTPError as err:
                    LOG.exception(err.message)

        return error

    def get_listener(self, service, bigip):
        u"""Retrieve BIG-IP virtual from a single BIG-IP system.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigip: Array of BigIP class instances to create Listener.
        """
        vip = self.service_adapter.get_virtual_name(service)
        obj = self.vs_helper.load(bigip=bigip,
                                  name=vip["name"],
                                  partition=vip["partition"])
        return obj

    def delete_listener(self, service, bigips):
        u"""Delete Listener from a set of BIG-IP systems.

        Delete virtual server that represents a Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete Listener.
        """
        vip = self.service_adapter.get_virtual_name(service)
        tls = self.service_adapter.get_tls(service)
        if tls:
            tls['name'] = vip['name']
            tls['partition'] = vip['partition']

        error = None
        for bigip in bigips:
            try:
                self.vs_helper.delete(bigip,
                                      name=vip["name"],
                                      partition=vip["partition"])
            except HTTPError as err:
                if err.response.status_code != 404:
                    error = f5_ex.VirtualServerDeleteException(err.message)
                    LOG.error("Virtual server delete error: %s",
                              error.message)
            except Exception as err:
                error = f5_ex.VirtualServerDeleteException(err.message)
                LOG.error("Virtual server delete error: %s",
                          error.message)

            # delete ssl profiles
            self.remove_ssl_profiles(tls, bigip)

            # delete cookie perist rules
            try:
                self._remove_cookie_persist_rule(vip, bigip)
            except HTTPError as err:
                LOG.exception(err.message)

        return error

    def add_ssl_profile(self, tls, vip, bigip):

        if "default_tls_container_id" in tls:
            container_ref = tls["default_tls_container_id"]
            self._create_ssl_profile(
                container_ref, bigip, vip, True)

        if "sni_containers" in tls and tls["sni_containers"]:
            for container in tls["sni_containers"]:
                container_ref = container["tls_container_id"]
                self._create_ssl_profile(container_ref, bigip, vip, False)

    def _create_ssl_profile(
            self, container_ref, bigip, vip, sni_default=False):
        cert = self.cert_manager.get_certificate(container_ref)
        key = self.cert_manager.get_private_key(container_ref)
        name = self.cert_manager.get_name(container_ref,
                                          self.service_adapter.prefix)

        try:
            # upload cert/key and create SSL profile
            ssl_profile.SSLProfileHelper.create_client_ssl_profile(
                bigip, name, cert, key, sni_default=sni_default,
                parent_profile=self.parent_ssl_profile)
        except HTTPError as err:
            if err.response.status_code != 409:
                LOG.error("SSL profile creation error: %s" %
                          err.message)
        finally:
            del cert
            del key

        # add ssl profile to virtual server
        if 'profiles' not in vip:
            vip['profiles'] = list()

        client_ssl_profile = {'name': name, 'context': "clientside"}
        if client_ssl_profile not in vip['profiles']:
            vip['profiles'].append(client_ssl_profile)

    def remove_ssl_profiles(self, tls, bigip):

        if "default_tls_container_id" in tls and \
                tls["default_tls_container_id"]:
            container_ref = tls["default_tls_container_id"]
            try:
                i = container_ref.rindex("/") + 1
            except ValueError as error:
                LOG.exception(error.message)
            else:
                name = self.service_adapter.prefix + container_ref[i:]
                self._remove_ssl_profile(name, bigip)

        if "sni_containers" in tls and tls["sni_containers"]:
            for container in tls["sni_containers"]:
                container_ref = container["tls_container_id"]
                try:
                    i = container_ref.rindex("/") + 1
                except ValueError as error:
                    LOG.exception(error.message)
                else:
                    name = self.service_adapter.prefix + container_ref[i:]
                    self._remove_ssl_profile(name, bigip)

    def _remove_ssl_profile(self, name, bigip):
        """Delete profile.

        :param name: Name of profile to delete.
        :param bigip: Single BigIP instances to update.
        """
        try:
            ssl_client_profile = bigip.tm.ltm.profile.client_ssls.client_ssl
            if ssl_client_profile.exists(name=name, partition='Common'):
                obj = ssl_client_profile.load(name=name, partition='Common')
                obj.delete()

        except Exception as err:
            # Not necessarily an error -- profile might be referenced
            # by another virtual server.
            LOG.warning(
                "Unable to delete profile %s. "
                "Response message: %s." % (name, err.message))

    def delete_orphaned_listeners(self, service, bigips):
        if 'listeners' not in service:
            ip_address = service['loadbalancer']['vip_address']
            if str(ip_address).endswith('%0'):
                ip_address = ip_address[:-2]
            for bigip in bigips:
                vses = bigip.tm.ltm.virtuals.get_collection()
                for vs in vses:
                    if str(vs.destination).startswith(ip_address):
                        vs.delete()
        else:
            listeners = service['listeners']
            for listener in listeners:
                svc = {"loadbalancer": service["loadbalancer"],
                       "listener": listener}
                vip = self.service_adapter.get_virtual(svc)
                for bigip in bigips:
                    vses = bigip.tm.ltm.virtuals.get_collection()
                    orphaned = True
                    for vs in vses:
                        if vip['destination'] == vs.destination:
                            if vip['name'] == vs.name:
                                orphaned = False
                        else:
                            orphaned = False
                    if orphaned:
                        for vs in vses:
                            if vip['name'] == vs.name:
                                vs.delete()

    def _add_cookie_persist_rule(self, vip, persistence, bigip):
        """Add cookie persist rules to virtual server instance.

        :param vip: Dictionary which contains name and partition of
        virtual server.
        :param persistence: Persistence definition.
        :param bigip: Single BigIP instances to update.
        """
        LOG.error("SP_DEBUG: adding cookie persist: %s -- %s",
                  persistence, vip)
        cookie_name = persistence.get('cookie_name', None)
        if not cookie_name:
            return

        rule_name = 'app_cookie_' + vip['name']
        rule_def = self._create_app_cookie_persist_rule(cookie_name)

        r = bigip.tm.ltm.rules.rule
        if not r.exists(name=rule_name, partition=vip["partition"]):
            try:
                r.create(name=rule_name,
                         apiAnonymous=rule_def,
                         partition=vip["partition"])
                LOG.debug("Created rule %s" % rule_name)
            except Exception as err:
                LOG.error("Failed to create rule %s", rule_name)

        u = bigip.tm.ltm.persistence.universals.universal
        if not u.exists(name=rule_name, partition=vip["partition"]):
            try:
                u.create(name=rule_name,
                         rule=rule_name,
                         partition=vip["partition"])
                LOG.debug("Created persistence universal %s" % rule_name)
            except Exception as err:
                LOG.error("Failed to create persistence universal %s" %
                          rule_name)
                LOG.exception(err)

    def _create_app_cookie_persist_rule(self, cookiename):
        """Create cookie persistence rule.

        :param cookiename: Name to substitute in rule.
        """
        rule_text = "when HTTP_REQUEST {\n"
        rule_text += " if { [HTTP::cookie " + str(cookiename)
        rule_text += "] ne \"\" }{\n"
        rule_text += "     persist uie [string tolower [HTTP::cookie \""
        rule_text += cookiename + "\"]] 3600\n"
        rule_text += " }\n"
        rule_text += "}\n\n"
        rule_text += "when HTTP_RESPONSE {\n"
        rule_text += " if { [HTTP::cookie \"" + str(cookiename)
        rule_text += "\"] ne \"\" }{\n"
        rule_text += "     persist add uie [string tolower [HTTP::cookie \""
        rule_text += cookiename + "\"]] 3600\n"
        rule_text += " }\n"
        rule_text += "}\n\n"
        return rule_text

    def _remove_cookie_persist_rule(self, vip, bigip):
        """Delete cookie persist rule.

        :param vip: Dictionary which contains name and partition of
        virtual server.
        :param bigip: Single BigIP instances to update.
        """
        rule_name = 'app_cookie_' + vip['name']

        u = bigip.tm.ltm.persistence.universals.universal
        if u.exists(name=rule_name, partition=vip["partition"]):
            obj = u.load(name=rule_name, partition=vip["partition"])
            obj.delete()
            LOG.debug("Deleted persistence universal %s" % rule_name)

        r = bigip.tm.ltm.rules.rule
        if r.exists(name=rule_name, partition=vip["partition"]):
            obj = r.load(name=rule_name, partition=vip["partition"])
            obj.delete()
            LOG.debug("Deleted rule %s" % rule_name)

    def get_stats(self, service, bigips, stat_keys):
        """Return stat values for a single virtual.

        Stats to collect are defined as an array of strings in input stats.
        Values are summed across one or more BIG-IPs defined in input bigips.

        :param service: Has listener name/partition
        :param bigips: One or more BIG-IPs to get listener stats from.
        :param stat_keys: Array of strings that define which stats to collect.
        :return: A dict with key/value pairs for each stat defined in
        input stats.
        """
        collected_stats = {}
        for stat_key in stat_keys:
            collected_stats[stat_key] = 0

        virtual = self.service_adapter.get_virtual(service)
        part = virtual["partition"]
        for bigip in bigips:
            try:
                vs_stats = self.vs_helper.get_stats(
                    bigip,
                    name=virtual["name"],
                    partition=part,
                    stat_keys=stat_keys)
                for stat_key in stat_keys:
                    if stat_key in vs_stats:
                        collected_stats[stat_key] += vs_stats[stat_key]

            except Exception as e:
                # log error but continue on
                LOG.error("Error getting virtual server stats: %s", e.message)

        return collected_stats
