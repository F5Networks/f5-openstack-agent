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

import copy
import json
import mock
import os
from pprint import pprint as pp
import requests
requests.packages.urllib3.disable_warnings()
import sys
import time
import pytest
from pytest import symbols

from oslo_config import cfg
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver

from f5.utils.testutils.registrytools import register_device
from f5.utils.testutils.registrytools import register_OC_atoms

from pycallgraph import PyCallGraph
from pycallgraph.output import GraphvizOutput

from urlparse import urlsplit
osd = os.path.dirname
DISTRIBUTIONROOT = osd(osd(osd(osd(__file__))))
del osd
SERVICELIBDIR = os.path.join(DISTRIBUTIONROOT,
                             'devtools',
                             'sample_data',
                             'service_library')
CREATELB_SVC =\
    json.load(open(os.path.join(SERVICELIBDIR, 'createlb.json'), 'r'))
DISCONNECTED_SVC =\
    json.load(open(os.path.join(
        SERVICELIBDIR, 'disconnected.json'), 'r'))['service']
CONNECTED_SVC =\
    json.load(open(os.path.join(
        SERVICELIBDIR, 'connected.json'), 'r'))['service']
DELETELB_SVC =\
    json.load(open(os.path.join(SERVICELIBDIR, 'deletelb.json'), 'r'))

for listener in DISCONNECTED_SVC['listeners']:
    listener['provisioning_status'] = 'PENDING_CREATE'
for pool in DISCONNECTED_SVC['pools']:
    pool['provisioning_status'] = 'PENDING_CREATE'
for monitor in DISCONNECTED_SVC['healthmonitors']:
    monitor['provisioning_status'] = 'PENDING_CREATE'
for member in DISCONNECTED_SVC['members']:
    member['provisioning_status'] = 'PENDING_CREATE'
    member['network_id'] = u'a8f301b2-b7b9-404a-a746-53c442fa1a4f'

for listener in CONNECTED_SVC['listeners']:
    listener['provisioning_status'] = 'PENDING_CREATE'
for pool in CONNECTED_SVC['pools']:
    pool['provisioning_status'] = 'PENDING_CREATE'
for monitor in CONNECTED_SVC['healthmonitors']:
    monitor['provisioning_status'] = 'PENDING_CREATE'
for member in CONNECTED_SVC['members']:
    member['provisioning_status'] = 'PENDING_CREATE'
    member['network_id'] = u'a8f301b2-b7b9-404a-a746-53c442fa1a4f'

@pytest.fixture(scope='module')
def setup_registry_snapshot(bigip):
    # Setup device registries
    pp('inside setup_registry_snapshot')
    return frozenset(register_device(bigip))


@pytest.fixture
def setup_neutronless(request, bigip, setup_registry_snapshot):
    pretest_snapshot = setup_registry_snapshot
    """F5 LBaaS agent for OpenStack."""
    # Setup neutronless icontroldriver
    for element, value in symbols.__dict__.items():
        setattr(cfg.CONF, element, value)
    icontroldriver = iControlDriver(cfg.CONF, registerOpts=False)
    icontroldriver.plugin_rpc = mock.MagicMock()
    wrappedicontroldriver = mock.MagicMock(wraps=icontroldriver)

    def _deletion_order(to_delete):
        ordering = {'/mgmt/tm/ltm/pool': 1,
                    'mgmt/tm/ltm/node/': 2,
                    'monitor': 3,
                    'virtual-address': 4,
                    '/mgmt/tm/ltm/virtual': 5,
                    '/mgmt/tm/net/fdb/tunnel': 6,
                    'mgmt/tm/net/tunnels/tunnel/': 7,
                    '/mgmt/tm/sys/folder': 8}
        def order_key(item):
            for k in ordering:
                if k in item:
                    return ordering[k]
            return 999
        ordered_for_deletion = sorted(list(to_delete), key=order_key)
        pp(ordered_for_deletion)
        return ordered_for_deletion

    def remove_test_created_elements():
        posttest_registry = register_device(bigip)
        created = frozenset(posttest_registry) - pretest_snapshot
        pp('created')
        pp(created)
        ordered = _deletion_order(created)
        for selfLink in ordered:
            if 'virtual-address' not in selfLink:
                posttest_registry[selfLink].delete() 

    request.addfinalizer(remove_test_created_elements)
    return bigip, wrappedicontroldriver, pretest_snapshot


def test_loadbalancer_CD(setup_neutronless):
    # UPDATELB_SVC doesn't appear to change the device state
    # so this test doesn't include an update invocation
    bigip, wicontrold, _ = setup_neutronless

    # record start state
    start_folders = bigip.tm.sys.folders.get_collection()
    assert len(start_folders) == 2
    for sf in start_folders:
        assert sf.name == '/' or sf.name == 'Common'

    # invoke CREATELB_SVC operation
    pp(DISCONNECTED_SVC)
    # pp(CREATELB_SVC)
    wicontrold._common_service_handler(DISCONNECTED_SVC)

    # verify CREATELB_SVCd state
    active_folders = bigip.tm.sys.folders.get_collection()
    vs = bigip.tm.ltm.virtuals.get_collection()[0]
    # pp(vs.raw)
    start_keys = frozenset(vs.__dict__)
    assert vs.selfLink == 'https://localhost/mgmt/tm/ltm/virtual'\
        '/~TEST_cd6a91ccb44945129ac78e7c992655eb~listener2?ver=11.6.0'
    #wicontrold._common_service_handler(CONNECTED_SVC)
    vsend = bigip.tm.ltm.virtuals.get_collection()[0]
    # pp(vsend.raw)
    stop_keys = frozenset(vsend.__dict__)
    pp(stop_keys - start_keys)
    pp(start_keys - stop_keys)
    #for k in start_keys:
    assert len(active_folders) == 3
    folder_names = [sf.name for sf in active_folders]
    thirty_two_zeros = '0'*32
    # assert '/' in folder_names and\
    #       'Common' in folder_names and\
    #       'TEST_' + thirty_two_zeros in folder_names

    # invoke DELETELB_SVC XXX operation FAILS silently!
    # wicontrold._common_service_handler(DELETELB_SVC)

    # verify DELETELB_SVCd state
    # end_folders = bigip.tm.sys.folders.get_collection()
    # assert len(end_folders) == 2
    # for sf in end_folders:
    #     assert sf.name == '/' or sf.name == 'Common'
