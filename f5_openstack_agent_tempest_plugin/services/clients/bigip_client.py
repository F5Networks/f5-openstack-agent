#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from f5.bigip import BigIP


class BigIPClient(object):
    """Client to verify BigIP configuration."""

    def __init__(self, hostname, username, password):
        """Initialize the Big IP client object."""
        self._bigip = BigIP(hostname=hostname,
                            username=username,
                            password=password)

    def verify_loadbalancer(self, loadbalancer):
        """Verify that the loadbalancer exists for the given tenant."""
        pass
