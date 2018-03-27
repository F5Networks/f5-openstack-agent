# coding=utf-8
# Copyright (c) 2014-2018, F5 Networks, Inc.
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

from icontrol.exceptions import iControlUnexpectedHTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions \
    import BigIPNotLicensedForVcmp
from f5_openstack_agent.lbaasv2.drivers.bigip.vcmp import VcmpManager

import copy
import mock
import pytest


VLAN = {
    'name': 'test_vlan',
    'folder': 'Common',
    'id': 1,
    'description': 'test vlan',
    'route_domain_id': 2
}


class FakeResponse400(object):
    status_code = 400


class FakeResponse404(object):
    status_code = 404


class FakeHTTPError400(iControlUnexpectedHTTPError):
    def __init__(self):
        self.message = 'One of the following features must be licensed/' \
            'provisioned for the URI vcmp : vcmp'
        self.response = FakeResponse400()


class FakeHTTPError404(iControlUnexpectedHTTPError):
    def __init__(self):
        self.message = 'test'
        self.response = FakeResponse404()


class FakeConf(object):
    def __init__(
            self, un='admin', pw='admin', vcmp_host='10.190.1.1, 10.190.1.2'):
        self.icontrol_username = un
        self.icontrol_password = pw
        self.icontrol_vcmp_hostname = vcmp_host


@pytest.fixture
def mock_driver():
    mock_driver = mock.MagicMock()
    mock_driver.get_bigip_hosts.return_value = '192.168.1.1'
    mock_driver.conf = FakeConf()
    return mock_driver


@pytest.fixture
def mock_host_obj():
    mgmt_root_obj = mock.MagicMock()
    # Build collection of guests
    guest = mock.MagicMock(name='guest1')
    guest.managementIp = '192.168.1.1/21'
    guest.hostname = '192.168.1.1'
    guest.name = 'guest1'
    guest.vlans = ['/Common/test_vlan']
    guest.tm.net.vlans.vlan.exists.return_value = True
    mgmt_root_obj.tm.vcmp.guests.get_collection.return_value = [guest]
    mgmt_root_obj.hostname = 'host1'
    return mgmt_root_obj


@pytest.fixture
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.ManagementRoot')
def setup_vcmp_mgr(mock_mgmt_root, mock_driver, mock_host_obj):
    mock_mgmt_root.return_value = mock_host_obj
    return VcmpManager(mock_driver)


# global mocks used for mocking the logger and utils in vcmp.py
mock_log = mock.MagicMock(name='mock_log')
mock_utils = mock.MagicMock(name='mock_utils')


@pytest.fixture
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.ManagementRoot')
def setup_vcmp_method_test(mock_mgmt_root, mock_driver, mock_host_obj):
    mock_bigip = mock.MagicMock(name='bigip1')
    mock_bigip.platformId = 'Z101'
    mock_bigip.hostname = '192.168.1.1'
    mock_driver.get_all_bigips.return_value = [mock_bigip]
    mock_mgmt_root.return_value = mock_host_obj
    mock_utils.strip_cidr_netmask.return_value = '192.168.1.1'
    return VcmpManager(mock_driver), mock_bigip


@pytest.fixture
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.ManagementRoot')
def old_setup_vcmp_method_test(mock_mgmt_root, mock_driver, mock_host_obj):
    mock_bigip = mock.MagicMock()
    mock_bigip.platformId = 'Z101'
    mock_bigip.hostname = '192.168.1.1'
    mock_driver.get_all_bigips.return_value = [mock_bigip]
    mock_mgmt_root.return_value = mock_host_obj
    return VcmpManager(mock_driver)


def test___init__(setup_vcmp_mgr):
    vcmp = setup_vcmp_mgr
    assert vcmp.vcmp_hosts != []
    assert len(vcmp.vcmp_hosts) is 2
    assert vcmp.vcmp_hosts[0]['guests'] != []
    assert len(vcmp.vcmp_hosts[0]['guests']) is 1


