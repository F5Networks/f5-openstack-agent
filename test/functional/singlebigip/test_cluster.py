'''
test_requirements = {'devices':         [VE],
                     'openstack_infra': []}

'''
# Copyright (c) 2015-2018, F5 Networks, Inc.
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
    # for 13.0.0, mgmt IP will always be 192.168.1.245
    assert (devices[0].managementIp == symbols.bigip_mgmt_ips[0] or
            devices[0].managementIp == '192.168.1.245')


def test_get_sync_status(mgmt_root):
    # expect Standalone
    assert cm.get_sync_status(mgmt_root) == 'Standalone'


def test_auto_sync(mgmt_root):
    # create device group test-group on BIGIP
    device_group = 'test-group'
    dg = mgmt_root.tm.cm.device_groups.device_group.create(name=device_group,
                                                           partition='Common')
    cm.disable_auto_sync(device_group, mgmt_root)
    assert dg.autoSync == 'disabled'

    cm.enable_auto_sync(device_group, mgmt_root)
    dg.refresh()
    assert dg.autoSync == 'enabled'

    # delete the device group created
    dg.delete()


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
    addr = cm.get_mgmt_addr_by_device(mgmt_root, device_name)
    # for 13.0.0, mgmt IP will always be 192.168.1.245
    assert (addr == symbols.bigip_mgmt_ips[0] or
            addr == '192.168.1.245')
