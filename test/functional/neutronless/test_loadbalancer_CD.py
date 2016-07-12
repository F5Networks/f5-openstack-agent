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
import pytest
from pytest import symbols
import requests
requests.packages.urllib3.disable_warnings()

from oslo_config import cfg

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver

from f5.utils.testutils.registrytools import register_device

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
UPDATELB_SVC =\
    json.load(open(os.path.join(SERVICELIBDIR, 'updatelb.json'), 'r'))
DELETELB_SVC =\
    json.load(open(os.path.join(SERVICELIBDIR, 'deletelb.json'), 'r'))


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
        ordered = []
        for order_tag in ['member',
                          '/mgmt/tm/ltm/pool',
                          'monitor',
                          '/mgmt/tm/ltm/virtual',
                          '/mgmt/tm/sys/folder']:
            for td in to_delete:
                path_start = urlsplit(td).path.rpartition('/')[0]
                if (order_tag in path_start) and ('address' not in td):
                    ordered.append(td)
        return ordered

    def remove_test_created_elements():
        posttest_registry = register_device(bigip)
        created = frozenset(posttest_registry) - pretest_snapshot
        ordered = _deletion_order(created)
        for selfLink in ordered:
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
    wicontrold._common_service_handler(CREATELB_SVC)

    # verify CREATELB_SVCd state
    active_folders = bigip.tm.sys.folders.get_collection()
    assert len(active_folders) == 3
    folder_names = [sf.name for sf in active_folders]
    thirty_two_zeros = '0'*32
    assert '/' in folder_names and\
           'Common' in folder_names and\
           'TEST_' + thirty_two_zeros in folder_names

    # invoke DELETELB_SVC XXX operation FAILS silently!
    wicontrold._common_service_handler(DELETELB_SVC)

    # verify DELETELB_SVCd state
    end_folders = bigip.tm.sys.folders.get_collection()
    assert len(end_folders) == 2
    for sf in end_folders:
        assert sf.name == '/' or sf.name == 'Common'


listener_config = {'name': 'test_listener',
                   'loadbalancer_id': CREATELB_SVC['loadbalancer']['id'],
                   'protocol': 'HTTP',
                   'protocol_port': 80,
                   'provisioning_status': 'PENDING_CREATE',
                   'id': 'b'*32}
CREATE_LISTEN_SVC = copy.deepcopy(CREATELB_SVC)
CREATE_LISTEN_SVC['listeners'].append(listener_config)
DELETE_LISTEN_SVC = copy.deepcopy(CREATE_LISTEN_SVC)
DELETE_LISTEN_SVC['listeners'][0]['provisioning_status'] = 'PENDING_DELETE'


def test_listener_CD(setup_neutronless):
    bigip, wicontrold, _ = setup_neutronless
    assert not bigip.tm.ltm.virtuals.get_collection()
    wicontrold._common_service_handler(CREATE_LISTEN_SVC)
    active_virts = bigip.tm.ltm.virtuals.get_collection()
    assert active_virts[0].name == 'test_listener'
    wicontrold._common_service_handler(DELETE_LISTEN_SVC)
    assert not bigip.tm.ltm.virtuals.get_collection()


# pp(CREATE_LISTEN_SVC)
pool_config = {'name': 'test_pool_anur23rgg',
               'lb_algorithm': 'ROUND_ROBIN',
               'listener_id': CREATE_LISTEN_SVC['listeners'][0]['id'],
               'protocol': 'HTTP',
               'provisioning_status': 'PENDING_CREATE',
               'id': 'c'*32}

CREATE_POOL_SVC = copy.deepcopy(CREATE_LISTEN_SVC)
CREATE_POOL_SVC['pools'].append(pool_config)
DELETE_POOL_SVC = copy.deepcopy(CREATE_POOL_SVC)
DELETE_POOL_SVC['pools'][0]['provisioning_status'] = 'PENDING_DELETE'


def test_pool_CD(setup_neutronless):
    bigip, wicontrold, _ = setup_neutronless
    assert not bigip.tm.ltm.pools.get_collection()
    wicontrold._common_service_handler(CREATE_POOL_SVC)
    assert bigip.tm.ltm.pools.get_collection()[0].name == 'test_pool_anur23rgg'
    wicontrold._common_service_handler(DELETE_POOL_SVC)
    assert not bigip.tm.ltm.pools.get_collection()


member_config = {'subnet_id': CREATELB_SVC['loadbalancer']['vip_subnet_id'],
                 'network_id': CREATELB_SVC['loadbalancer']['network_id'],
                 'provisioning_status': 'PENDING_CREATE',
                 'pool_id': CREATE_POOL_SVC['pools'][0]['id'],
                 'protocol_port': 80,
                 'id': 'd'*32}

CREATE_MEMBER_SVC = copy.deepcopy(CREATE_POOL_SVC)
CREATE_MEMBER_SVC['members'].append(member_config)
DELETE_MEMBER_SVC = copy.deepcopy(CREATE_MEMBER_SVC)
DELETE_MEMBER_SVC['members'][0]['provisioning_status'] = 'PENDING_DELETE'


def test_member_CD(setup_neutronless):
    bigip, wicontrold, _ = setup_neutronless
    wicontrold._common_service_handler(CREATE_POOL_SVC)
    assert bigip.tm.ltm.pools.get_collection()[0].name == 'test_pool_anur23rgg'
    members = bigip.tm.ltm.pools.get_collection()[0].members_s
    assert not members.get_collection()
    wicontrold._common_service_handler(CREATE_MEMBER_SVC)
    # SANITY CHECK assert
    # bigip.tm.ltm.pools.get_collection()[0].name == 'test_pool_anur23rgg'
    assert members.get_collection()
    wicontrold._common_service_handler(DELETE_MEMBER_SVC)
    assert not members.get_collection()


monitor_config = {'delay': 3,
                  'pool_id': CREATE_POOL_SVC['pools'][0]['id'],
                  'type': 'HTTP',
                  'timeout': 13,
                  'max_retries': 7,
                  'provisioning_status': 'PENDING_CREATE',
                  'id': 'e'*32}

CREATE_HM_SVC = copy.deepcopy(CREATE_MEMBER_SVC)
CREATE_HM_SVC['healthmonitors'].append(monitor_config)
DELETE_HM_SVC = copy.deepcopy(CREATE_HM_SVC)
DELETE_HM_SVC['healthmonitors'][0]['provisioning_status'] == 'PENDING_DELETE'


def test_healthmonitor_CD(setup_neutronless):
    bigip, wicontrold, _ = setup_neutronless
    https = bigip.tm.ltm.monitor.https
    init_monitors = set([x.selfLink for x in https.get_collection()])
    assert len(init_monitors) == 2
    test_sl = 'https://localhost/mgmt/tm/ltm/monitor/http/'\
              '~TEST_00000000000000000000000000000000'\
              '~TEST_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee?ver=11.6.0'
    expected_monitors = init_monitors | set((test_sl,))
    wicontrold._common_service_handler(CREATE_POOL_SVC)
    wicontrold._common_service_handler(CREATE_HM_SVC)
    observed_with_test_mon = set([x.selfLink for x in https.get_collection()])
    assert observed_with_test_mon == expected_monitors
    wicontrold._common_service_handler(DELETE_HM_SVC)
    observed_post_delete = set([x.selfLink for x in https.get_collection()])
    assert observed_post_delete == init_monitors
