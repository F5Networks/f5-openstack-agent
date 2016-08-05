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
from mock import call
import pytest
import requests
import time

from f5.utils.testutils.registrytools import register_device
requests.packages.urllib3.disable_warnings()


from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver

import logging

# Toggle feature on/off configurations
OSLO_CONFIGS = json.load(open('oslo_confs.json'))
FEATURE_ON = OSLO_CONFIGS["feature_on"]
FEATURE_OFF = OSLO_CONFIGS["feature_off"]


# LIbrary of services as received from the neutron server
NEUTRON_SERVICES = json.load(open('neutron_services.json'))
SEGID_CREATELB = NEUTRON_SERVICES["create_connected_loadbalancer"]
NOSEGID_CREATELB = NEUTRON_SERVICES["create_disconnected_loadbalancer"]
SEGID_CREATELISTENER = NEUTRON_SERVICES["create_connected_listener"]
NOSEGID_CREATELISTENER = NEUTRON_SERVICES["create_disconnected_listener"]

# BigIP device states observed via f5sdk.
AGENT_INIT_URIS = \
    set([u'https://localhost/mgmt/tm/net/tunnels/vxlan/'
         '~Common~vxlan_ovs?ver=11.6.0',

         'https://localhost/mgmt/tm/net/tunnels/gre/'
         '~Common~gre_ovs?ver=11.6.0'])

SEG_INDEPENDENT_LB_URIS =\
    set([u'https://localhost/mgmt/tm/sys/folder/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/route-domain/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver=11.5.0',

         'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver=11.6.0'])

SEG_DEPENDENT_LB_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/snat-translation/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~snat-traffic-group-local-only'
         '-ce69e293-56e7-43b8-b51c-01b91d66af20_0?ver=11.6.0',

         u'https://localhost/mgmt/tm/ltm/snatpool/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d~tunnel-vxlan-46?ver=11.5.0',

         u'https://localhost/mgmt/tm/net/self/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~tunnel-vxlan-46?ver=11.6.0'])

LISTENER_SPECIFIC_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/virtual-address/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~10.2.2.140%251?ver=11.6.0',

         u'https://localhost/mgmt/tm/ltm/virtual/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~SAMPLE_LISTENER?ver=11.6.0'])


def configure_icd(icd_config):
    class ConfFake(object):
        '''minimal fake config object to replace oslo with controlled params'''
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
    mock_rpc_plugin.get_port_by_name.return_value =\
        [{'fixed_ips': [{'ip_address': '10.2.2.134'}]}]
    icontroldriver = iControlDriver(ConfFake(icd_config),
                                    registerOpts=False)
    icontroldriver.plugin_rpc = mock_rpc_plugin
    return icontroldriver


def logcall(lh, call, *cargs, **ckwargs):
    lh.setLevel(logging.DEBUG)
    call(*cargs, **ckwargs)
    lh.setLevel(logging.NOTSET)


def handle_init_registry(bigip, icd_configuration):
    init_registry = register_device(bigip)
    icontroldriver = configure_icd(icd_configuration)
    start_registry = register_device(bigip)
    assert set(start_registry.keys()) - set(init_registry.keys()) ==\
        AGENT_INIT_URIS
    return icontroldriver, start_registry


@pytest.mark.skip(reason="Fails because it's possible the agent should report"
                  " operating_status as OFFLINE.")
def test_featureoff_withsegid_lb(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            SEGID_CREATELB)
    after_create_registry = register_device(bigip)
    create_uris = set(after_create_registry.keys()) -\
        set(start_registry.keys())
    assert create_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert 'MISCONFIGURATION' not in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.get_port_by_name.call_args_list ==\
        [call(port_name=u'local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-'
         'ce69e293-56e7-43b8-b51c-01b91d66af20_0')]
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ACTIVE',
            'OFFLINE')]


def test_withsegid_lb(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            SEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert 'MISCONFIGURATION' not in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.get_port_by_name.call_args_list ==\
        [call(port_name=u'local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-'
         'ce69e293-56e7-43b8-b51c-01b91d66af20_0')]
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ACTIVE',
            'OFFLINE')]


def test_featureoff_withsegid_listener(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            SEGID_CREATELISTENER)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris ==\
        SEG_INDEPENDENT_LB_URIS |\
        SEG_DEPENDENT_LB_URIS |\
        LISTENER_SPECIFIC_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert 'MISCONFIGURATION' not in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.get_port_by_name.call_args_list ==\
        [call(port_name=u'local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-'
         'ce69e293-56e7-43b8-b51c-01b91d66af20_0')]
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ACTIVE',
            'ONLINE')]
    assert icontroldriver.plugin_rpc.\
        update_listener_status.call_args_list ==\
        [call.update_listener_status(
            u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
            'ACTIVE',
            'ONLINE')]


@pytest.mark.skip(reason='Fails until an appropriate log message is written'
                  ' and a correct update is sent to neutron.')
def test_featureoff_nosegid_lb(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            NOSEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert 'MISCONFIGURATION' in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ERROR',
            'OFFLINE')]


@pytest.mark.skip(reason='Fails until an appropriate log message is written'
                  ' and a correct update is sent to neutron.')
def test_featureoff_nosegid_listener(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            NOSEGID_CREATELISTENER)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS | LISTENER_SPECIFIC_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert 'MISCONFIGURATION' in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ERROR',
            'OFFLINE')]
    assert icontroldriver.plugin_rpc.\
        update_listener_status.call_args_list ==\
        [call.update_listener_status(
            u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
            'ERROR',
            'OFFLINE')]


