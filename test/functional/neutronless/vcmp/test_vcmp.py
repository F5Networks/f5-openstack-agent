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


from copy import deepcopy
import json
import logging
import mock
from mock import call
import os
import pytest
import requests

from f5.bigip import ManagementRoot
from f5.utils.testutils.registrytools import register_device
from f5_openstack_agent.lbaasv2.drivers.bigip.exceptions import \
    BigIPNotLicensedForVcmp
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

# Toggle feature on/off configurations
curdir = os.path.dirname(os.path.realpath(__file__))
OSLO_CONFIGS = json.load(open(os.path.join(curdir, 'vcmp_oslo_confs.json')))
VCMP_CONFIG = OSLO_CONFIGS["vcmp_single_host"]
VCMP_CLUSTER_CONFIG = OSLO_CONFIGS["vcmp_cluster"]

GUEST_VLAN = '/TEST_128a63ef33bc4cf891d684fad58e7f2d/vlan-1-1-46'
COMMON_VLAN = '/Common/vlan-1-1-46'

# Library of services as received from the neutron server
NEUTRON_SERVICES = json.load(open(os.path.join(
    curdir, 'vcmp_neutron_services.json')))
CREATELB = NEUTRON_SERVICES["create_connected_loadbalancer"]
DELETELB = NEUTRON_SERVICES["delete_connected_loadbalancer"]
CREATELISTENER = NEUTRON_SERVICES["create_connected_listener"]
DELETELISTENER = NEUTRON_SERVICES["delete_connected_listener"]


def create_default_mock_rpc_plugin():
    mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
    mock_rpc_plugin.get_port_by_name.return_value = [
        {'fixed_ips': [{'ip_address': '10.2.2.134'}]}
    ]
    return mock_rpc_plugin


def configure_icd(icd_config, create_mock_rpc):
    class ConfFake(object):
        '''minimal fake config object to replace oslo with controlled params'''
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    icontroldriver = iControlDriver(ConfFake(icd_config),
                                    registerOpts=False)
    icontroldriver.plugin_rpc = create_mock_rpc()
    return icontroldriver


def logcall(lh, call, *cargs, **ckwargs):
    call(*cargs, **ckwargs)


def handle_init_registry(bigip, icd_configuration,
                         create_mock_rpc=create_default_mock_rpc_plugin):
    icontroldriver = configure_icd(icd_configuration, create_mock_rpc)
    start_registry = register_device(bigip)
    return icontroldriver, start_registry


@pytest.fixture
def vcmp_setup(request):
    def remove_vlan():
        for host in hosts:
            host['guest'].refresh()
            test_vlan = 'vlan-1-1-46'
            # Disassociate VLAN with Guest
            if hasattr(host['guest'], 'vlans') and \
                    COMMON_VLAN in host['guest'].vlans:
                host['guest'].modify(
                    vlans=host['guest'].vlans.remove(COMMON_VLAN))
            # Remove VLAN from Host entirely
            if host['bigip'].tm.net.vlans.vlan.exists(
                    name=test_vlan, partition='Common'):
                v = host['bigip'].tm.net.vlans.vlan.load(
                    name=test_vlan, partition='Common')
                v.delete()
    hosts = []
    # Set bigip1 as first in list to use for tests that do not require
    # multiple hosts
    vcmp_hosts = [pytest.symbols.icontrol_vcmp_host1,
                  pytest.symbols.icontrol_vcmp_host2]
    for vcmp in vcmp_hosts:
        host = ManagementRoot(
            vcmp['host_ip'],
            pytest.symbols.icontrol_username,
            pytest.symbols.icontrol_password
        )
        guest = host.tm.vcmp.guests.guest.load(name=vcmp['guest_name'])
        hosts.append({'bigip': host, 'guest': guest})
    request.addfinalizer(remove_vlan)
    return hosts


