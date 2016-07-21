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
from f5.bigip import ManagementRoot
from f5.utils.testutils.registrytools import register_device
from pprint import pprint as pp
import sys
import time
import pytest
import yaml

import requests

requests.packages.urllib3.disable_warnings()


def test_loadbalancer_CLUDS(setup_with_nclientmanager, bigip):
    start_registry = register_device(bigip)
    nclientmanager = setup_with_nclientmanager
    subnets = nclientmanager.list_subnets()['subnets']
    for sn in subnets:
        if 'client-v4' in sn['name']:
            lbconf = {'vip_subnet_id': sn['id'],
                      'tenant_id':     sn['tenant_id'],
                      'name':          'testlb_02'}
    start_folders = bigip.tm.sys.folders.get_collection()
    # check that the bigip partitions are correct pre-create
    pp(lbconf)
    assert len(start_folders) == 2
    for sf in start_folders:
        assert sf.name == '/' or sf.name == 'Common'
    # Initialize lb and wait for confirmation from neutron
    active_lb = nclientmanager.create_loadbalancer({'loadbalancer': lbconf})

    lbid = active_lb['loadbalancer']['id']
    assert active_lb['loadbalancer']['description'] == ''
    assert active_lb['loadbalancer']['provisioning_status'] == 'ACTIVE'
    assert active_lb['loadbalancer']['provider'] == 'f5networks'
    # Test show and update
    end_registry = register_device(bigip)
    pp([f.selfLink for f in bigip.tm.sys.folders.get_collection()])
    new_uris = set(end_registry.keys()) - set(start_registry.keys())
    pp(new_uris)
    nclientmanager.update_loadbalancer(
        lbid, {'loadbalancer': {'description': 'as;iofnypq3489'}})
    shown_lb = nclientmanager.show_loadbalancer(lbid)
    assert shown_lb['loadbalancer']['description'] == 'as;iofnypq3489'
    # verify the creation of the appropriate partition on the bigip

    active_folders = bigip.tm.sys.folders.get_collection()
    assert len(active_folders) == 3
    for sf in active_folders:
        assert sf.name == '/' or\
            sf.name == 'Common' or\
            sf.name.startswith('Project_')
    # delete
    time.sleep(2)
    nclientmanager.delete_loadbalancer(lbid)
    # verify removal from OS on delete
    assert not nclientmanager.list_loadbalancers()['loadbalancers']
    final_folders = bigip.tm.sys.folders.get_collection()
    ## verify removal of partition from bigip on delete
    assert len(final_folders) == 2
    for sf in final_folders:
        assert sf.name == '/' or sf.name == 'Common'