def test___init__no_vcmp_hosts():
    mock_driver = mock.MagicMock()
    mock_driver.conf = FakeConf(vcmp_host='')
    vcmp = VcmpManager(mock_driver)
    assert vcmp.vcmp_hosts == []


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.ManagementRoot')
def test__init_vcmp_hosts_no_vcmp(mock_mgmt_root, mock_driver, mock_host_obj):
    mock_host_obj.tm.vcmp.guests.get_collection.side_effect = \
        FakeHTTPError400()
    mock_mgmt_root.return_value = mock_host_obj
    with pytest.raises(BigIPNotLicensedForVcmp) as ex:
        VcmpManager(mock_driver)
    assert 'Given vCMP host 10.190.1.1 is not licensed for vCMP' in \
        ex.value.message


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.ManagementRoot')
def test__init_vcmp_hosts_icontrol_exception(
        mock_mgmt_root, mock_driver, mock_host_obj):
    mock_host_obj.tm.vcmp.guests.get_collection.side_effect = \
        FakeHTTPError404()
    mock_mgmt_root.return_value = mock_host_obj
    with pytest.raises(FakeHTTPError404) as ex:
        VcmpManager(mock_driver)
    assert 'test' in ex.value.message


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.ManagementRoot')
def test__init_vcmp_hosts_exception(
        mock_mgmt_root, mock_driver, mock_host_obj):
    mock_host_obj.tm.vcmp.guests.get_collection.side_effect = Exception('test')
    mock_mgmt_root.return_value = mock_host_obj
    with pytest.raises(Exception) as ex:
        VcmpManager(mock_driver)
    assert 'test' in ex.value.message


def test_get_vcmp_guest(setup_vcmp_mgr):
    vcmp = setup_vcmp_mgr
    mock_bigip = mock.MagicMock()
    mock_bigip.hostname = '192.168.1.1'
    ret = vcmp.get_vcmp_guest(vcmp.vcmp_hosts[0], mock_bigip)
    # Ensure the guest we get back is the only guest we defined
    assert ret is vcmp.vcmp_hosts[0]['guests'][0]


def test_get_vcmp_guest_none_guest(setup_vcmp_mgr):
    vcmp = setup_vcmp_mgr
    ret = vcmp.get_vcmp_guest(vcmp.vcmp_hosts[0], mock.MagicMock())
    assert ret is None


def test_get_vcmp_host(setup_vcmp_mgr):
    vcmp = setup_vcmp_mgr
    ret = vcmp.get_vcmp_host(vcmp.vcmp_hosts[0]['guests'][0])
    assert ret is vcmp.vcmp_hosts[0]


