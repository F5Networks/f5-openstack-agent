# coding=utf-8
# Copyright 2017-2018 F5 Networks Inc.
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

"""Test high rate of FDB updates."""

import logging
import random
import pytest
import requests


from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper

from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

@pytest.fixture
def services():
    return list()

@pytest.fixture(scope="module")
def bigip():
    """Create an F5-sdk client."""
    return BigIpClient(pytest.symbols.bigip_floating_ips[0],
                       pytest.symbols.bigip_username,
                       pytest.symbols.bigip_password)


def random_ip():
    "Create a random IP address."
    return ".".join(map(str, (random.randint(0, 255) for _ in range(4))))

def random_mac():
    "Create a random MAC address."
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

    seg_id_start = 167
    seg_id_end = 176
    n_records = 9 

    # create tunnels on BIG-IP, and fake fdb entries
    for seg_id in range(seg_id_start, seg_id_end):
        tunnel_name = 'tunnel-vxlan-{}'.format(seg_id)
        model = {
            'name': tunnel_name,
            'key': seg_id,
            'profile': 'vxlan_ovs',
            'localAddress': '201.0.155.10'}
        net_helper.create_multipoint_tunnel(bigip.bigip, model)
        tunnels.append(tunnel_name)

        # create a set of fdb entries that reference network seg ID
        for _ in range(n_records):
            entry = create_fdb_entry(seg_id)
            fdb_entries.append(entry)

    # add fdb entries
    for fdb_entry in fdb_entries:
        # mimic neutron L2 pop add_fdb_entries
        icontrol_driver.fdb_add(fdb_entry)

    for fdb_entry in fdb_entries:
        # mimic neutron L2 pop add_fdb_entries
        icontrol_driver.fdb_add(fdb_entry)

    # check created
    for tunnel_name in tunnels:
        records = net_helper.get_fdb_entry(bigip.bigip, tunnel_name=tunnel_name)
        assert records

    # remove fdb entries
    for fdb_entry in fdb_entries:
        # mimic neutron L2 pop remove_fdb_entries
        icontrol_driver.fdb_remove(fdb_entry)

    # check removed
    for tunnel_name in tunnels:
        records = net_helper.get_fdb_entry(bigip.bigip, tunnel_name=tunnel_name)
        assert not records
        net_helper.delete_tunnel(bigip.bigip, tunnel_name)

