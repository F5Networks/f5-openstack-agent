# Copyright (c) 2016-2018, F5 Networks, Inc.
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

GUEST_VLAN = '/TEST_128a63ef33bc4cf891d684fad58e7f2d/vlan-46'
COMMON_VLAN = '/Common/vlan-46'

# Library of services as received from the neutron server
NEUTRON_SERVICES = json.load(open(os.path.join(
    curdir, 'vcmp_neutron_services.json')))
CREATELB = NEUTRON_SERVICES["create_lb"]
DELETELB = NEUTRON_SERVICES["delete_lb"]
CREATELISTENER = NEUTRON_SERVICES["create_listener"]
DELETELISTENER = NEUTRON_SERVICES["delete_listener"]
CREATELISTENER_FLAT = NEUTRON_SERVICES["create_listener_flat"]
DELETELISTENER_FLAT = NEUTRON_SERVICES["delete_listener_flat"]


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
            test_vlan = 'vlan-46'
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


@pytest.fixture
def mgmt_vlan(request, vcmp_setup):
    hosts = vcmp_setup
    host1 = hosts[0]['bigip']
    host1.tm.refresh()
    guest1 = hosts[0]['guest']
    guest1.refresh()

    def remove_mgmt_vlan():
        host1.tm.refresh()
        guest1.refresh()
        vlans = guest1.vlans
        vlans.remove('/Common/mgmt_vlan')
        guest1.modify(vlans=vlans)
        mgmt_vlan = host1.tm.net.vlans.vlan.load(
            name='mgmt_vlan', partition='Common')
        mgmt_vlan.delete()

    host1.tm.net.vlans.vlan.create(
        name='mgmt_vlan', partition='Common')
    guest1.modify(vlans=['/Common/mgmt_vlan'])
    request.addfinalizer(remove_mgmt_vlan)


def check_host_and_guest_vlans_on_delete(vcmp_host, bigip):
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN not in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    vcmp_host['guest'].refresh()
    assert vcmp_host['bigip'].tm.net.vlans.vlan.exists(
        name='vlan-46', partition='Common') is False
    assert bigip.tm.sys.folders.folder.exists(
        name='TEST_128a63ef33bc4cf891d684fad58e7f2d') is False


def check_host_and_guest_vlans_on_create(vcmp_host, bigip):
    bigip_vlans = [v.fullPath for v in bigip.tm.net.vlans.get_collection()]
    assert GUEST_VLAN in bigip_vlans
    assert COMMON_VLAN not in bigip_vlans
    vcmp_host['guest'].refresh()
    assert COMMON_VLAN in vcmp_host['guest'].vlans
    assert vcmp_host['bigip'].tm.net.vlans.vlan.exists(
        name='vlan-46', partition='Common')


def test_vcmp_createlb(track_bigip_cfg, setup_bigip_devices, bigip, vcmp_setup,
                       vcmp_uris):
    '''Create lb with vcmp turned on.'''

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
        [call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c'
              '-01b91d66af20'.format(
                  pytest.symbols.icontrol_vcmp_host1['guest_hostname'])),
         call(port_name=u'snat-traffic-group-local-only-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20_0')]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    # Since the loadbalancer was not deleted via a service object, we should
    # have a leftover VLAN on the vCMP host and the VLAN should be associated
    # with the guest, and the VLAN from within the guest should be there
    check_host_and_guest_vlans_on_create(vcmp_host[0], bigip)


