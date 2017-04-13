'''
test_requirements = {'devices':         [VE],
                     'openstack_infra': [Neutron or Neutronless]}

'''
# Copyright 2015-2106 F5 Networks Inc.
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

import json
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from f5.bigip import BigIP
from f5_openstack_agent.lbaasv2.drivers.bigip.pool_service import \
    PoolServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.loadbalancer_service import \
    LoadBalancerServiceBuilder


def test_create_listener(symbols):
    lb_service = LoadBalancerServiceBuilder()
    pool_builder = PoolServiceBuilder()
    bigips = [BigIP(symbols.bigip_mgmt_ip_public, 'admin', 'admin')]
    service = json.load(open("service.json"))["service"]

    try:
        # create partition
        lb_service.prep_service(service, bigips)

        # create BIG-IP virtual servers
        pools = service["pools"]
        loadbalancer = service["loadbalancer"]

        for pool in pools:
            # create a service object in form expected by builder
            svc = {"loadbalancer": loadbalancer,
                   "pool": pool}

            # create
            pool_builder.create_pool(svc, bigips)

            # delete
            pool_builder.delete_pool(svc, bigips)

    finally:
        lb_service.delete_partition(service, bigips)
