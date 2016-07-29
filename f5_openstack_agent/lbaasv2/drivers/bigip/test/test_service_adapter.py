# coding=utf-8
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

import copy

import pytest

from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import\
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import\
    SubnetNotMatched
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import\
    SubnetsNotInService


class FakeConf(object):
    def __init__(self):
        self.environment_prefix = False


ID_TO_MATCH = u'MATCH!'
MATCHED_SUBNET = {u'allocation_pools': {u'end': u'172.16.101.254',
                                        u'start': u'172.16.101.2'},
                  u'cidr': u'172.16.101.0/24',
                  u'dns_nameservers': u'',
                  u'enable_dhcp': True,
                  u'gateway_ip': u'172.16.101.1',
                  u'host_routes': u'',
                  u'id': ID_TO_MATCH,
                  u'ip_version': 4,
                  u'ipv6_address_mode': u'',
                  u'ipv6_ra_mode': u'',
                  u'name': u'private-subnet',
                  u'network_id': u'a8f301b2-b7b9-404a-a746-53c442fa1a4f',
                  u'subnetpool_id': u'',
                  u'tenant_id': u'822022f87c3a47189a0b1a4a8d855ce4'}

MISSED_SUBNET = copy.deepcopy(MATCHED_SUBNET)
MISSED_SUBNET['id'] = '-'.join([u'f'*8, u'f'*4, u'f'*4, u'f'*4, u'f'*12])
FAKESUCCESSFULSERVICE = {'subnets': [MISSED_SUBNET, MATCHED_SUBNET]}


def test_succesful_get_subnet_from_service():
    sma = ServiceModelAdapter(FakeConf())
    subnet = sma.get_subnet_from_service(FAKESUCCESSFULSERVICE, ID_TO_MATCH)
    assert subnet == MATCHED_SUBNET


FAKEMATCHLESSSERVICE = {'subnets': [MISSED_SUBNET,
                                    MISSED_SUBNET,
                                    MISSED_SUBNET]}


def test_matchless_service():
    sma = ServiceModelAdapter(FakeConf())
    with pytest.raises(SubnetNotMatched) as SNMEIO:
        sma.get_subnet_from_service(FAKEMATCHLESSSERVICE, ID_TO_MATCH)
    assert SNMEIO.value.message.startswith("No matching")


FAKESUBNETLESSSERIVE = {'listeners': ['a', 'a']}


def test_subnetless_service():
    sma = ServiceModelAdapter(FakeConf())
    with pytest.raises(SubnetsNotInService) as SNMEIO:
        sma.get_subnet_from_service(FAKESUBNETLESSSERIVE, ID_TO_MATCH)
    assert SNMEIO.value.message.startswith('The service object does not have')
