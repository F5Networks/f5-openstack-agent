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


class CertManagerBase(object):
    """Base class for custom implementations to get certs/keys."""

    def get_certificate(self, ref):
        """Retrieves certificate from certificate manager.

        :param string ref: Reference to certificate stored in a certificate
        manager.
        :returns string: Certificate data.
        """
        raise NotImplementedError()

    def get_private_key(self, ref):
        """Retrieves key from certificate manager.

        :param string ref: Reference to key stored in a certificate manager.
        :returns string: Key data.
        """
        raise NotImplementedError()

    def get_name(self, ref, prefix):
        """Returns a name that uniquely identifies cert/key pair.

        :param string ref: Reference to certificate/key container stored in a
        certificate manager.
        :param string prefix: The environment prefix. Can be optionally
        used to add name.
        :returns string: Unique name for cert/key pair.
        """
        raise NotImplementedError()
