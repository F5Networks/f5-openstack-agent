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

import os
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class SSLProfileError(Exception):
    pass


class SSLProfileHelper(object):

    @staticmethod
    def create_client_ssl_profile(bigip, name, cert, key, **kwargs):
        key_passphrase = kwargs.get("key_passphrase", None)
        sni_default = kwargs.get("sni_default", False)
        intermediates = kwargs.get("intermediates", None)
        parent_profile = kwargs.get("parent_profile", None)
        profile_name = kwargs.get("profile_name", None)
        if not profile_name:
            profile_name = name

        peerCertMode = "ignore"
        client_auth = kwargs.get("client_auth", False)
        if client_auth:
            peerCertMode = "require"

        client_ca_cert = kwargs.get("client_ca_cert", None)
        ca_cert_filename = kwargs.get("ca_cert_filename", None)

        ciphers = "DEFAULT"
        tm_options = ["dont-insert-empty-fragments", "no-tlsv1.3"]
        tls_protocols = kwargs.get("tls_protocols", None)
        cipher_suites = kwargs.get("cipher_suites", None)
        if tls_protocols:
            protocols = tls_protocols.split(",")
            protocol_map = {
                "TLS1.0": "no-tlsv1",
                "TLS1.1": "no-tlsv1.1",
                "TLS1.2": "no-tlsv1.2",
                "TLS1.3": "no-tlsv1.3"
            }
            for protocol in protocols:
                protocol_map.pop(protocol, None)
            if len(protocol_map.keys()) < 4:
                # Convert valid tls_protocols input to tm_options, and also
                # configure ciphers of client ssl profile. Otherwise, use
                # bigip default value.
                tm_options = ["dont-insert-empty-fragments"] + \
                             protocol_map.values()
                if cipher_suites:
                    ciphers = cipher_suites

        uploader = bigip.shared.file_transfer.uploads
        cert_registrar = bigip.tm.sys.crypto.certs
        key_registrar = bigip.tm.sys.crypto.keys
        ssl_client_profile = bigip.tm.ltm.profile.client_ssls.client_ssl

        # Check that parent profile exists; use default if not.
        if parent_profile and not ssl_client_profile.exists(
                name=parent_profile, partition='Common'):
            parent_profile = None

        certfilename = name + '.crt'
        interfilename = name + '_inter' + '.crt' if intermediates else None
        keyfilename = name + '.key'

        try:
            chain_path = None
            if interfilename:
                # import chains
                uploader.upload_bytes(intermediates, interfilename)

                param_set = {}
                param_set['name'] = interfilename
                param_set['from-local-file'] = os.path.join(
                    '/var/config/rest/downloads/', interfilename)
                cert_registrar.exec_cmd('install', **param_set)

                chain_path = '/Common/' + interfilename

            # In-memory upload -- data not written to local file system but
            # is saved as a file on the BIG-IP.
            uploader.upload_bytes(cert, certfilename)
            uploader.upload_bytes(key, keyfilename)

            # import certificate
            param_set = {}
            param_set['name'] = certfilename
            param_set['from-local-file'] = os.path.join(
                '/var/config/rest/downloads/', certfilename)
            cert_registrar.exec_cmd('install', **param_set)

            # import key
            param_set['name'] = keyfilename
            param_set['from-local-file'] = os.path.join(
                '/var/config/rest/downloads/', keyfilename)
            key_registrar.exec_cmd('install', **param_set)

            if client_ca_cert:
                uploader.upload_bytes(client_ca_cert, ca_cert_filename)
                # import certificate
                param_set = {}
                param_set['name'] = ca_cert_filename
                param_set['from-local-file'] = os.path.join(
                    '/var/config/rest/downloads/', ca_cert_filename)
                cert_registrar.exec_cmd('install', **param_set)
                ca_cert_filename = '/Common/' + ca_cert_filename

            # create ssl-client profile from cert/key pair
            chain = [{'name': name,
                      'cert': '/Common/' + certfilename,
                      'chain': chain_path,
                      'key': '/Common/' + keyfilename,
                      'passphrase': key_passphrase}]

            if ssl_client_profile.exists(name=profile_name,
                                         partition='Common'):
                profile = ssl_client_profile.load(name=profile_name,
                                                  partition='Common')
                # BIG-IP v14 or higher version support to modify client
                # authentication settings individually.
                # See https://cdn.f5.com/product/bugtracker/ID674106.html
                profile.modify(certKeyChain=chain,
                               sniDefault=sni_default,
                               peerCertMode=peerCertMode,
                               caFile=ca_cert_filename,
                               tmOptions=tm_options,
                               ciphers=ciphers,
                               defaultsFrom=parent_profile)
            else:
                ssl_client_profile.create(name=profile_name,
                                          partition='Common',
                                          certKeyChain=chain,
                                          sniDefault=sni_default,
                                          peerCertMode=peerCertMode,
                                          caFile=ca_cert_filename,
                                          tmOptions=tm_options,
                                          ciphers=ciphers,
                                          defaultsFrom=parent_profile)
        except Exception as err:
            LOG.error("Error creating SSL profile: %s" % err.message)
            raise SSLProfileError(err.message)

    @staticmethod
    def get_client_ssl_profile_count(bigip):
        return len(
            bigip.tm.ltm.profile.client_ssls.get_collection(
                partition='Common'))
