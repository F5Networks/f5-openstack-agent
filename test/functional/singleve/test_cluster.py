'''
test_requirements = {'devices':         [VE],
                     'openstack_infra': []}

'''
# Copyright 2015-2016 F5 Networks Inc.
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

from pprint import pprint as pp
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import\
    ClusterManager

cm = ClusterManager()


def test_device_name(mgmt_root):
    device_name = mgmt_root._meta_data['device_name']
    assert cm.get_device_name(mgmt_root) == device_name


def test_devices(mgmt_root, symbols):
    devices = cm.devices(mgmt_root)
    assert len(devices) == 1
    for k, v in symbols.__dict__.items():
        print('key: {}'.format(k))
        print('value: {}'.format(v))
    assert devices[0].managementIp == symbols.bigip_mgmt_ip


def test_get_sync_status(mgmt_root):
    # expect Standalone
    assert cm.get_sync_status(mgmt_root) == 'Standalone'


def test_auto_sync(mgmt_root):
    # assume BIG-IP has device group test-group
    device_group = 'test-group'
    cm.disable_auto_sync(device_group, mgmt_root)
    dg = mgmt_root.cm.device_groups.device_group.load(name=device_group,
                                                  partition='Common')
    assert dg.autoSync == 'disabled'

    cm.enable_auto_sync(device_group, mgmt_root)
    dg.refresh()
    assert dg.autoSync == 'enabled'


def test_get_traffic_groups(mgmt_root):
    # assume 'traffic-group-local-only' already created
    traffic_groups = cm.get_traffic_groups(mgmt_root)
    assert 'traffic-group-local-only' in traffic_groups


def test_get_device_group():
    device_group = cm.get_device_group
    assert device_group is not None


def test_get_mgmt_addr_by_device(symbols, mgmt_root):
    pp(dir(symbols))
    device_name = mgmt_root._meta_data['device_name']
    devices = cm.devices(mgmt_root)
    addr = cm.get_mgmt_addr_by_device(mgmt_root, device_name)
    mgmt_ips = (symbols.bigip_mgmt_ip, symbols.bigip_mgmt_ip_public)
    assert addr in mgmt_ips
    print(addr)
