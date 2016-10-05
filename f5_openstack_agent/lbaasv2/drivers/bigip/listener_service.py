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

import urllib

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.disconnected_service import \
    DisconnectedService
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import ssl_profile
from neutron_lbaas.services.loadbalancer import constants as lb_const

LOG = logging.getLogger(__name__)


class ListenerServiceBuilder(object):
    """Create LBaaS v2 Listener on BIG-IP®s.

    Handles requests to create, update, delete LBaaS v2 listener
    objects on one or more BIG-IP® systems. Maps LBaaS listener
    defined in service object to a BIG-IP® virtual server.
    """

    def __init__(self, service_adapter, cert_manager, parent_ssl_profile=None):
        self.cert_manager = cert_manager
        self.disconnected_service = DisconnectedService()
        self.parent_ssl_profile = parent_ssl_profile
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.service_adapter = service_adapter
        LOG.debug("ListenerServiceBuilder: using parent_ssl_profile %s ",
                  parent_ssl_profile)

    def create_listener(self, service, bigips):
        """Create listener on set of BIG-IP®s.

        Creates a BIG-IP® virtual server to represent an LBaaS
        Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to create Listener.
        """
        vip = self.service_adapter.get_virtual(service)
        tls = self.service_adapter.get_tls(service)
        if tls:
            tls['name'] = vip['name']
            tls['partition'] = vip['partition']

        service['listener']['operating_status'] = lb_const.ONLINE
        # Hierarchical Port Binding mode adjustments
        if not self.disconnected_service.is_service_connected(service):
            # start the virtual server on a disconnected network if the neutron
            # network does not yet exist
            network_name = DisconnectedService.network_name
            vip['vlansEnabled'] = True
            vip.pop('vlansDisabled', None)
            vip['vlans'] = [
                '/%s/%s' % (vip['partition'], network_name)
            ]
            # strip out references to network pieces that don't yet exist
            vip.pop('sourceAddressTranslation', None)
            # the listener is offline until we have a real network
            service['listener']['operating_status'] = lb_const.OFFLINE

        network_id = service['loadbalancer']['network_id']
        for bigip in bigips:
            self.service_adapter.get_vlan(vip, bigip, network_id)
            self.vs_helper.create(bigip, vip)

            if tls:
                self.add_ssl_profile(tls, bigip)

        # Traffic group is added after create in order to take adavantage
        # of BIG-IP® defaults.
        traffic_group = self.service_adapter.get_traffic_group(service)
        if traffic_group:
            ip_address = service['loadbalancer']['vip_address']
            if str(ip_address).endswith('%0'):
                ip_address = ip_address[:-2]
            else:
                ip_address = urllib.quote(ip_address)

            for bigip in bigips:
                virtual_address = \
                    bigip.tm.ltm.virtual_address_s.virtual_address
                obj = virtual_address.load(name=ip_address,
                                           partition=vip['partition'])
                obj.modify(trafficGroup=traffic_group)

    def get_listener(self, service, bigip):
        """Retrieve BIG-IP® virtual from a single BIG-IP® system.

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
        """Delete Listener from a set of BIG-IP® systems.

        Deletes virtual server that represents a Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to delete Listener.
        """
        vip = self.service_adapter.get_virtual_name(service)
        tls = self.service_adapter.get_tls(service)
        if tls:
            tls['name'] = vip['name']
            tls['partition'] = vip['partition']

        for bigip in bigips:
            self.vs_helper.delete(bigip,
                                  name=vip["name"],
                                  partition=vip["partition"])

            # delete ssl profiles
            self.remove_ssl_profiles(tls, bigip)

    def add_ssl_profile(self, tls, bigip):
        # add profile to virtual server
        vip = {'name': tls['name'],
               'partition': tls['partition']}

        if "default_tls_container_id" in tls:
            container_ref = tls["default_tls_container_id"]
            self.create_ssl_profile(
                container_ref, bigip, vip, True)

        if "sni_containers" in tls and tls["sni_containers"]:
            for container in tls["sni_containers"]:
                container_ref = container["tls_container_id"]
                self.create_ssl_profile(container_ref, bigip, vip, False)

    def create_ssl_profile(self, container_ref, bigip, vip, sni_default=False):
        cert = self.cert_manager.get_certificate(container_ref)
        key = self.cert_manager.get_private_key(container_ref)
        name = self.cert_manager.get_name(container_ref,
                                          self.service_adapter.prefix)

        try:
            # upload cert/key and create SSL profile
            ssl_profile.SSLProfileHelper.create_client_ssl_profile(
                bigip,
                name,
                cert,
                key,
                sni_default=sni_default,
                parent_profile=self.parent_ssl_profile)
        finally:
            del cert
            del key

        # add ssl profile to virtual server
        self._add_profile(vip, name, bigip, context='clientside')

    def update_listener(self, service, bigips):
        """Update Listener from a single BIG-IP® system.

        Updates virtual servers that represents a Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to update.
        """
        vip = self.service_adapter.get_virtual(service)

        for bigip in bigips:
            self.vs_helper.update(bigip, vip)

    def update_listener_pool(self, service, name, bigips):
        """Update virtual server's default pool attribute.

        Sets the virutal server's pool attribute to the name of the
        pool (or empty when deleting pool). For LBaaS, this should be
        call when the pool is created.

        :param service: Dictionary which contains a listener, pool,
        and load balancer definition.
        :param name: Name of pool (empty string to unset).
        :param bigips: Array of BigIP class instances to update.
        """
        vip = self.service_adapter.get_virtual_name(service)
        vip["pool"] = name
        for bigip in bigips:
            v = bigip.tm.ltm.virtuals.virtual
            if v.exists(name=vip["name"], partition=vip["partition"]):
                obj = v.load(name=vip["name"], partition=vip["partition"])
                obj.modify(**vip)

    def update_session_persistence(self, service, bigips):
        """Update session persistence for virtual server.

        Handles setting persistence type and creating associated
        profiles if necessary. This should be called when the pool
        is created because LBaaS pools define persistence types, not
        listener objects.

        :param service: Dictionary which contains a listener, pool,
        and load balancer definition.
        :param bigips: Array of BigIP class instances to update.
        """
        pool = service["pool"]
        if "session_persistence" in pool and pool['session_persistence']:
            vip = self.service_adapter.get_virtual_name(service)
            persistence = pool['session_persistence']
            persistence_type = persistence['type']
            vip_persist = self.service_adapter.get_session_persistence(service)
            for bigip in bigips:
                if persistence_type == 'HTTP_COOKIE':
                    self._add_profile(vip, 'http', bigip)
                elif persistence_type == 'APP_COOKIE':
                    self._add_profile(vip, 'http', bigip)
                    if 'cookie_name' in persistence:
                        self._add_cookie_persist_rule(vip, persistence, bigip)

                # profiles must be added before setting profile attribute
                self.vs_helper.update(bigip, vip_persist)
                LOG.debug("Set persist %s" % vip["name"])

    def _add_profile(self, vip, profile_name, bigip, context='all'):
        """Adds profile to virtual server instance. Assumes Common.

        :param vip: Dictionary which contains name and partition of
        virtual server.
        :param profile_name: Name of profile to add.
        :param bigip: Single BigIP instances to update.
        """
        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vip["name"], partition=vip["partition"])
        p = obj.profiles_s
        profiles = p.get_collection()

        # see if profile exists
        for profile in profiles:
            if profile.name == profile_name:
                return

        # not found -- add profile (assumes Common partition)
        p.profiles.create(name=profile_name,
                          partition='Common',
                          context=context)
        LOG.debug("Created profile %s" % profile_name)

    def _add_cookie_persist_rule(self, vip, persistence, bigip):
        """Adds cookie persist rules to virtual server instance.

        :param vip: Dictionary which contains name and partition of
        virtual server.
        :param persistence: Persistence definition.
        :param bigip: Single BigIP instances to update.
        """
        cookie_name = persistence['cookie_name']
        rule_def = self._create_app_cookie_persist_rule(cookie_name)
        rule_name = 'app_cookie_' + vip['name']

        r = bigip.tm.ltm.rules.rule
        if not r.exists(name=rule_name, partition=vip["partition"]):
            r.create(name=rule_name,
                     apiAnonymous=rule_def,
                     partition=vip["partition"])
            LOG.debug("Created rule %s" % rule_name)

        u = bigip.tm.ltm.persistence.universals.universal
        if not u.exists(name=rule_name, partition=vip["partition"]):
            u.create(name=rule_name,
                     rule=rule_name,
                     partition=vip["partition"])
            LOG.debug("Created persistence universal %s" % rule_name)

    def _create_app_cookie_persist_rule(self, cookiename):
        """Creates cookie persistence rule.

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

    def remove_session_persistence(self, service, bigips):
        """Resest persistence for virtual server instance.

        Clears persistence and deletes profiles.

        :param service: Dictionary which contains a listener, pool
        and load balancer definition.
        :param bigips: Single BigIP instances to update.
        """
        pool = service["pool"]
        if "session_persistence" in pool and pool['session_persistence']:
            vip = self.service_adapter.get_virtual_name(service)
            vip["persist"] = []
            vip["fallbackPersistence"] = ""
            persistence = pool['session_persistence']
            persistence_type = persistence['type']

            for bigip in bigips:
                # remove persistence
                self.vs_helper.update(bigip, vip)
                LOG.debug("Cleared session persistence for %s" % vip["name"])

                # remove profiles and rules
                if persistence_type == 'HTTP_COOKIE':
                    self._remove_profile(vip, 'http', bigip)
                elif persistence_type == 'APP_COOKIE':
                    self._remove_profile(vip, 'http', bigip)
                    if 'cookie_name' in persistence:
                        self._remove_cookie_persist_rule(
                            vip, bigip)

    def remove_ssl_profiles(self, tls, bigip):

        if "default_tls_container_id" in tls and \
                tls["default_tls_container_id"]:
            container_ref = tls["default_tls_container_id"]
            i = container_ref.rindex("/") + 1
            name = self.service_adapter.prefix + container_ref[i:]
            self._remove_ssl_profile(name, bigip)

        if "sni_containers" in tls and tls["sni_containers"]:
            for container in tls["sni_containers"]:
                container_ref = container["tls_container_id"]
                i = container_ref.rindex("/") + 1
                name = self.service_adapter.prefix + container_ref[i:]
                self._remove_ssl_profile(name, bigip)

    def _remove_ssl_profile(self, name, bigip):
        """Deletes profile.

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
            LOG.warn(
                "Unable to delete profile %s. "
                "Response message: %s." % (name, err.message))

    def _remove_profile(self, vip, profile_name, bigip):
        """Deletes profile.

        :param vip: Dictionary which contains name and partition of
        virtual server.
        :param profile_name: Name of profile to delete.
        :param bigip: Single BigIP instances to update.
        """
        try:
            v = bigip.tm.ltm.virtuals.virtual
            obj = v.load(name=vip["name"], partition=vip["partition"])
            p = obj.profiles_s
            profiles = p.get_collection()

            # see if profile exists
            for profile in profiles:
                if profile.name == profile_name:
                    pr = p.profiles.load(name=profile_name, partition='Common')
                    pr.delete()
                    LOG.debug("Deleted profile %s" % profile.name)
                    return
        except Exception as err:
            # Not necessarily an error -- profile might be referenced
            # by another virtual server.
            LOG.warn(
                "Unable to delete profile %s. "
                "Response message: %s." % (profile_name, err.message))

    def _remove_cookie_persist_rule(self, vip, bigip):
        """Deletes cookie persist rule.

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