def test_vcmp_createlb(setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    vcmp_host = vcmp_setup
    icontroldriver, start_registry = handle_init_registry(bigip, VCMP_CONFIG)
    service = deepcopy(CREATELB)
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == set(vcmp_uris['vcmp_lb_uris'])
    rpc = icontroldriver.plugin_rpc
    assert rpc.get_port_by_name.call_args_list == \
        [call(port_name=u'local-bigip-12.0.int.lineratesystems.com-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20_0')]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    # Since the loadbalancer was not deleted via a service object, we should
    # have a leftover VLAN on the vCMP host and the VLAN should be associated
    # with the guest, and the VLAN from within the guest should be there
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    vcmp_host[0]['guest'].refresh()
    assert COMMON_VLAN in vcmp_host[0]['guest'].vlans
    assert vcmp_host[0]['bigip'].tm.net.vlans.vlan.exists(
        name='vlan-1-1-46', partition='Common')


def test_vcmp_deletelb(setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    vcmp_host = vcmp_setup
    icontroldriver, start_registry = handle_init_registry(bigip, VCMP_CONFIG)
    service = deepcopy(CREATELB)
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == set(vcmp_uris['vcmp_lb_uris'])
    rpc = icontroldriver.plugin_rpc
    assert rpc.get_port_by_name.call_args_list == \
        [call(port_name=u'local-bigip-12.0.int.lineratesystems.com-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20_0')]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            deepcopy(DELETELB),
            delete_partition=True)
    # After the deletelb is called above, the vcmp guest should no longer
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN not in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    vcmp_host[0]['guest'].refresh()
    assert not hasattr(vcmp_host[0]['guest'], 'vlans')
    assert not vcmp_host[0]['bigip'].tm.net.vlans.vlan.exists(
        name='vlan-1-1-46', partition='Common')


def test_vcmp_create_listener(
        setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    vcmp_host = vcmp_setup
    icontroldriver, start_registry = handle_init_registry(bigip, VCMP_CONFIG)
    service = deepcopy(CREATELISTENER)
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == (
        set(vcmp_uris['vcmp_lb_uris']) | set(vcmp_uris['vcmp_listener_uris']))
    rpc = icontroldriver.plugin_rpc
    assert rpc.get_port_by_name.call_args_list == \
        [call(port_name=u'local-bigip-12.0.int.lineratesystems.com-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20_0')]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    vcmp_host[0]['guest'].refresh()
    assert COMMON_VLAN in vcmp_host[0]['guest'].vlans
    assert vcmp_host[0]['bigip'].tm.net.vlans.vlan.exists(
        name='vlan-1-1-46', partition='Common')


def test_vcmp_delete_listener(
        setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    vcmp_host = vcmp_setup
    icontroldriver, start_registry = handle_init_registry(bigip, VCMP_CONFIG)
    service = deepcopy(CREATELISTENER)
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == (
        set(vcmp_uris['vcmp_lb_uris']) | set(vcmp_uris['vcmp_listener_uris']))
    rpc = icontroldriver.plugin_rpc
    assert rpc.get_port_by_name.call_args_list == \
        [call(port_name=u'local-bigip-12.0.int.lineratesystems.com-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20_0')]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
    # Delete the listener, then delete the loadbalancer
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            deepcopy(DELETELISTENER))
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            deepcopy(DELETELB),
            delete_partition=True)

    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN not in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    vcmp_host[0]['guest'].refresh()
    assert not hasattr(vcmp_host[0]['guest'], 'vlans')
    assert vcmp_host[0]['bigip'].tm.net.vlans.vlan.exists(
        name='vlan-1-1-46', partition='Common') is False


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
            'ClusterManager')
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG')
def test_vcmp_clustered_guests(
        mock_log, mock_cm, setup_bigip_devices,
        bigip, bigip2, vcmp_setup, vcmp_uris):
    mock_cm_obj = mock.MagicMock()
    mock_cm_obj.get_traffic_groups.return_value = ['traffic-group-1']
    mock_cm_obj.get_device_name.side_effect = ['bigip-12.0', 'bigip2-12.0']
    mock_cm.return_value = mock_cm_obj
    vcmp_hosts = vcmp_setup
    icontroldriver1, before1 = handle_init_registry(
        bigip, VCMP_CLUSTER_CONFIG)
    service = deepcopy(CREATELB)
    logcall(setup_bigip_devices,
            icontroldriver1._common_service_handler,
            service)
    # Make sure the calls we expect to see in the log are there for each host
    assert call('VcmpManager::_check_vcmp_host_assignments Check registered '
                'bigips to ensure vCMP Guests have a vCMP host assignment') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::_check_vcmp_host_assignments vCMP host found for'
                ' Guest 10.190.5.187') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::_check_vcmp_host_assignments vCMP host found for'
                ' Guest 10.190.5.184') in \
        mock_log.debug.call_args_list
    assert call(u'VcmpManager::_init_vcmp_hosts: vCMPHost[10.190.5.185] '
                'vCMPGuest[bigip-12.0] - mgmt: 10.190.5.187') in \
        mock_log.debug.call_args_list
    assert call(u'VcmpManager::_init_vcmp_hosts: vCMPHost[10.190.5.186] '
                'vCMPGuest[bigip2-12.0] - mgmt: 10.190.5.184') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::_check_guest_vlans: VLAN /Common/vlan-1-1-46 is '
                'not associated with guest bigip-12.0') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Associated VLAN '
                'vlan-1-1-46 with vCMP Guest bigip-12.0') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: VLAN /Common/vlan'
                '-1-1-46 exists on vCMP Guest bigip-12.0.') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Deleted VLAN '
                '/Common/vlan-1-1-46 from vCMP Guest bigip-12.0') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::_check_guest_vlans: VLAN /Common/vlan-1-1-46 '
                'is not associated with guest bigip2-12.0') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Associated VLAN '
                'vlan-1-1-46 with vCMP Guest bigip2-12.0') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: VLAN /Common/vlan-1'
                '-1-46 exists on vCMP Guest bigip2-12.0.') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Deleted VLAN '
                '/Common/vlan-1-1-46 from vCMP Guest bigip2-12.0') in \
        mock_log.debug.call_args_list
    # Before we delete the lb, ensure the hosts and guests have the
    # VLANs needed
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    bigip2_vlans = [v.fullPath for v in bigip2.tm.net.vlans.get_collection()]
    assert GUEST_VLAN in bigip2_vlans
    assert COMMON_VLAN not in bigip2_vlans
    for host in vcmp_hosts:
        host['guest'].refresh()
        assert hasattr(host['guest'], 'vlans')
        assert host['bigip'].tm.net.vlans.vlan.exists(
            name='vlan-1-1-46', partition='Common')
    logcall(setup_bigip_devices,
            icontroldriver1._common_service_handler,
            deepcopy(DELETELB),
            delete_partition=True)
    # After the deletelb is called above, the vcmp guest should no longer
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN not in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    for host in vcmp_hosts:
        host['guest'].refresh()
        assert hasattr(host['guest'], 'vlans') is False
        assert host['bigip'].tm.net.vlans.vlan.exists(
            name='vlan-1-1-46', partition='Common') is False


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
            'ClusterManager')
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG')
def test_vcmp_clustered_guests_more_hosts_than_guests(
        mock_log, mock_cm, setup_bigip_devices,
        bigip, bigip2, vcmp_setup, vcmp_uris):
    mock_cm_obj = mock.MagicMock()
    mock_cm_obj.get_traffic_groups.return_value = ['traffic-group-1']
    mock_cm_obj.get_device_name.side_effect = ['bigip-12.0', 'bigip2-12.0']
    mock_cm.return_value = mock_cm_obj
    copy_config = deepcopy(VCMP_CLUSTER_CONFIG)
    old_vcmp_hosts = copy_config['icontrol_vcmp_hostname']
    # Make the vcmp hosts in the config have additional connectable bigips,
    # but those extras are copied from the guests in icontrol_hostnames.
    # So let's make sure we get a failure to initialize a vcmp host.
    copy_config['icontrol_vcmp_hostname'] = old_vcmp_hosts + ',' + \
        copy_config['icontrol_hostname']
    with pytest.raises(BigIPNotLicensedForVcmp) as ex:
        icontroldriver1, before1 = handle_init_registry(
            bigip, copy_config)
    assert 'VcmpManager::_init_vcmp_hosts: Given vCMP host 10.190.5.187 ' \
        'is not licensed for vCMP.' in ex.value.message
