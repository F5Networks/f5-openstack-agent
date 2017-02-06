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


from conftest import remove_elements
from conftest import setup_neutronless_test
from copy import deepcopy
from f5.bigip import ManagementRoot
from f5.utils.testutils.registrytools import register_device
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
import json
import logging
import mock
from mock import call
import os
from os.path import dirname as osd
import pytest
import requests
import time

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

oslo_config_filename =\
    os.path.join(osd(os.path.abspath(__file__)), 'oslo_confs.json')
# Toggle feature on/off configurations
OSLO_CONFIGS = json.load(open(oslo_config_filename))
FEATURE_ON = OSLO_CONFIGS["feature_on"]
FEATURE_OFF = OSLO_CONFIGS["feature_off"]
FEATURE_OFF_GRM = OSLO_CONFIGS["feature_off_grm"]
FEATURE_OFF_COMMON_NET = OSLO_CONFIGS["feature_off_common_net"]
FEATURE_ON['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
FEATURE_OFF['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
FEATURE_OFF_GRM['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
FEATURE_OFF_COMMON_NET['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public


tmos_version = ManagementRoot(
                   pytest.symbols.bigip_mgmt_ip_public,
                   pytest.symbols.bigip_username,
                   pytest.symbols.bigip_password
               ).tmos_version
dashed_mgmt_ip = pytest.symbols.bigip_mgmt_ip_public.replace('.', '-')
icontrol_fqdn = 'host-' + dashed_mgmt_ip + '.openstacklocal'
if tmos_version == '12.1.0':
    icontrol_fqdn = 'bigip1'
neutron_services_filename =\
    os.path.join(osd(os.path.abspath(__file__)), 'neutron_services.json')
# Library of services as received from the neutron server
NEUTRON_SERVICES = json.load(open(neutron_services_filename))
SEGID_CREATELB = NEUTRON_SERVICES["create_connected_loadbalancer"]
SEGID_DELETELB = NEUTRON_SERVICES["delete_loadbalancer"]
NOSEGID_CREATELB = NEUTRON_SERVICES["create_disconnected_loadbalancer"]
SEGID_CREATELISTENER = NEUTRON_SERVICES["create_connected_listener"]
NOSEGID_CREATELISTENER = NEUTRON_SERVICES["create_disconnected_listener"]

# BigIP device states observed via f5sdk.
AGENT_INIT_URIS = \
    set([u'https://localhost/mgmt/tm/net/tunnels/vxlan/'
         '~Common~vxlan_ovs?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/tunnels/gre/'
         '~Common~gre_ovs?ver='+tmos_version])

SEG_INDEPENDENT_LB_URIS =\
    set([u'https://localhost/mgmt/tm/sys/folder/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/route-domain/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver=11.5.0',

         u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver='+tmos_version])

SEG_INDEPENDENT_LB_URIS_GRM =\
    set([u'https://localhost/mgmt/tm/sys/folder/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver=11.5.0',

         u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver='+tmos_version])

SEG_DEPENDENT_LB_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/snat-translation/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~snat-traffic-group-local-only'
         '-ce69e293-56e7-43b8-b51c-01b91d66af20_0?ver='+tmos_version,

         u'https://localhost/mgmt/tm/ltm/snatpool/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d~tunnel-vxlan-46?ver=11.5.0',

         u'https://localhost/mgmt/tm/net/self/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~local-' + icontrol_fqdn + '-ce69e293-56e7-43b8-b51c-01b91d66af20?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~tunnel-vxlan-46?ver='+tmos_version,

         u'https://localhost/mgmt/tm/ltm/virtual-address/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_50c5d54a-5a9e-4a80-9e74-8400a461a077?ver='+tmos_version])

SEG_INDEPENDENT_LB_URIS_COMMON_NET =\
    set([u'https://localhost/mgmt/tm/ltm/snat-translation/'
         '~Common'
         '~snat-traffic-group-local-only'
         '-ce69e293-56e7-43b8-b51c-01b91d66af20_0?ver='+tmos_version,

         u'https://localhost/mgmt/tm/ltm/snatpool/'
         '~Common'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver='+tmos_version,

         u'https://localhost/mgmt/tm/net/self/'
         '~Common'
         '~local-' + icontrol_fqdn + '-ce69e293-56e7-43b8-b51c-01b91d66af20?ver='+tmos_version,

         u'https://localhost/mgmt/tm/ltm/virtual-address/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_50c5d54a-5a9e-4a80-9e74-8400a461a077?ver='+tmos_version])

SEG_LISTENER_URIS = \
    set([u'https://localhost/mgmt/tm/ltm/virtual/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_105a227a-cdbf-4ce3-844c-9ebedec849e9?ver='+tmos_version])

NOSEG_LB_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/virtual-address/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_50c5d54a-5a9e-4a80-9e74-8400a461a077?ver='+tmos_version])

NOSEG_LISTENER_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/virtual/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_105a227a-cdbf-4ce3-844c-9ebedec849e9?ver='+tmos_version])

ERROR_MSG_MISCONFIG = 'Misconfiguration: Segmentation ID is missing'
ERROR_MSG_VXLAN_TUN = 'Failed to create vxlan tunnel:'
ERROR_MSG_GRE_TUN = 'Failed to create gre tunnel:'
ERROR_MSG_TIMEOUT = 'TIMEOUT: failed to connect '


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


@pytest.fixture
def bigip():
    LOG.debug(pytest.symbols)
    LOG.debug(pytest.symbols.bigip_mgmt_ip_public)
    return ManagementRoot(pytest.symbols.bigip_mgmt_ip_public, 'admin', 'admin')


@pytest.fixture
def setup_l2adjacent_test(request, bigip, makelogdir):
    loghandler = setup_neutronless_test(request, bigip, makelogdir, vlan=True)
    LOG.info('Test setup: %s' % request.node.name)

    # FIXME: This is a work around for GH issue #487
    # https://github.com/F5Networks/f5-openstack-agent/issues/487
    def kill_icontrol():
        time.sleep(2)
    request.addfinalizer(kill_icontrol)

    try:
        remove_elements(bigip,
                        SEG_INDEPENDENT_LB_URIS |
                        SEG_DEPENDENT_LB_URIS |
                        SEG_LISTENER_URIS |
                        AGENT_INIT_URIS,
                        vlan=True)
    finally:
        LOG.info('removing pre-existing config')

    return loghandler


def handle_init_registry(bigip, icd_configuration,
                         create_mock_rpc=create_default_mock_rpc_plugin):
    LOG.debug(type(bigip))
    init_registry = register_device(bigip)
    icontroldriver = configure_icd(icd_configuration, create_mock_rpc)
    LOG.debug(bigip.raw)
    start_registry = register_device(bigip)
    if icd_configuration['f5_global_routed_mode'] == False:
        assert set(start_registry.keys()) - set(init_registry.keys()) == \
            AGENT_INIT_URIS
    return icontroldriver, start_registry


def test_featureoff_withsegid_lb(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(SEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.get_port_by_name.call_args_list == [
        call(port_name=u'local-' + icontrol_fqdn + '-ce69e293-56e7-43b8-b51c-01b91d66af20'),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_withsegid_lb(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(SEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.get_port_by_name.call_args_list == [
        call(port_name=u'local-' + icontrol_fqdn + '-ce69e293-56e7-43b8-b51c-01b91d66af20'),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_featureoff_withsegid_listener(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(SEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == (SEG_INDEPENDENT_LB_URIS |
                           SEG_DEPENDENT_LB_URIS |
                           SEG_LISTENER_URIS)
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.get_port_by_name.call_args_list == [
        call(port_name=u'local-' + icontrol_fqdn + '-ce69e293-56e7-43b8-b51c-01b91d66af20'),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]


def test_featureoff_nosegid_lb(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(NOSEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ERROR', 'OFFLINE')
    ]


def test_featureoff_nosegid_listener(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ERROR', 'OFFLINE')
    ]


def test_withsegid_listener(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(SEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == (SEG_INDEPENDENT_LB_URIS |
                           SEG_DEPENDENT_LB_URIS |
                           SEG_LISTENER_URIS)
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.get_port_by_name.call_args_list == [
        call(port_name=u'local-' + icontrol_fqdn + '-ce69e293-56e7-43b8-b51c-01b91d66af20'),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_nosegid_lb(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(NOSEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS | NOSEG_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'OFFLINE')
    ]


def test_nosegid_listener(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == (SEG_INDEPENDENT_LB_URIS | NOSEG_LISTENER_URIS |
                           NOSEG_LB_URIS)
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'OFFLINE')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'OFFLINE')
    ]


def test_nosegid_listener_timeout(setup_l2adjacent_test, bigip):
    def create_mock_rpc_plugin():
        mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
        mock_rpc_plugin.get_port_by_name.return_value = [
            {'fixed_ips': [{'ip_address': '10.2.2.134'}]}
        ]
        mock_rpc_plugin.get_all_loadbalancers.return_value = [
            {'lb_id': u'50c5d54a-5a9e-4a80-9e74-8400a461a077'}
        ]
        service = deepcopy(NOSEGID_CREATELISTENER)
        service['loadbalancer']['provisioning_status'] = "ACTIVE"
        mock_rpc_plugin.get_service_by_loadbalancer_id.return_value = service
        return mock_rpc_plugin
    # Configure
    icontroldriver, start_registry = handle_init_registry(
        bigip, FEATURE_ON, create_mock_rpc_plugin)
    gtimeout = icontroldriver.conf.f5_network_segment_gross_timeout
    poll_interval = icontroldriver.conf.f5_network_segment_polling_interval
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    # Set timers
    start_time = time.time()
    timeout = start_time + gtimeout
    # Begin operations
    while time.time() < (timeout + (2*poll_interval)):
        time.sleep(poll_interval)
        create_registry = register_device(bigip)
        create_uris = set(create_registry.keys()) - set(start_registry.keys())
        assert create_uris == (SEG_INDEPENDENT_LB_URIS | NOSEG_LISTENER_URIS |
                               NOSEG_LB_URIS)
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    assert ERROR_MSG_TIMEOUT in open(logfilename).read()

    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    # check for the expected number of calls to each rpc
    all_list = []
    for rpc_call in rpc.get_all_loadbalancers.call_args_list:
        all_list.append(str(rpc_call))
    assert len(all_list) > gtimeout+1
    one_list = []
    for rpc_call in rpc.get_service_by_loadbalancer_id.call_args_list:
        one_list.append(str(rpc_call))
    assert len(one_list) == gtimeout+1
    # check for the expected number of unique calls to each rpc
    assert len(set(all_list)) == 1
    assert len(set(one_list)) == 1
    # check for the expected status transitions
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'OFFLINE'),
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ERROR', 'OFFLINE')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'OFFLINE'),
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'OFFLINE'),
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ERROR', 'OFFLINE')
    ]


def test_nosegid_to_segid(setup_l2adjacent_test, bigip):
    def create_swing_mock_rpc_plugin():
        # set up mock to return segid after 3 polling attempts
        mock_rpc_plugin = mock.MagicMock(name='swing_mock_rpc_plugin')
        mock_rpc_plugin.get_port_by_name.return_value = [
            {'fixed_ips': [{'ip_address': '10.2.2.134'}]}
        ]
        no_lb = []
        one_lb = [{'lb_id': '50c5d54a-5a9e-4a80-9e74-8400a461a077'}]
        mock_rpc_plugin.get_all_loadbalancers.side_effect = [
            no_lb, no_lb, no_lb, no_lb,
            one_lb, one_lb, one_lb, one_lb, one_lb, one_lb, one_lb, one_lb
        ]
        miss = deepcopy(NOSEGID_CREATELISTENER)
        miss['loadbalancer']['provisioning_status'] = "ACTIVE"
        hit = deepcopy(SEGID_CREATELISTENER)
        hit['loadbalancer']['provisioning_status'] = "ACTIVE"
        mock_rpc_plugin.get_service_by_loadbalancer_id.side_effect = [
            miss, deepcopy(miss), deepcopy(miss),
            hit, deepcopy(hit), deepcopy(hit), deepcopy(hit), deepcopy(hit),
            deepcopy(hit), deepcopy(hit), deepcopy(hit), deepcopy(hit)
        ]
        return mock_rpc_plugin
    # Configure
    icontroldriver, start_registry = handle_init_registry(
        bigip, FEATURE_ON, create_swing_mock_rpc_plugin)
    gtimeout = icontroldriver.conf.f5_network_segment_gross_timeout
    # Begin operations
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    # Before gtimeout
    time.sleep(gtimeout)
    create_registry = register_device(bigip)
    create_uris = set(create_registry.keys()) - set(start_registry.keys())

    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    # check for the expected number of calls to each rpc
    all_list = []
    for rpc_call in rpc.get_all_loadbalancers.call_args_list:
        all_list.append(str(rpc_call))
    assert len(all_list) > gtimeout
    one_list = []
    for rpc_call in rpc.get_service_by_loadbalancer_id.call_args_list:
        one_list.append(str(rpc_call))
    assert len(one_list) >= gtimeout
    # check for the expected number of unique calls to each rpc
    assert len(set(all_list)) == 1
    assert len(set(one_list)) == 1
    assert create_uris == (SEG_INDEPENDENT_LB_URIS |
                           SEG_DEPENDENT_LB_URIS |
                           SEG_LISTENER_URIS)
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_TIMEOUT not in open(logfilename).read()
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    # check that the last status update takes the object online
    assert list(rpc.update_loadbalancer_status.call_args_list)[-1] == (
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    )
    assert rpc.update_listener_status.call_args_list[-1] == (
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    )

def test_featureoff_grm_lb(setup_l2adjacent_test, bigip):
    def create_mock_rpc_plugin():
        mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
        mock_rpc_plugin.get_port_by_name.return_value = [
            {'fixed_ips': [{'ip_address': '10.2.2.134'}]}
        ]
        mock_rpc_plugin.get_all_loadbalancers.return_value = [
            {'lb_id': u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
             'tenant_id': u'128a63ef33bc4cf891d684fad58e7f2d'
            }
        ]
        return mock_rpc_plugin

    icontroldriver, start_registry = handle_init_registry(bigip,
                                                          FEATURE_OFF_GRM,
                                                          create_mock_rpc_plugin)

    service = deepcopy(SEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    empty_set = set()

    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS_GRM | NOSEG_LB_URIS

    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()

    rpc = icontroldriver.plugin_rpc

    service = deepcopy(SEGID_DELETELB)

    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service, True)

    after_destroy_registry = register_device(bigip)    
    post_destroy_uris = (set(after_destroy_registry.keys()) -
                   set(start_registry.keys()))

    assert post_destroy_uris == empty_set

def test_featureoff_nosegid_common_lb_net(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF_COMMON_NET)
    service = deepcopy(NOSEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS_COMMON_NET | \
        SEG_INDEPENDENT_LB_URIS | \
        NOSEG_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert not ERROR_MSG_MISCONFIG in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]

def test_featureoff_nosegid_create_listener_common_lb_net(setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF_COMMON_NET)
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = (set(after_create_registry.keys()) -
                   set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS_COMMON_NET | \
        SEG_INDEPENDENT_LB_URIS | \
        NOSEG_LB_URIS | NOSEG_LISTENER_URIS

    logfilename = setup_l2adjacent_test.baseFilename
    assert not ERROR_MSG_MISCONFIG in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc

    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
