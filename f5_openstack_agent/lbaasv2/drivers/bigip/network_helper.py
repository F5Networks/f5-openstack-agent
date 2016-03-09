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

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class NetworkHelper(object):
    def create_l2gre_multipoint_profile(self, bigip, name, folder):
        pass

    def create_vxlan_multipoint_profile(self, bigip, name, folder):
        pass

    def get_l2gre_tunnel_key(self, bigip, name, folder):
        pass

    def get_vlan_id(self, bigip, name, folder):
        pass

    def get_vxlan_tunnel_key(self, bigip, name, folder):
        pass

    def get_selfip_addr(self, bigip, vtep_selfip_name, vtep_folder):
        pass

    def get_selfips(self, bigip, folder, vlan):
        pass

    def delete_selfip(self, bigip, name, folder):
        pass

    def route_domain_exists(self, bigip, folder_name, domain_id=None):
        # need route-domain support
        # route = bigip.net.route-domains.route-domain
        # route_name = '~' + folder_name + '~'
        # if domain_id:
        #    route_name += folder_name + '_aux_' + str(domain_id)
        # return route.exists(name=route_name)
        return True

    def get_route_domain(self, bigip, folder):
        pass

    def create_route_domain(self, bigip, folder_name, strictness=None):
        pass

    def delete_route_domain(self, bigip, folder_name, domain_name):
        pass

    def get_route_domain_ids(self, bigip, folder):
        pass

    def get_route_domain_names(self, bigip, folder):
        pass

    def get_vlans_in_route_domain_by_id(self, bigip, folder, route_domain_id):
        pass

    def arp_delete_by_subnet(self, bigip, subnet=None, mask=None, folder=None):
        pass