@pytest.mark.skip(reason="fails until vxlan-none bug is fixed and rpc calls"
                  " are validated.")
def test_withsegid_listener(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            SEGID_CREATELISTENER)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris ==\
        SEG_INDEPENDENT_LB_URIS |\
        SEG_DEPENDENT_LB_URIS |\
        LISTENER_SPECIFIC_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert 'MISCONFIGURATION' not in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.get_port_by_name.call_args_list ==\
        [call(port_name=u'local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20'),
         call(port_name=u'snat-traffic-group-local-only-'
         'ce69e293-56e7-43b8-b51c-01b91d66af20_0')]
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ACTIVE',
            'ONLINE')]
    assert icontroldriver.plugin_rpc.\
        update_listener_status.call_args_list ==\
        [call.update_listener_status(
            u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
            'ACTIVE',
            'ONLINE')]


@pytest.mark.skip(reason="Fails until rpc call is validated.")
def test_nosegid_lb(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            NOSEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert 'MISCONFIGURATION' not in open(logfilename).read()
    print(icontroldriver.plugin_rpc.method_calls)
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ACTIVE',
            'OFFLINE')]


@pytest.mark.skip(reason="fails until vxlan-none bug is fixed and appropriate"
                  " update_listener_status rpc call is validated")
def test_nosegid_listener(setup_neutronless_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            NOSEGID_CREATELISTENER)
    after_create_registry = register_device(bigip)
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert 'MISCONFIGURATION' not in open(logfilename).read()
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS | LISTENER_SPECIFIC_URIS
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list ==\
        [call.update_loadbalancer_status(
            u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
            'ACTIVE',
            'OFFLINE')]
    assert icontroldriver.plugin_rpc.\
        update_listener_status.call_args_list ==\
        [call.update_listener_status(
            u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
            'ACTIVE',
            'OFFLINE')]


@pytest.mark.skip(reason="fails until vxlan-none bug is fixed and appropriate"
                  " update_listener_status rpc call is validated")
def test_nosegid_listener_timeout(setup_neutronless_test, bigip):
    # Configure
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    gtimeout = icontroldriver.conf.f5_network_segment_gross_timeout
    poll_interval = icontroldriver.conf.f5_network_segment_polling_interval
    # Set timers
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            NOSEGID_CREATELB)
    start_time = time.time()
    timeout = start_time + gtimeout
    # Begin operations
    while time.time() < (timeout + (2*poll_interval)):
        time.sleep(poll_interval)
        logcall(setup_neutronless_test,
                icontroldriver._common_service_handler,
                NOSEGID_CREATELISTENER)
        create_registry = register_device(bigip)
        new_uris = set(create_registry.keys()) - set(start_registry.keys())
        assert new_uris == SEG_INDEPENDENT_LB_URIS | LISTENER_SPECIFIC_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert "TIMEOUT: failed to connect " in open(logfilename).read()

    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list == [
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ACTIVE',
                'OFFLINE'),
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ACTIVE',
                'OFFLINE'),
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ACTIVE',
                'OFFLINE'),
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ERROR',
                'OFFLINE')]
    assert icontroldriver.plugin_rpc.\
        update_listener_status.call_args_list == [
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ACTIVE',
                'OFFLINE'),
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ACTIVE',
                'OFFLINE'),
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ACTIVE',
                'OFFLINE'),
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ERROR',
                'OFFLINE')]


@pytest.mark.skip(reason="fails until vxlan-none bug is fixed and appropriate"
                  " update_listener_status rpc call is validated")
def test_nosegid_to_segid(setup_neutronless_test, bigip):
    # Configure
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    gtimeout = icontroldriver.conf.f5_network_segment_gross_timeout
    poll_interval = icontroldriver.conf.f5_network_segment_polling_interval
    # Set timers
    start_time = time.time()
    timeout = start_time + gtimeout
    # Begin operations
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            NOSEGID_CREATELB)
    while time.time() < (timeout - (2*poll_interval)):
        time.sleep(poll_interval)
        logcall(setup_neutronless_test,
                icontroldriver._common_service_handler,
                NOSEGID_CREATELISTENER)
        create_registry = register_device(bigip)
        new_uris = set(create_registry.keys()) - set(start_registry.keys())
        assert new_uris == SEG_INDEPENDENT_LB_URIS
    # Before gtimeout
    time.sleep(poll_interval)
    logcall(setup_neutronless_test,
            icontroldriver._common_service_handler,
            SEGID_CREATELISTENER)
    create_registry = register_device(bigip)
    new_uris = set(create_registry.keys()) - set(start_registry.keys())

    print(icontroldriver.plugin_rpc.method_calls)
    assert new_uris ==\
        SEG_INDEPENDENT_LB_URIS |\
        SEG_DEPENDENT_LB_URIS |\
        LISTENER_SPECIFIC_URIS
    logfilename = setup_neutronless_test.baseFilename
    assert "Failed to create vxlan tunnel: tunnel-vxlan-None"\
        not in open(logfilename).read()
    assert icontroldriver.plugin_rpc.\
        update_loadbalancer_status.call_args_list == [
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ACTIVE',
                'OFFLINE'),
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ACTIVE',
                'OFFLINE'),
            call.update_loadbalancer_status(
                u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
                'ACTIVE',
                'ONLINE')]
    assert icontroldriver.plugin_rpc.\
        update_listener_status.call_args_list == [
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ACTIVE',
                'OFFLINE'),
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ACTIVE',
                'OFFLINE'),
            call.update_listener_status(
                u'105a227a-cdbf-4ce3-844c-9ebedec849e9',
                'ACTIVE',
                'ONLINE')]
