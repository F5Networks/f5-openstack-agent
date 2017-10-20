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

#import pdb

from oslo_log import log as logging

from neutron.plugins.common import constants as plugin_const

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import ssl_profile
from neutron_lbaas.services.loadbalancer import constants as lb_const
from requests import HTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip import utils

LOG = logging.getLogger(__name__)


class ListenerServiceBuilder(object):
    u"""Create LBaaS v2 Listener on BIG-IPs.

    Handles requests to create, update, delete LBaaS v2 listener
    objects on one or more BIG-IP systems. Maps LBaaS listener
    defined in service object to a BIG-IP virtual server.
    """

    def __init__(self, lbaas_builder, service_adapter, cert_manager, parent_ssl_profile=None):

        self.lbaas_builder = lbaas_builder
        self.cert_manager = cert_manager
        self.parent_ssl_profile = parent_ssl_profile
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.service_adapter = service_adapter
        LOG.debug("ListenerServiceBuilder: using parent_ssl_profile %s ",
                  parent_ssl_profile)


    def create_listener(self, service, bigips):
        u"""Create listener on set of BIG-IPs.

        Create a BIG-IP virtual server to represent an LBaaS
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
                    LOG.debug("Virtual server already exists updating")
                    try:
                        self.update_listener(service, bigips)
                        #self.vs_helper.update(bigip, vip)
                    except Exception as e:
                        LOG.warn("Update triggered in create failed, this could be due to timing issues in assure_service")
                        LOG.warn('VS info %s',service['listener'])
                        LOG.exception(e)
                        LOG.warn('Exception %s',e)
                        raise e

                else:
                    LOG.exception("Virtual server creation error: %s" %
                                  err.message)
                    raise
            if tls:
                #pdb.set_trace()
                self.add_ssl_profile(tls, bigip)

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

        for bigip in bigips:
            self.vs_helper.delete(bigip,
                                  name=vip["name"],
                                  partition=vip["partition"])

            # delete ssl profiles
            self.remove_ssl_profiles(tls, bigip)

    def add_ssl_profile(self, tls, bigip, add_to_vip=True):
        # add profile to virtual server
        vip = {'name': tls['name'],
               'partition': tls['partition']}

        if "default_tls_container_id" in tls:
            container_ref = tls["default_tls_container_id"]
            self.create_ssl_profile(
                container_ref, bigip, vip, True, add_to_vip)

        if "sni_containers" in tls and tls["sni_containers"]:
            for container in tls["sni_containers"]:
                container_ref = container["tls_container_id"]
                self.create_ssl_profile(container_ref, bigip, vip, False, add_to_vip)


    def create_ssl_profile(self, container_ref, bigip, vip, sni_default=False, add_to_vip=True):
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
                sni_default=True,
                parent_profile=self.parent_ssl_profile)

            # upload cert/key and create SSL profile
            ssl_profile.SSLProfileHelper.create_client_ssl_profile(
                bigip,
                name + '_NotDefault',
                cert,
                key,
                sni_default=False,
                parent_profile=self.parent_ssl_profile)
        finally:
            del cert
            del key

        # add ssl profile to virtual server
        if add_to_vip:
            f5name = name
            if not sni_default:
                f5name += '_NotDefault'
            self._add_profile(vip, f5name, bigip, context='clientside')

    def update_listener(self, service, bigips):
        u"""Update Listener from a single BIG-IP system.

        Updates virtual servers that represents a Listener object.

        :param service: Dictionary which contains a both a listener
        and load balancer definition.
        :param bigips: Array of BigIP class instances to update.
        """

        u"""
        ATTENTION: The hole impl. is a hack.
        For ssl profile settings the order is very important:
        1. A new ssl profile is created but not applied to the listener
        2. The esd_apply configures the listener with the new profile (so the old one will be detached)
        3. The update will apply the changes to the listener
        4. The remove_ssl is than be able to remove unneeded ssl profiles because they got detached in 3.
        """

        # check for ssl client cert changes
        old_default = None
        old_sni_containers = None
        new_default = None
        new_sni_containers = None
        vip = self.service_adapter.get_virtual(service)
        old_listener = service.get('old_listener')

        #pdb.set_trace()

        if old_listener != None:
            listener = service.get('listener')
            if old_listener.get('default_tls_container_id') != listener.get('default_tls_container_id'):
                old_default = old_listener.get('default_tls_container_id')
                new_default = listener.get('default_tls_container_id')

            # determine sni delta with set substraction
            old_snis = old_listener.get('sni_containers')
            new_snis = listener.get('sni_containers')
            old_ids = []
            new_ids = []
            for old in old_snis:
                old_ids.append(old.get('tls_container_id'))
            for new in new_snis:
                new_ids.append(new.get('tls_container_id'))
            new_sni_containers = self._make_sni_tls(vip, list(set(new_ids) - set(old_ids)))
            old_sni_containers = self._make_sni_tls(vip, list(set(old_ids) - set(new_ids)))

        # create old and new tls listener configurations
        # create new ssl-profiles on F5 BUT DO NOT APPLY them to listener
        old_tls = None
        if (new_default != None or (new_sni_containers != None and new_sni_containers['sni_containers'])):
            new_tls = self.service_adapter.get_tls(service)
            new_tls = self._make_default_tls(vip, new_tls.get('default_tls_container_id'))

            if old_default != None:
                old_tls = self._make_default_tls(vip, old_default)

            for bigip in bigips:
                # create ssl profile but do not apply
                if new_tls != None:
                    try:
                        self.add_ssl_profile(new_tls, bigip, False)
                    except:
                        pass
                if new_sni_containers != None and new_sni_containers['sni_containers']:
                    try:
                        self.add_ssl_profile(new_sni_containers, bigip, False)
                    except:
                        pass


        # process esd's AND create new client ssl config for listener
        vip = self.apply_esds(service)

        # apply changes to listener AND remove not needed ssl profiles on F5
        network_id = service['loadbalancer']['network_id']
        for bigip in bigips:
            self.service_adapter.get_vlan(vip, bigip, network_id)
            self.vs_helper.update(bigip, vip)
            # delete ssl profiles
            if old_tls != None:
                try:
                    self.remove_ssl_profiles(old_tls, bigip)
                except:
                    pass
            if old_sni_containers != None and old_sni_containers['sni_containers']:
                try:
                    self.remove_ssl_profiles(old_sni_containers, bigip)
                except:
                    pass


    def _make_default_tls(self, vip, id):
        return {'name': vip['name'], 'partition': vip['partition'], 'default_tls_container_id': id}

    def _make_sni_tls(self, vip, ids):
        containers = {'name': vip['name'], 'partition': vip['partition'], 'sni_containers': []}
        for id in ids:
            containers['sni_containers'].append({'tls_container_id': id})
        return containers

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
                # if persistence_type != 'SOURCE_IP':
                #     #if listener['protocol'] == 'TCP':
                #         #self._remove_profile(vip, 'fastL4', bigip)
                #
                #     # Add default profiles
                #
                #     profiles = utils.get_default_profiles(self.service_adapter.conf, listener['protocol'])
                #
                #
                #     for profile in profiles.values():
                #         self._add_profile(vip, profile.get('name'), bigip)


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

    def _cc_create_app_cookie_persist_rule(self, cookiename):
        """Create cookie persistence rule.

        :param cookiename: Name to substitute in rule.
        """
        rule_text = """
             when RULE_INIT {
             
                # Cookie name prefix
                set static::ck_pattern BIGipServer*, %s
             
                # Log debug to /var/log/ltm? 1=yes, 0=no)
                set static::ck_debug 1
             
                # Cookie encryption passphrase
                # Change this to a custom string!
                set static::ck_pass "abc123"
            }
            when HTTP_REQUEST {
             
                if {$static::ck_debug}{log local0. "Request cookie names: [HTTP::cookie names]"}
                
                # Check if the cookie names in the request match our string glob pattern
                if {[set cookie_names [lsearch -all -inline [HTTP::cookie names] $static::ck_pattern]] ne ""}{
             
                    # We have at least one match so loop through the cookie(s) by name
                    if {$static::ck_debug}{log local0. "Matching cookie names: [HTTP::cookie names]"}
                        foreach cookie_name $cookie_names {
                            
                            # Decrypt the cookie value and check if the decryption failed (null return value)
                            if {[HTTP::cookie decrypt $cookie_name $static::ck_pass] eq ""}{
                 
                                # Cookie wasn't encrypted, delete it
                                if {$static::ck_debug}{log local0. "Removing cookie as decryption failed for $cookie_name"}
                                    HTTP::cookie remove $cookie_name
                            }
                        }
                    if {$static::ck_debug}{log local0. "Cookie header(s): [HTTP::header values Cookie]"}
                }
            }
            when HTTP_RESPONSE {
             
                if {$static::ck_debug}{log local0. "Response cookie names: [HTTP::cookie names]"}
                
                # Check if the cookie names in the request match our string glob pattern
                if {[set cookie_names [lsearch -all -inline [HTTP::cookie names] $static::ck_pattern]] ne ""}{
                    
                    # We have at least one match so loop through the cookie(s) by name
                    if {$static::ck_debug}{log local0. "Matching cookie names: [HTTP::cookie names]"}
                        foreach cookie_name $cookie_names {
                            
                            # Encrypt the cookie value
                            HTTP::cookie encrypt $cookie_name $static::ck_pass
                        }
                    if {$static::ck_debug}{log local0. "Set-Cookie header(s): [HTTP::header values Set-Cookie]"}
                }
            }       
        """ % (cookiename)
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
            self._remove_ssl_profile(name + '_NotDefault', bigip)


        if "sni_containers" in tls and tls["sni_containers"]:
            for container in tls["sni_containers"]:
                container_ref = container["tls_container_id"]
                i = container_ref.rindex("/") + 1
                name = self.service_adapter.prefix + container_ref[i:]
                self._remove_ssl_profile(name, bigip)
                self._remove_ssl_profile(name + '_NotDefault', bigip)

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

    def apply_esds(self, service):


        listener = service['listener']

        l7policies = listener.get('l7_policies')

        if l7policies is None:
            return

        fastl4 = {'partition':'Common','name':'fastL4','context':'all'}
        stcp_profiles = []
        ctcp_profiles = []
        cssl_profiles = []
        sssl_profiles = []
        http_profile = {}
        oneconnect_profile = {}
        compression_profile = {}
        persistence_profiles = []

        policies = []
        irules = []
        # get virtual server name

        update_attrs = self.service_adapter.get_virtual(service)

        # get ssl certificates for listener
        tls = self.service_adapter.get_tls(service)
        # initialize client ssl profile with already existing certificates
        if bool(tls):
            if "default_tls_container_id" in tls:
                container_ref = tls["default_tls_container_id"]
                def_name = self.cert_manager.get_name(container_ref,
                                                  self.service_adapter.prefix)
                cssl_profiles.append({'name': def_name,
                                      'partition': 'Common',
                                      'context': 'clientside'})

            if "sni_containers" in tls and tls["sni_containers"]:
                for container in tls["sni_containers"]:
                    if 'tls_container_id' in container:
                        sni_ref = container['tls_container_id']
                        sni_name = self.cert_manager.get_name(sni_ref,
                                                              self.service_adapter.prefix) + '_NotDefault'
                        cssl_profiles.append({'name': sni_name,
                                              'partition': 'Common',
                                              'context': 'clientside'})


        for l7policy in l7policies:
            name = l7policy.get('name', None)
            if name and self.lbaas_builder.is_esd(name) and l7policy.get('provisioning_status')!= plugin_const.PENDING_DELETE:
                esd = self.lbaas_builder.get_esd(name)
                if esd is not None:

                    # start with server tcp profile, only add if not already got some
                    ctcp_context = 'all'

                    if 'lbaas_fastl4' in esd:
                        if esd['lbaas_fastl4']=='':
                            fastl4= {}

                    if len(stcp_profiles)==0:
                        if 'lbaas_stcp' in esd:
                            # set serverside tcp profile
                            stcp_profiles.append({'name': esd['lbaas_stcp'],
                                             'partition': 'Common',
                                             'context': 'serverside'})
                            # restrict client profile
                            ctcp_context = 'clientside'

                    if len(ctcp_profiles)==0:
                        # must define client profile; default to tcp if not in ESD
                        if 'lbaas_ctcp' in esd:
                            ctcp_profile = esd['lbaas_ctcp']
                        else:
                            ctcp_profile = 'tcp'
                        ctcp_profiles.append({'name':  ctcp_profile,
                                         'partition': 'Common',
                                         'context': ctcp_context})
                    # http profiles
                    if 'lbaas_http' in esd and not bool(http_profile):
                        if esd['lbaas_http'] == '':
                            http_profile = {}
                        else:
                            http_profile = {'name':  esd['lbaas_http'],
                                             'partition': 'Common',
                                             'context': 'all'}

                    # one connect profiles
                    if 'lbaas_one_connect' in esd and not bool(oneconnect_profile) :
                        if esd['lbaas_one_connect'] == '':
                            oneconnect_profile = {}
                        else:
                            oneconnect_profile = {'name':  esd['lbaas_one_connect'],
                                             'partition': 'Common',
                                             'context': 'all'}

                    # http compression profiles
                    if 'lbaas_http_compression' in esd and not bool(compression_profile):
                        if esd['lbaas_http_compression'] == '':
                            compression_profile = {}
                        else:
                            compression_profile = {'name':  esd['lbaas_http_compression'],
                                             'partition': 'Common',
                                             'context': 'all'}

                    # SSL profiles
                    if 'lbaas_cssl_profile' in esd:
                        cssl_profiles.append({'name': esd['lbaas_cssl_profile'],
                                         'partition': 'Common',
                                         'context': 'clientside'})
                    if 'lbaas_sssl_profile' in esd:
                        sssl_profiles.append({'name': esd['lbaas_sssl_profile'],
                                         'partition': 'Common',
                                         'context': 'serverside'})

                    # persistence
                    if 'lbaas_persist' in esd:
                        update_attrs['persist'] = [{'name': esd['lbaas_persist']}]
                    if 'lbaas_fallback_persist' in esd:
                        update_attrs['fallbackPersistence'] = esd['lbaas_fallback_persist']

                    # iRules
                    if 'lbaas_irule' in esd:
                        for irule in esd['lbaas_irule']:
                            irules.append('/Common/' + irule)

                    # L7 policies
                    if 'lbaas_policy' in esd:
                        for policy in esd['lbaas_policy']:
                            policies.append({'name': policy, 'partition': 'Common'})

        profiles=[]

        if listener['protocol'] == lb_const.PROTOCOL_TCP:
            if bool(fastl4):
                profiles.append(fastl4)
            else:
                profiles = stcp_profiles + ctcp_profiles
        else:
            default_profiles = utils.get_default_profiles(self.service_adapter.conf, listener['protocol'])

        if bool(http_profile):
            profiles.append(http_profile)
        else:
            if listener['protocol'] != lb_const.PROTOCOL_TCP:
                profiles.append( default_profiles['http'])

        if bool(cssl_profiles):
            for cssl_profile in cssl_profiles:
                profiles.append(cssl_profile)

        if bool(oneconnect_profile):
            profiles.append(oneconnect_profile)
        else:
            if listener['protocol'] != lb_const.PROTOCOL_TCP:
                profiles.append(default_profiles['oneconnect'])

        if bool(compression_profile):
            profiles.append(compression_profile)

        if profiles:
            update_attrs['profiles'] = profiles

        update_attrs['rules'] = update_attrs.get('rules',[])+irules

        update_attrs['policies'] = update_attrs.get('policies',[])+policies

        return update_attrs
