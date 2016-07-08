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

import json
import mock
import os
from pprint import pprint as pp
import requests
requests.packages.urllib3.disable_warnings()
import pytest
from pytest import symbols
import time

from oslo_config import cfg

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver

from f5.utils.testutils.registrytools import register_device

osd = os.path.dirname
DISTRIBUTIONROOT = osd(osd(osd(osd(__file__))))
del osd
SERVICELIBDIR = os.path.join(DISTRIBUTIONROOT,
                             'devtools',
                             'sample_data',
                             'service_library')
LISTENER_ID = u'ffffffff-ffff-ffff-ffff-ffffffffffff'
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

pp(DISCONNECTED_SVC)
DISCONNECTED_SVC['pools'][0]['listeners'][0]['id'] = LISTENER_ID
DISCONNECTED_SVC['listeners'][0]['id'] = LISTENER_ID
CONNECTED_SVC['pools'][0]['listeners'][0]['id'] = LISTENER_ID
CONNECTED_SVC['listeners'][0]['id'] = LISTENER_ID
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
        ordering = {'/mgmt/tm/ltm/virtual': 1,
                    '/mgmt/tm/ltm/pool': 2,
                    'mgmt/tm/ltm/node/': 3,
                    'monitor': 4,
                    'virtual-address': 5,
                    '/mgmt/tm/net/fdb/tunnel': 6,
                    'mgmt/tm/net/tunnels/tunnel/': 7,
                    '/mgmt/tm/sys/folder': 8}

        def order_key(item):
            for k in ordering:
                if k in item:
                    return ordering[k]
            return 999
        ordered_for_deletion = sorted(list(to_delete), key=order_key)
        return ordered_for_deletion

    def remove_test_created_elements():
        posttest_registry = register_device(bigip)
        created = frozenset(posttest_registry) - pretest_snapshot
        ordered = _deletion_order(created)
        for selfLink in ordered:
            if 'virtual-address' not in selfLink:
                posttest_registry[selfLink].delete()

    request.addfinalizer(remove_test_created_elements)
    return bigip, wrappedicontroldriver, pretest_snapshot


def test_disconnected_service(setup_neutronless):
    bigip, wicontrold, _ = setup_neutronless

    # record start state
    start_folders = bigip.tm.sys.folders.get_collection()
    assert len(start_folders) == 2
    for sf in start_folders:
        assert sf.name == '/' or sf.name == 'Common'

    count = 0
    while count <= 5:
        count = count + 1
        time.sleep(1)
        wicontrold._common_service_handler(DISCONNECTED_SVC)
        vs = bigip.tm.ltm.virtuals.get_collection()[0]
        assert vs.vlans ==\
            [u'/TEST_cd6a91ccb44945129ac78e7c992655eb/disconnected_network']
    assert vs.selfLink == 'https://localhost/mgmt/tm/ltm/virtual'\
        '/~TEST_cd6a91ccb44945129ac78e7c992655eb~listener2?ver=11.6.0'
    wicontrold._common_service_handler(CONNECTED_SVC)
    vsend = bigip.tm.ltm.virtuals.get_collection()[0]
    assert vsend.selfLink == 'https://localhost/mgmt/tm/ltm/virtual'\
        '/~TEST_cd6a91ccb44945129ac78e7c992655eb~listener2?ver=11.6.0'
    assert 'vlans' not in vsend.__dict__
