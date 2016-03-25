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

from f5.bigip import BigIP
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import\
    ClusterManager

device_name = 'host-vm-26.int.lineratesystems.com'
mgmt_ip = '10.190.5.7'
bigip = BigIP(mgmt_ip, 'admin', 'admin')
cm = ClusterManager()


def test_device_name():
    assert cm.get_device_name(bigip) == device_name


def test_devices():
    devices = cm.devices(bigip)
    assert len(devices) == 1
    assert devices[0].managementIp == mgmt_ip


def test_get_sync_status():
    # expect Standalone
    assert cm.get_sync_status(bigip) == 'Standalone'


def test_auto_sync():
    # assume BIG-IP has device group test-group
    device_group = 'test-group'
    cm.disable_auto_sync(device_group, bigip)
    dg = bigip.cm.device_groups.device_group.load(name=device_group,
                                                  partition='Common')
    assert dg.autoSync == 'disabled'

    cm.enable_auto_sync(device_group, bigip)
    dg.refresh()
    assert dg.autoSync == 'enabled'


def test_get_traffic_groups():
    # assume 'traffic-group-local-only' already created
    traffic_groups = cm.get_traffic_groups(bigip)
    assert 'traffic-group-local-only' in traffic_groups


def test_get_device_group():
    device_group = cm.get_device_group
    assert device_group is not None


def test_get_mgmt_addr_by_device():
    addr = cm.get_mgmt_addr_by_device(bigip, device_name)
    assert addr == mgmt_ip
