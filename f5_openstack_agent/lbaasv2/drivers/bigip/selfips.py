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

import netaddr
from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType
from requests import HTTPError

LOG = logging.getLogger(__name__)


class BigipSelfIpManager(object):

    def __init__(self, driver, l2_service, l3_binding):
        self.driver = driver
        self.l2_service = l2_service
        self.l3_binding = l3_binding
        self.selfip_manager = BigIPResourceHelper(ResourceType.selfip)
        self.network_helper = NetworkHelper()

    def create_bigip_selfip(self, bigip, model):
        if not model['name']:
            return False
        s = bigip.net.selfips.selfip
        if s.exists(name=model['name'], partition=model['partition']):
            return True
        try:
            self.selfip_manager.create(bigip, model)
        except HTTPError as err:
            if err.response.status_code is not 400:
                raise
            if err.response.text.find("must be one of the vlans "
                                      "in the associated route domain") > 0:
                self.network_helper.add_vlan_to_domain(
                    name=model['vlan_name'], partition=model['partition'])
                self.selfip_manager.create(bigip, model)

    def assure_bigip_selfip(self, bigip, service, subnetinfo):

        network = subnetinfo['network']
        if not network:
            LOG.error('Attempted to create selfip and snats '
                      'for network with no id... skipping.')
            return
        subnet = subnetinfo['subnet']

        tenant_id = service['pool']['tenant_id']
        # If we have already assured this subnet.. return.
        # Note this cache is periodically cleared in order to
        # force assurance that the configuration is present.
        if tenant_id in bigip.assured_tenant_snat_subnets and \
                subnet['id'] in bigip.assured_tenant_snat_subnets[tenant_id]:
            return

        selfip_address = self._get_bigip_selfip_address(bigip, subnet)
        selfip_address += '%' + str(network['route_domain_id'])

        if self.l2_service.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = service['pool']['tenant_id']

        (network_name, preserve_network_name) = \
            self.l2_service.get_network_name(bigip, network)

        model = {
            "name": "local-" + bigip.device_name + "-" + subnet['id'],
            "ip_address": selfip_address,
            "netmask": netaddr.IPNetwork(subnet['cidr']).netmask,
            "vlan_name": network_name,
            "floating": "False",
            "partition": network_folder,
            "preserve_vlan_name": preserve_network_name
        }
        self.create(bigip, model)
        # TO DO: we need to only bind the local SelfIP to the
        # local device... not treat it as if it was floating
        if self.l3_binding:
            self.l3_binding.bind_address(subnet_id=subnet['id'],
                                         ip_address=selfip_address)

    def _get_bigip_selfip_address(self, bigip, subnet):
        # Get ip address for selfip to use on BIG-IP®.
        selfip_name = "local-" + bigip.device_name + "-" + subnet['id']
        ports = self.driver.plugin_rpc.get_port_by_name(port_name=selfip_name)
        if len(ports) > 0:
            port = ports[0]
        else:
            port = self.driver.plugin_rpc.create_port_on_subnet(
                subnet_id=subnet['id'],
                mac_address=None,
                name=selfip_name,
                fixed_address_count=1)
        return port['fixed_ips'][0]['ip_address']

    def assure_gateway_on_subnet(self, bigip, subnetinfo, traffic_group):
        # Called for every bigip only in replication mode.
        # Otherwise called once.
        subnet = subnetinfo['subnet']
        if subnet['id'] in bigip.assured_gateway_subnets:
            return

        network = subnetinfo['network']
        (network_name, preserve_network_name) = \
            self.l2_service.get_network_name(bigip, network)

        if self.l2_service.is_common_network(network):
            network_folder = 'Common'
            network_name = '/Common/' + network_name
        else:
            network_folder = subnet['tenant_id']

        # Select a traffic group for the floating SelfIP
        floating_selfip_name = "gw-" + subnet['id']
        netmask = netaddr.IPNetwork(subnet['cidr']).netmask

        model = {
            'name': floating_selfip_name,
            'ip_address': subnet['gateway_ip'],
            'netmask': netmask,
            'vlan_name': network_name,
            'floating': True,
            'traffic_group': traffic_group,
            'partition': network_folder,
            'preserve_vlan_name': preserve_network_name
        }
        self.create(bigip, model)

        if self.l3_binding:
            self.l3_binding.bind_address(subnet_id=subnet['id'],
                                         ip_address=subnet['gateway_ip'])

        # Setup a wild card ip forwarding virtual service for this subnet
        gw_name = "gw-" + subnet['id']
        vs = bigip.ltm.virtuals.virtual
        if not vs.exists(name=gw_name, partition=network_folder):
            vs.create(
                name=gw_name,
                partition=network_folder,
                destination='0.0.0.0:0',
                mask='0.0.0.0',
                vlansEnabled=True,
                vlans=[network_name],
                sourceAddressTranslation={'type': 'automap'},
                ipForward=True
            )
        else:
            vs.load(name=gw_name, partition=network_folder)
        virtual_address = bigip.ltm.virtual_address_s.virtual_address
        virtual_address.load(name='0.0.0.0:0', partition=network_folder)
        virtual_address.update(trafficGroup=traffic_group)
        bigip.assured_gateway_subnets.append(subnet['id'])

    def delete_gateway_on_subnet(self, bigip, subnetinfo):
        # Called for every bigip only in replication mode.
        # Otherwise called once.
        network = subnetinfo['network']
        if not network:
            LOG.error('Attempted to delete default gateway '
                      'for network with no id... skipping.')
            return
        subnet = subnetinfo['subnet']
        if self.l2_service.is_common_network(network):
            network_folder = 'Common'
        else:
            network_folder = subnet['tenant_id']

        floating_selfip_name = "gw-" + subnet['id']
        if self.driver.conf.f5_populate_static_arp:
            self.network_helper.arp_delete_by_subnet(
                bigip,
                partition=network_folder,
                subnet=subnetinfo['subnet']['cidr'],
                mask=None
            )

        self.network_helper.delete_selfip(
            bigip, floating_selfip_name, network_folder)

        if self.l3_binding:
            self.l3_binding.unbind_address(subnet_id=subnet['id'],
                                           ip_address=subnet['gateway_ip'])

        gw_name = "gw-" + subnet['id']

        vs = bigip.ltm.virtuals.virtual
        if vs.exists(name=gw_name, partition=network_folder):
            vs.load(name=gw_name, partition=network_folder)
            vs.delete()

        if subnet['id'] in bigip.assured_gateway_subnets:
            bigip.assured_gateway_subnets.remove(subnet['id'])
        return gw_name
