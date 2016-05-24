# coding=utf-8
# Copyright 2016 F5 Networks Inc.
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
import shutil
import tempfile

from oslo_log import log as logging
from requests import HTTPError

LOG = logging.getLogger(__name__)


class SSLProfileHelper(object):

    @staticmethod
    def create_client_ssl_profile(bigip, name, cert, key):
        uploader = bigip.shared.file_transfer.uploads
        cert_registrar = bigip.tm.sys.crypto.certs
        key_registrar = bigip.tm.sys.crypto.keys
        ssl_client_profile = bigip.tm.ltm.profile.client_ssls.client_ssl

        certfilename = name + '.crt'
        keyfilename = name + '.key'
        tls_dir = tempfile.mkdtemp()

        # write certificate to temp file
        certpath = os.path.join(tls_dir, certfilename)
        f = open(certpath, "w")
        f.write(cert)
        f.close()

        # write key to temp file
        keypath = os.path.join(tls_dir, keyfilename)
        f = open(keypath, "w")
        f.write(key)
        f.close()

        # upload files to BIG-IP
        try:
            uploader.upload_file(str(certpath))
            uploader.upload_file(str(keypath))

            # create BIG-IP cert objects
            cert_registrar.install_cert(certfilename)
            key_registrar.install_key(certfilename, keyfilename)

            # create ssl-client profile
            chain = [{'name': name,
                      'cert': '/Common/' + certfilename,
                      'key': '/Common/' + keyfilename}]
            ssl_client_profile.create(name=name, certKeyChain=chain)
        except HTTPError as err:
            LOG.error("Error uploading cert/key %s"
                      "Repsponse status code: %s. Response "
                      "message: %s." % (certpath,
                                        err.response.status_code,
                                        err.message))
            raise err
        finally:
            shutil.rmtree(tls_dir)
