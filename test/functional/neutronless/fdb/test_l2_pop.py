# coding=utf-8
# Copyright 2017 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import json
import logging
import os
import pytest
import random
import requests

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper

from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.resource_validator import ResourceValidator

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/single_pool.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture(scope="module")
def bigip():
    return BigIpClient(pytest.symbols.bigip_mgmt_ip_public,
                       pytest.symbols.bigip_username,
                       pytest.symbols.bigip_password)


@pytest.fixture
def fake_plugin_rpc(services):

    rpcObj = FakeRPCPlugin(services)

    return rpcObj

@pytest.fixture
def icontrol_driver(icd_config, fake_plugin_rpc):
    class ConfFake(object):
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    icd = iControlDriver(ConfFake(icd_config),
                         registerOpts=False)

    icd.plugin_rpc = fake_plugin_rpc

    return icd

def random_ip():
    ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
    return ip

def random_mac():
    return "%02x:%02x:%02x:%02x:%02x:%02x" % (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    )

def create_fdb_entry(seg_id):
    """
    Example of fdb entry received from Neutron l2 pop events:

    'e2192a41-1f28-4a58-b1b8-90e551bf8dc4': {
        'network_type': 'vxlan',
        'ports': {
            '216.114.18.232': [['d9:ec:4f:7b:83:09',
                                '213.160.170.162']]
        },
        'segment_id': 84
    }
    """
    n_vteps = random.randint(1, 6)
    vtep = random_ip()
    ports = {}
    ports[vtep] = list()
    for _ in range(n_vteps):
        record = list()
        record.append(random_mac())
        record.append(random_ip())
        ports[vtep].append(record)

    return {
        'e2192a41-1f28-4a58-b1b8-90e551bf8dc4': {
            'network_type': 'vxlan',
            'segment_id': seg_id,
            'ports': ports
        }
    }

def test_add_remove_fdbs(bigip, icontrol_driver):
    """ Test simulating L2 pop events to add/remove fdb entries."""

    net_helper = NetworkHelper()
    tunnels = list()
    fdb_entries = list()

    # create tunnels on BIG-IP, and fake fdb entries
    for seg_id in range(50, 55):
        tunnel_name = 'tunnel-vxlan-{}'.format(seg_id)
        net_helper.create_multipoint_tunnel(bigip.bigip,
            {'name': tunnel_name,
             'key': seg_id,
             'profile': 'vxlan_ovs',
             'localAddress': '201.0.155.10'})
        tunnels.append(tunnel_name)

        # create a set of fdb entries that reference network seg ID
        for _ in range(3):
            entry = create_fdb_entry(seg_id)
            fdb_entries.append(entry)

    # add fdb entries
    for fdb_entry in fdb_entries:
        # mimic neutron L2 pop add_fdb_entries
        icontrol_driver.fdb_add(fdb_entry)

    # check created
    for tunnel_name in tunnels:
        records = net_helper.get_fdb_entry(bigip.bigip, tunnel_name=tunnel_name)
        assert len(records) > 0

    # remove fdb entries
    for fdb_entry in fdb_entries:
        # mimic neutron L2 pop remove_fdb_entries
        icontrol_driver.fdb_remove(fdb_entry)

    # check removed
    for tunnel_name in tunnels:
        records = net_helper.get_fdb_entry(bigip.bigip, tunnel_name=tunnel_name)
        assert len(records) == 0
        net_helper.delete_tunnel(bigip.bigip, tunnel_name)
