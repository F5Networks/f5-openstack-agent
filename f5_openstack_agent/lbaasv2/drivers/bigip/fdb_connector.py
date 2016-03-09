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


class FDBConnector(object):
    # Abstract base class for interfacing with an external
    # forwarding database

    def __init__(self, conf):
        self.conf = conf

    def notify_vtep_added(self, network, vtep_ip_address):
        # Advertise local VTEP IP address in fdb.
        raise NotImplementedError()

    def notify_vtep_removed(self, network, vtep_ip_address):
        # Remove local VTEP IP address in fdb.
        raise NotImplementedError()

    def advertise_tunnel_ips(self, tunnel_ips):
        # Advertise tunnel IP address in fdb.
        raise NotImplementedError()