def test_vcmp_deletelb(track_bigip_cfg, setup_bigip_devices, bigip, vcmp_setup,
                       vcmp_uris):
    '''Create and delete lb with vcmp turned on.'''

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
        [call(port_name=u'local-{}-ce69e293-56e7-43b8-'
              'b51c-01b91d66af20'.format(
                  pytest.symbols.icontrol_vcmp_host1['guest_hostname'])),
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
    # have the vlan attached
    check_host_and_guest_vlans_on_delete(vcmp_host[0], bigip)
    assert not hasattr(vcmp_host[0]['guest'], 'vlans')


def test_vcmp_deletelb_with_mgmt_vlan(
        track_bigip_cfg, setup_bigip_devices, bigip, vcmp_setup, vcmp_uris,
        mgmt_vlan):
    '''Create and delete lb with vcmp turned on and mgmt vlan exists.

    We need to ensure a pre-existing management vlan, which is associated
    with the guest outside of the agent's control, actually stays associated
    once the last loadbalancer is torn down.
    '''

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
        [call(port_name=u'local-{}-ce69e293-56e7-43b8-'
              'b51c-01b91d66af20'.format(
                  pytest.symbols.icontrol_vcmp_host1['guest_hostname'])),
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
    # have vlan-46
    check_host_and_guest_vlans_on_delete(vcmp_host[0], bigip)
    # mgmt_vlan should remain associated with guest
    assert vcmp_host[0]['guest'].vlans == ['/Common/mgmt_vlan']


def test_vcmp_create_listener(
        track_bigip_cfg, setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    '''Create listener with vcmp turned on.'''

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
        [call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c'
              '-01b91d66af20'.format(
                  pytest.symbols.icontrol_vcmp_host1['guest_hostname'])),
         call(port_name=u'snat-traffic-group-local-only-ce69e293-'
              '56e7-43b8-b51c-01b91d66af20_0')]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
    check_host_and_guest_vlans_on_create(vcmp_host[0], bigip)


def test_vcmp_delete_listener(
        track_bigip_cfg, setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    '''Create and delete listener with vcmp turned on.'''

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
        [call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c-'
              '01b91d66af20'.format(
                  pytest.symbols.icontrol_vcmp_host1['guest_hostname'])),
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
    check_host_and_guest_vlans_on_delete(vcmp_host[0], bigip)
    assert not hasattr(vcmp_host[0]['guest'], 'vlans')


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
            'ClusterManager')
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG')
def test_vcmp_clustered_guests(
        track_bigip_cfg, mock_log, mock_cm, setup_bigip_devices,
        bigip, bigip2, vcmp_setup, vcmp_uris):
    '''Test creation of lb with guests clustered across hosts.'''

    mock_cm_obj = mock.MagicMock()
    mock_cm_obj.get_traffic_groups.return_value = ['traffic-group-1']
    mock_cm_obj.get_device_name.side_effect = [
        pytest.symbols.icontrol_vcmp_host1['guest_name'],
        pytest.symbols.icontrol_vcmp_host2['guest_name']
    ]
    mock_cm.return_value = mock_cm_obj
    vcmp_hosts = vcmp_setup
    icontroldriver1, before1 = handle_init_registry(
        bigip, VCMP_CLUSTER_CONFIG)
    service = deepcopy(CREATELB)
    logcall(setup_bigip_devices,
            icontroldriver1._common_service_handler,
            service)
    # Make sure guests are associated with their respective hosts
    assert call('VcmpManager::_check_vcmp_host_assignments Check registered '
                'bigips to ensure vCMP Guests have a vCMP host assignment') in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::_check_vcmp_host_assignments vCMP host found for'
                ' Guest {}'.format(pytest.symbols.bigip_ip)) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::_check_vcmp_host_assignments vCMP host found for'
                ' Guest {}'.format(pytest.symbols.bigip2_ip)) in \
        mock_log.debug.call_args_list
    assert call(u'VcmpManager::_init_vcmp_hosts: vCMPHost[{0}] '
                'vCMPGuest[{1}] - mgmt: {2}'.format(
                    pytest.symbols.icontrol_vcmp_host1['host_ip'],
                    pytest.symbols.icontrol_vcmp_host1['guest_name'],
                    pytest.symbols.bigip_ip)) in \
        mock_log.debug.call_args_list
    assert call(u'VcmpManager::_init_vcmp_hosts: vCMPHost[{0}] '
                'vCMPGuest[{1}] - mgmt: {2}'.format(
                    pytest.symbols.icontrol_vcmp_host2['host_ip'],
                    pytest.symbols.icontrol_vcmp_host2['guest_name'],
                    pytest.symbols.bigip2_ip)) in \
        mock_log.debug.call_args_list
    # Check VLAN on first host and guest
    assert call('VcmpManager::_check_guest_vlans: VLAN /Common/vlan-46 is '
                'not associated with guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host1['guest_name'])) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Associated VLAN '
                'vlan-46 with vCMP Guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host1['guest_name'])) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: VLAN /Common/vlan'
                '-46 exists on vCMP Guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host1['guest_name'])) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Deleted VLAN '
                '/Common/vlan-46 from vCMP Guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host1['guest_name'])) in \
        mock_log.debug.call_args_list
    # Check VLAN on second host and guest
    assert call('VcmpManager::_check_guest_vlans: VLAN /Common/vlan-46 is '
                'not associated with guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host2['guest_name'])) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Associated VLAN '
                'vlan-46 with vCMP Guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host2['guest_name'])) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: VLAN /Common/vlan'
                '-46 exists on vCMP Guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host2['guest_name'])) in \
        mock_log.debug.call_args_list
    assert call('VcmpManager::assoc_vlan_with_vcmp_guest: Deleted VLAN '
                '/Common/vlan-46 from vCMP Guest {}'.format(
                    pytest.symbols.icontrol_vcmp_host2['guest_name'])) in \
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
            name='vlan-46', partition='Common')
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
            name='vlan-46', partition='Common') is False


@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver.'
            'ClusterManager')
@mock.patch('f5_openstack_agent.lbaasv2.drivers.bigip.vcmp.LOG')
def test_vcmp_clustered_guests_more_hosts_than_guests(
        track_bigip_cfg, mock_log, mock_cm, setup_bigip_devices, bigip, bigip2,
        vcmp_setup, vcmp_uris):
    '''Exception should raise when given host that is not licensed for vcmp.'''

    mock_cm_obj = mock.MagicMock()
    mock_cm_obj.get_traffic_groups.return_value = ['traffic-group-1']
    mock_cm_obj.get_device_name.side_effect = [
        pytest.symbols.icontrol_vcmp_host1['guest_name'],
        pytest.symbols.icontrol_vcmp_host2['guest_name']
    ]
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
    assert 'VcmpManager::_init_vcmp_hosts: Given vCMP host {} ' \
        'is not licensed for vCMP.'.format(
            pytest.symbols.bigip_ip) in ex.value.message


def test_vcmp_delete_listener_flat(
        track_bigip_cfg, setup_bigip_devices, bigip, vcmp_setup, vcmp_uris):
    '''Create listener with vcmp turned on and flat as network type.'''

    vcmp_host = vcmp_setup
    icontroldriver, start_registry = handle_init_registry(bigip, VCMP_CONFIG)
    service = deepcopy(CREATELISTENER_FLAT)
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
        [call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c-'
              '01b91d66af20'.format(
                  pytest.symbols.icontrol_vcmp_host1['guest_hostname'])),
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
            deepcopy(DELETELISTENER_FLAT))
    logcall(setup_bigip_devices,
            icontroldriver._common_service_handler,
            deepcopy(DELETELB),
            delete_partition=True)
    check_host_and_guest_vlans_on_delete(vcmp_host[0], bigip)
    assert not hasattr(vcmp_host[0]['guest'], 'vlans')
