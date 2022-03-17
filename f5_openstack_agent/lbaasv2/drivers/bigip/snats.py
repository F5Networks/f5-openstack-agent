# Copyright (c) 2014-2018, F5 Networks, Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import \
    ResourceType
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BigipSnatManager(object):
    def __init__(self, driver, l2_service):
        self.driver = driver
        self.l2_service = l2_service
        self.snatpool_manager = BigIPResourceHelper(ResourceType.snatpool)

    def get_flavor_snat_name(self, lb_id):
        return 'snat_' + lb_id

    def assure_bigip_snats(
            self, bigip, subnetinfo,
            snat_info, tenant_id, snat_name):
        # Configure the ip addresses for snat
        network = subnetinfo['network']
        members = [
            m + '%' + str(network['route_domain_id'])
            for m in snat_info['addrs']
        ]

        snat_pool_model = {
            "name": snat_info['pool_name'],
            "partition": snat_info['pool_folder'],
            "members": members
        }
        try:
            self.snatpool_manager.create(
                bigip,
                snat_pool_model
            )
        except Exception as err:
            LOG.exception(err)
            raise f5_ex.SNATCreationException(
                "Error creating snat pool: %s" %
                snat_info)

    def delete_flavor_snats(self, bigip, subnetinfo,
                            partition, snat_pool):

        try:
            # icontrol rest will not raise error
            # when 404
            self.snatpool_manager.delete(
                bigip,
                name=snat_pool,
                partition=partition
            )
        except Exception as err:
            LOG.exception(err)
            raise f5_ex.SNATCreationException(
                "Error deleting snat pool: %s" %
                snat_pool)

    def update_flavor_snats(
        self, bigip, partition, pool_name,
        new_snat_addrs
    ):
        try:
            # icontrol rest will raise error
            # when 404
            snatpool = self.snatpool_manager.load(
                bigip,
                name=pool_name,
                partition=partition
            )
            snatpool.modify(members=new_snat_addrs)
        except Exception as err:
            LOG.exception(err)
            raise f5_ex.SNATCreationException(
                "Error updating snat pool: %s" %
                new_snat_addrs)

    def snatpool_exist(self, bigip, name, partition='Common'):
        if not name:
            return False
        return self.snatpool_manager.exists(
            bigip, name=name, partition=partition
        )