def test_get_vcmp_host_none_host(setup_vcmp_mgr):
    vcmp = setup_vcmp_mgr
    ret = vcmp.get_vcmp_host(mock.MagicMock())
    assert ret is None


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test__check_vcmp_host_assignments(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    mock_utils.get_device_info.return_value = mock_bigip
    assert vcmp._check_vcmp_host_assignments() is None
    assert mock_log.debug.call_args == mock.call(
        'VcmpManager::_check_vcmp_host_assignments vCMP host found for '
        'Guest 192.168.1.1')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test__check_vcmp_host_assignments_no_host(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    mock_utils.get_device_info.return_value = mock_bigip
    # this bigip has no host. It is not a guest.
    vcmp.get_vcmp_host = mock.MagicMock(return_value=False)
    assert vcmp._check_vcmp_host_assignments() is None
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::_check_vcmp_host_assignments vCMP host not found '
        'for Guest 192.168.1.1')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test__check_vcmp_host_assignments_bad_platform(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    # Bad platform id
    mock_bigip.platformId = 'Z102'
    mock_utils.get_device_info.return_value = mock_bigip
    assert vcmp._check_vcmp_host_assignments() is None
    assert mock_log.debug.call_args == mock.call(
        'VcmpManager::_check_vcmp_host_assignments BIG-IP 192.168.1.1 is '
        'not a vCMP Guest')


def test__get_vlan_use_count(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    use_cnt = vcmp._get_vlan_use_count(vcmp.vcmp_hosts[0], 'test_vlan')
    assert use_cnt is 1


def test__get_vlan_use_count_zero(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    use_cnt = vcmp._get_vlan_use_count(vcmp.vcmp_hosts[0], 'test_vlan_2')
    assert use_cnt is 0


def test__is_vlan_assoc_with_vcmp_guest(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    ret = vcmp._is_vlan_assoc_with_vcmp_guest(
        vcmp.vcmp_hosts[0]['guests'][0], VLAN)
    assert ret is True


def test__is_vlan_assoc_with_vcmp_guest_no_vlan(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    bad_vlan = copy.copy(VLAN)
    bad_vlan['name'] = 'bad_vlan'
    ret = vcmp._is_vlan_assoc_with_vcmp_guest(
        vcmp.vcmp_hosts[0]['guests'][0], bad_vlan)
    assert ret is False


def test__is_vlan_assoc_with_vcmp_guest_exception(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp.get_vcmp_host = mock.MagicMock()
    vcmp.get_vcmp_host.side_effect = Exception
    ret = vcmp._is_vlan_assoc_with_vcmp_guest(
        vcmp.vcmp_hosts[0]['guests'][0], VLAN)
    assert ret is False


def test_assoc_vlan_with_vcmp_guest(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=False)
    vcmp.assoc_vlan_with_vcmp_guest(mock_bigip, VLAN)
    assert vcmp.vcmp_hosts[0]['guests'][0].modify.call_args == mock.call(
        vlans=['/Common/test_vlan', 'test_vlan'])


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
def test_assoc_vlan_with_vcmp_guest_assoc_exception(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=False)
    vcmp.vcmp_hosts[0]['guests'][0].modify.side_effect = Exception('test')
    vcmp.assoc_vlan_with_vcmp_guest(vcmp.vcmp_hosts[0]['guests'][0], VLAN)
    assert vcmp.vcmp_hosts[0]['guests'][0].modify.call_args == mock.call(
        vlans=['/Common/test_vlan', 'test_vlan'])
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::assoc_vlan_with_vcmp_guest: Exception associating VLAN '
        'test_vlan to vCMP Guest guest1: test')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
def test_assoc_vlan_with_vcmp_guest_already_assoc(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=True)
    assert vcmp.assoc_vlan_with_vcmp_guest(
        vcmp.vcmp_hosts[0]['guests'][0], VLAN) is None


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
def test_assoc_vlan_with_vcmp_guest_create_exception(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    mock_bigip.tm.net.vlans.vlan.exists.side_effect = Exception('test')
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=False)
    vcmp.assoc_vlan_with_vcmp_guest(mock_bigip, VLAN)
    assert vcmp.vcmp_hosts[0]['guests'][0].modify.call_args == mock.call(
        vlans=['/Common/test_vlan', 'test_vlan'])
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::assoc_vlan_with_vcmp_guest: Exception waiting for vCMP '
        'Host VLAN test_vlan to be created on vCMP Guest guest1: test')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.time')
def test_assoc_vlan_with_vcmp_guest_vlan_not_created(
        mock_time, setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    mock_bigip.tm.net.vlans.vlan.exists.return_value = False
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=False)
    vcmp.assoc_vlan_with_vcmp_guest(mock_bigip, VLAN)
    assert vcmp.vcmp_hosts[0]['guests'][0].modify.call_args == mock.call(
        vlans=['/Common/test_vlan', 'test_vlan'])
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::assoc_vlan_with_vcmp_guest: VLAN /Common/test_vlan '
        'does not exist on vCMP Guest guest1')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
def test_assoc_vlan_with_vcmp_guest_vlan_delete_exception(
        setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    mock_bigip.tm.net.vlans.vlan.load().delete.side_effect = Exception('test')
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=False)
    vcmp.assoc_vlan_with_vcmp_guest(mock_bigip, VLAN)
    assert vcmp.vcmp_hosts[0]['guests'][0].modify.call_args == mock.call(
        vlans=['/Common/test_vlan', 'test_vlan'])
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::assoc_vlan_with_vcmp_guest: Exception deleting VLAN '
        '/Common/test_vlan from vCMP Guest guest1: test')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.hasattr')
def test_assoc_vlan_with_vcmp_no_vlan_attr(
        mock_hasattr, setup_vcmp_method_test):
    mock_hasattr.return_value = False
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp._is_vlan_assoc_with_vcmp_guest = mock.MagicMock(return_value=False)
    vcmp.assoc_vlan_with_vcmp_guest(mock_bigip, VLAN)
    assert vcmp.vcmp_hosts[0]['guests'][0].modify.call_args == mock.call(
        vlans=['test_vlan'])
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::assoc_vlan_with_vcmp_guest: Exception deleting VLAN '
        '/Common/test_vlan from vCMP Guest guest1: test')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test_disassoc_vlan_with_vcmp_guest(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp.get_vcmp_host = mock.MagicMock(return_value=vcmp.vcmp_hosts[0])
    mock_utils.get_device_info.return_value = mock_bigip
    vcmp._get_vlan_use_count = mock.MagicMock(return_value=0)
    vcmp.disassoc_vlan_with_vcmp_guest(mock_bigip, 'test_vlan')
    assert mock_log.debug.call_args == mock.call(
        'VcmpManager::disassoc_vlan_with_vcmp_guest Deleted VLAN test_vlan '
        'from vCMP Host host1')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test_disassoc_vlan_with_vcmp_guest_exception(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp.vcmp_hosts[0]['guests'][0].modify.side_effect = Exception('test')
    vcmp.get_vcmp_host = mock.MagicMock(return_value=vcmp.vcmp_hosts[0])
    mock_utils.get_device_info.return_value = mock_bigip
    vcmp._get_vlan_use_count = mock.MagicMock(return_value=0)
    vcmp.disassoc_vlan_with_vcmp_guest(mock_bigip, 'test_vlan')
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::disassoc_vlan_with_vcmp_guest Exception removing VLAN '
        'test_vlan association from vCMP Guest 192.168.1.1: test')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test_disassoc_vlan_with_vcmp_guest_vlan_in_use(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp.get_vcmp_host = mock.MagicMock(return_value=vcmp.vcmp_hosts[0])
    mock_utils.get_device_info.return_value = mock_bigip
    vcmp._get_vlan_use_count = mock.MagicMock(return_value=1)
    vcmp.disassoc_vlan_with_vcmp_guest(mock_bigip, 'test_vlan')
    assert mock_log.debug.call_args == mock.call(
        'VcmpManager::disassoc_vlan_with_vcmp_guest VLAN test_vlan in use by '
        'other vCMP Guests on vCMP Host host1')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test_disassoc_vlan_with_vcmp_guest_vlan_exception(setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp.get_vcmp_host = mock.MagicMock(return_value=vcmp.vcmp_hosts[0])
    mock_utils.get_device_info.return_value = mock_bigip
    vcmp._get_vlan_use_count = mock.MagicMock(return_value=0)
    vcmp.vcmp_hosts[0]['bigip'].tm.net.vlans.vlan.load().side_effect = \
        Exception('test')
    vcmp.disassoc_vlan_with_vcmp_guest(mock_bigip, 'test_vlan')
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::disassoc_vlan_with_vcmp_guest Exception removing VLAN '
        'test_vlan association from vCMP Guest 192.168.1.1: test')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG', mock_log)
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.utils', mock_utils)
def test_disassoc_vlan_with_vcmp_guest_vlan_delete_exception(
        setup_vcmp_method_test):
    vcmp, mock_bigip = setup_vcmp_method_test
    vcmp.get_vcmp_host = mock.MagicMock(return_value=vcmp.vcmp_hosts[0])
    mock_utils.get_device_info.return_value = mock_bigip
    mock_utils.get_device_info.return_value = mock_bigip
    vcmp._get_vlan_use_count = mock.MagicMock(return_value=0)
    vcmp.vcmp_hosts[0]['bigip'].tm.net.vlans.vlan.load().delete.side_effect = \
        Exception('test')
    vcmp.vcmp_hosts[0]['bigip'].icontrol.hostname = 'host1'
    vcmp.disassoc_vlan_with_vcmp_guest(mock_bigip, 'test_vlan')
    assert mock_log.error.call_args == mock.call(
        'VcmpManager::disassoc_vlan_with_vcmp_guest Exception deleting VLAN '
        'test_vlan from vCMP Host host1:test')
