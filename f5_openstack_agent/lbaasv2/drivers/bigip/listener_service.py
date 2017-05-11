# coding=utf-8
# Copyright 2014-2017 F5 Networks Inc.
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
from neutron_lbaas.services.loadbalancer import constants as lb_const
from requests import HTTPError

LOG = logging.getLogger(__name__)


class ListenerServiceBuilder(object):
    u"""Create LBaaS v2 Listener on BIG-IP®s.

    Handles requests to create, update, delete LBaaS v2 listener
    objects on one or more BIG-IP® systems. Maps LBaaS listener
    defined in service object to a BIG-IP® virtual server.
    """

    def __init__(self, service_adapter, cert_manager, parent_ssl_profile=None):
        self.cert_manager = cert_manager
        self.parent_ssl_profile = parent_ssl_profile
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.service_adapter = service_adapter
        LOG.debug("ListenerServiceBuilder: using parent_ssl_profile %s ",
                  parent_ssl_profile)

    def create_listener(self, service, bigips):
        u"""Create listener on set of BIG-IP®s.

        Create a BIG-IP® virtual server to represent an LBaaS
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

        network_id = service['loadbalancer']['network_id']
        for bigip in bigips:
            self.service_adapter.get_vlan(vip, bigip, network_id)
            try:
                self.vs_helper.create(bigip, vip)
            except HTTPError as err:
                if err.response.status_code == 409:
                    LOG.debug("Virtual server already exists")
                else:
                    LOG.exception("Virtual server creation error: %s" %
                                  err.message)
                    raise
            if tls:
                self.add_ssl_profile(tls, bigip)

    def get_listener(self, service, bigip):
        u"""Retrieve BIG-IP® virtual from a single BIG-IP® system.

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
        u"""Delete Listener from a set of BIG-IP® systems.

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
        u"""Update Listener from a single BIG-IP® system.

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
        if vip:
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
            listener = service['listener']
            for bigip in bigips:
                # For TCP listeners, must remove fastL4 profile before adding
                # adding http/oneconnect profiles.
                if persistence_type != 'SOURCE_IP':
                    if listener['protocol'] == 'TCP':
                        self._remove_profile(vip, 'fastL4', bigip)

                    # HTTP listeners should have http and oneconnect profiles
                    self._add_profile(vip, 'http', bigip)
                    self._add_profile(vip, 'oneconnect', bigip)

                if persistence_type == 'APP_COOKIE' and \
                        'cookie_name' in persistence:
                    self._add_cookie_persist_rule(vip, persistence, bigip)

                # profiles must be added before setting persistence
                self.vs_helper.update(bigip, vip_persist)
                LOG.debug("Set persist %s" % vip["name"])
        else:
            self.remove_session_persistence(service, bigips)

    def _add_profile(self, vip, profile_name, bigip, context='all'):
        """Add profile to virtual server instance. Assumes Common.

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
        """Add cookie persist rules to virtual server instance.

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

    def remove_session_persistence(self, service, bigips):
        """Resest persistence for virtual server instance.

        Clears persistence and deletes profiles.

        :param service: Dictionary which contains a listener, pool
        and load balancer definition.
        :param bigips: Single BigIP instances to update.
        """

        vip = self.service_adapter.get_virtual_name(service)
        vip["persist"] = []
        vip["fallbackPersistence"] = ""

        listener = service["listener"]
        if listener['protocol'] == 'TCP':
            # Revert VS back to fastL4. Must do an update to replace
            # profiles instead of using add/remove profile. Leave http
            # profiles in place for non-TCP listeners.
            vip['profiles'] = ['/Common/fastL4']

        for bigip in bigips:
            # Check for custom app_cookie profile.
            has_app_cookie = False
            vs = self.vs_helper.load(bigip, vip['name'], vip['partition'])
            persistence = getattr(vs, 'persist', None)
            if persistence:
                persist_name = persistence[0].get('name', '')
                if persist_name:
                    has_app_cookie = persist_name.lower().\
                        startswith('app_cookie')

                self.vs_helper.update(bigip, vip)
                LOG.debug("Cleared session persistence for %s" % vip["name"])

                if has_app_cookie:
                    # Delete app_cookie profile. Other persist types have
                    # Common profiles and remain in place.
                    self._remove_cookie_persist_rule(vip, bigip)

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
            LOG.warn(
                "Unable to delete profile %s. "
                "Response message: %s." % (name, err.message))

    def _remove_profile(self, vip, profile_name, bigip):
        """Delete profile.

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

    def _add_policy(self, vs, policy_name, bigip):
        vs_name = vs['name']
        vs_partition = vs['partition']
        policy_partition = 'Common'

        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name,
                     partition=vs_partition)
        p = obj.policies_s
        policies = p.get_collection()

        # see if policy already added to virtual server
        for policy in policies:
            if policy.name == policy_name:
                LOG.debug("L7Policy found. Not adding.")
                return

        try:
            # not found -- add policy to virtual server
            p.policies.create(name=policy_name,
                              partition=policy_partition)
        except Exception as exc:
            # Bug in TMOS 12.1 will return a 404 error, but the request
            # succeeded. Verify that policy was added, and ignore exception.
            LOG.debug(exc.message)
            if not p.policies.exists(name=policy_name,
                                     partition=policy_partition):
                # really failed, raise original exception
                raise

        # success
        LOG.debug("Added L7 policy {0} for virtual sever {1}".format(
            policy_name, vs_name))

    def _remove_policy(self, vs, policy_name, bigip):
        vs_name = vs['name']
        vs_partition = vs['partition']
        policy_partition = 'Common'

        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name,
                     partition=vs_partition)
        p = obj.policies_s
        policies = p.get_collection()

        # find policy and remove from virtual server
        for policy in policies:
            if policy.name == policy_name:
                l7 = p.policies.load(name=policy_name,
                                     partition=policy_partition)
                l7.delete()
                LOG.debug("Removed L7 policy {0} for virtual sever {1}".
                          format(policy_name, vs_name))

    def _add_irule(self, vs, irule_name, bigip, rule_partition='Common'):
        vs_name = vs['name']
        vs_partition = vs['partition']

        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name,
                     partition=vs_partition)
        r = obj.rules
        rules = r.get_collection()

        # see if iRule already added to virtual server
        for rule in rules:
            if rule.name == irule_name:
                LOG.debug("iRule found. Not adding.")
                return

        try:
            # not found -- add policy to virtual server
            r.rules.create(name=irule_name,
                           partition=rule_partition)
        except Exception as exc:
            # Bug in TMOS 12.1 will return a 404 error, but the request
            # succeeded. Verify that policy was added, and ignore exception.
            LOG.debug(exc.message)
            if not r.rule.exists(name=irule_name,
                                 partition=rule_partition):
                # really failed, raise original exception
                raise

        # success
        LOG.debug("Added iRule {0} for virtual sever {1}".format(
            irule_name, vs_name))

    def _remove_irule(self, vs, irule_name, bigip, rule_partition='Common'):
        vs_name = vs['name']
        vs_partition = vs['partition']

        v = bigip.tm.ltm.virtuals.virtual
        obj = v.load(name=vs_name,
                     partition=vs_partition)
        r = obj.rules_s
        rules = r.get_collection()

        # find iRule and remove from virtual server
        for rule in rules:
            if rule.name == irule_name:
                irule = r.rules.load(name=irule_name,
                                     partition=rule_partition)
                irule.delete()
                LOG.debug("Removed iRule {0} for virtual sever {1}".
                          format(irule_name, vs_name))

    def apply_esd(self, svc, esd, bigips):
        profiles = []

        # get virtual server name
        update_attrs = self.service_adapter.get_virtual_name(svc)

        # start with server tcp profile
        if 'lbaas_stcp' in esd:
            # set serverside tcp profile
            profiles.append({'name': esd['lbaas_stcp'],
                             'partition': 'Common',
                             'context': 'serverside'})
            # restrict client profile
            ctcp_context = 'clientside'
        else:
            # no serverside profile; use client profile for both
            ctcp_context = 'all'

        # must define client profile; default to tcp if not in ESD
        if 'lbaas_ctcp' in esd:
            ctcp_profile = esd['lbaas_ctcp']
        else:
            ctcp_profile = 'tcp'
        profiles.append({'name':  ctcp_profile,
                         'partition': 'Common',
                         'context': ctcp_context})

        # SSL profiles
        if 'lbaas_cssl_profile' in esd:
            profiles.append({'name': esd['lbaas_cssl_profile'],
                             'partition': 'Common',
                             'context': 'clientside'})
        if 'lbaas_sssl_profile' in esd:
            profiles.append({'name': esd['lbaas_sssl_profile'],
                             'partition': 'Common',
                             'context': 'serverside'})

        # persistence
        if 'lbaas_persist' in esd:
            update_attrs['persist'] = [{'name': esd['lbaas_persist']}]
        if 'lbaas_fallback_persist' in esd:
            update_attrs['fallbackPersistence'] = esd['lbaas_fallback_persist']

        if profiles:
            # always use http and oneconnect
            profiles.append({'name': 'http',
                             'partition': 'Common',
                             'context': 'all'})
            profiles.append({'name': 'oneconnect',
                             'partition': 'Common',
                             'context': 'all'})
            update_attrs['profiles'] = profiles

        # iRules
        if 'lbaas_irule' in esd:
            irules = []
            for irule in esd['lbaas_irule']:
                irules.append('/Common/' + irule)
            update_attrs['rules'] = irules

        # L7 policies
        if 'lbaas_policy' in esd:
            policies = []
            for policy in esd['lbaas_policy']:
                policies.append({'name': policy, 'partition': 'Common'})
            update_attrs['policies'] = policies

        # udpate BIG-IPs
        for bigip in bigips:
            self.vs_helper.update(bigip, update_attrs)

    def remove_esd(self, svc, esd, bigips):
        # original service object definition of listener
        vs = self.service_adapter.get_virtual(svc)

        # add back SSL profile for TLS?
        tls = self.service_adapter.get_tls(svc)
        if tls:
            tls['name'] = vs['name']
            tls['partition'] = vs['partition']

        # remove iRules
        if 'lbaas_irule' in esd:
            vs['rules'] = []

        # remove policies
        if 'lbaas_policy' in esd:
            vs['policies'] = []

        # reset persistence to original definition
        if 'pool' in svc:
            vip_persist = self.service_adapter.get_session_persistence(svc)
            vs.update(vip_persist)

        for bigip in bigips:
            try:
                # update VS back to original listener definition
                self.vs_helper.update(bigip, vs)

                # add back SSL profile for TLS
                if tls:
                    self.add_ssl_profile(tls, bigip)
            except Exception as err:
                LOG.exception("Virtual server update error: %s" % err.message)
                raise
