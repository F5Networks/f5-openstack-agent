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


from conftest import remove_elements
from conftest import setup_neutronless_test
from copy import deepcopy
from distutils.version import StrictVersion
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
import re
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
FEATURE_ON['icontrol_hostname'] = pytest.symbols.bigip_floating_ips[0]
FEATURE_OFF['icontrol_hostname'] = pytest.symbols.bigip_floating_ips[0]
FEATURE_OFF_GRM['icontrol_hostname'] = pytest.symbols.bigip_floating_ips[0]
FEATURE_OFF_COMMON_NET['icontrol_hostname'] = \
    pytest.symbols.bigip_floating_ips[0]
FEATURE_ON['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name
FEATURE_OFF['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name
FEATURE_OFF_GRM['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name
FEATURE_OFF_COMMON_NET['f5_vtep_selfip_name'] = \
    pytest.symbols.f5_vtep_selfip_name


tmos_version = ManagementRoot(
    pytest.symbols.bigip_floating_ips[0],
    pytest.symbols.bigip_username,
    pytest.symbols.bigip_password).tmos_version
# Note, BIG-IP generates selfip based upon the net it is on (172), not the
# public net (10)...  This is based upon testenv.
mgmt_ip = pytest.symbols.bigip_mgmt_ips[0]
icontrol_fqdn = 'host-' + mgmt_ip + '.openstacklocal'
if StrictVersion(tmos_version) >= StrictVersion('12.1.0'):
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
class UrlNames():
    """A convenient label library that provides common URL names"""
    # Neutron-based names used...
    tenant_id = u'128a63ef33bc4cf891d684fad58e7f2d'
    loadbalancer_id = u'50c5d54a-5a9e-4a80-9e74-8400a461a077'
    listener_id = u'105a227a-cdbf-4ce3-844c-9ebedec849e9'
    vip_port = u'ce69e293-56e7-43b8-b51c-01b91d66af20'
    # Translation names, shortcuts and handles...
    prefix = u'TEST_'
    partition = u'{}{}'.format(prefix, tenant_id)
    virtual_address = u'{}{}'.format(prefix, loadbalancer_id)
    virtual = u'{}{}'.format(prefix, listener_id)
    common = u'Common'
    base = u'https://localhost/mgmt/tm'
    snat_trans_spec = u'snat-traffic-group-local-only'
    selfip = u'local-{}'.format(icontrol_fqdn)
    tunnel_name = u'tunnel-vxlan-46'


class UrlSnips():
    """URL generator for the common URL's being used to compare events with

    Each URL should have its original in-place, but commented out for quick
    reference.  If this test suite fails somewhere due to an equality issue
    for a set, then reference this object and its participles that are missing
    and/or are there inappropriately.

    This object is meant to make things more easily readable; thus, you can
    use the 'url2name' dictionary if you'd like.  Keep in mind that URL's
    coming from the SDK will have:
        /?ver=xx.xx.xx/
    At the end of each URL.  This should be stripped by the stripping method
    in this library before comparisons!  If they are not, then this library is
    useless.

    I am expensive, but I am readable.  I am complicated, yet not complex.
    You can read my pieces and understand their meaning and where they come
    from.  And lastly, I'm written to be troubleshooted easily in a complex
    world...
        ~sidsn
    """
    version_strip = re.compile('\?ver=[\d\.]+')  # we know what bigip version
    tunnels = u'{u.base}/net/tunnels'.format(u=UrlNames)
    vxlan_profile = u'{}/vxlan/~Common~vxlan_ovs'.format(tunnels)
    gre_profile = u'{}/gre/~Common~gre_ovs'.format(tunnels)
    # u'https://localhost/mgmt/tm/sys/folder/'
    # u'~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    folder = u'{u.base}/sys/folder/~{u.partition}'.format(u=UrlNames)
    # u'https://localhost/mgmt/tm/net/route-domain/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    route_domain = \
        u'{u.base}/net/route-domain/~{u.partition}~{u.partition}'.format(
            u=UrlNames)
    # u'https://localhost/mgmt/tm/ltm/snat-translation/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~snat-traffic-group-local-only'
    # '-ce69e293-56e7-43b8-b51c-01b91d66af20_0'
    snat_translation_address = \
        unicode('{u.base}/ltm/snat-translation/~{u.partition}~'
                '{u.snat_trans_spec}-{u.vip_port}_0').format(u=UrlNames)
    # u'https://localhost/mgmt/tm/ltm/snat-translation/'
    # u'~Common~snat-traffic-group-local-only-'
    # u'ce69e293-56e7-43b8-b51c-01b91d66af20_0'
    common_snat_translation_address = \
        unicode('{u.base}/ltm/snat-translation/~{u.common}~'
                '{u.snat_trans_spec}-{u.vip_port}_0').format(u=UrlNames)
    # u'https://localhost/mgmt/tm/ltm/snatpool/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    snatpool = \
        u'{u.base}/ltm/snatpool/~{u.partition}~{u.partition}'.format(
            u=UrlNames)
    # 'https://localhost/mgmt/tm/net/self/~Common~local-{}'
    # '-ce69e293-56e7-43b8-b51c-01b91d66af20'
    common_selfip = \
        unicode('{u.base}/net/self/~{u.common}~{u.selfip}-'
                '{u.vip_port}').format(u=UrlNames)
    # u'https://localhost/mgmt/tm/net/self/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~local-{}-ce69e293-56e7-43b8-b51c-01b91d66af20'
    tenant_selfip = \
        u'{u.base}/net/self/~{u.partition}~{u.selfip}-{u.vip_port}'.format(
            u=UrlNames)
    # u'https://localhost/mgmt/tm/ltm/virtual-address/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~TEST_50c5d54a-5a9e-4a80-9e74-8400a461a077'])
    virtual_address = \
        unicode('{u.base}/ltm/virtual-address/~{u.partition}~'
                '{u.virtual_address}').format(u=UrlNames)
    # u'https://localhost/mgmt/tm/net/fdb/tunnel/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d~tunnel-vxlan-46',
    fdb_tunnel = \
        u'{u.base}/net/fdb/tunnel/~{u.partition}~{u.tunnel_name}'.format(
            u=UrlNames)
    # u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~tunnel-vxlan-46',
    partition_tunnel = \
        u'{}/tunnel/~{u.partition}~{u.tunnel_name}'.format(
            tunnels, u=UrlNames)
    # u'https://localhost/mgmt/tm/ltm/virtual/'
    # '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    # '~TEST_105a227a-cdbf-4ce3-844c-9ebedec849e9'
    virtual = \
        u'{u.base}/ltm/virtual/~{u.partition}~{u.virtual}'.format(u=UrlNames)
    # u'https://localhost/mgmt/tm/auth/partition/'
    # u'~TEST_128a63ef33bc4cf891d684fad58e7f2d'
    partition = \
        u'{u.base}/auth/partition/{u.partition}'.format(u=UrlNames)
    url2name = {
        route_domain: 'route_domain', virtual_address: 'virtual_address',
        snat_translation_address: 'snat_translation_address',
        snatpool: 'snatpool', common_selfip: 'common_selfip',
        tenant_selfip: 'tenant_selfip', fdb_tunnel: 'fdb_tunnel',
        partition_tunnel: 'partition_tunnel', virtual: 'virtual',
        partition: 'partition'}

    @classmethod
    def strip_version(cls, items):
        """This is the /?ver=xx.xx.xx/ stripper method aforementioned"""
        return set([cls.version_strip.sub('', item) for item in items])


AGENT_INIT_URIS = \
    set([UrlSnips.vxlan_profile, UrlSnips.gre_profile])

SEG_INDEPENDENT_LB_URIS =\
    set([UrlSnips.folder, UrlSnips.route_domain, UrlSnips.partition])

SEG_INDEPENDENT_LB_URIS_GRM =\
    set([UrlSnips.folder, UrlSnips.partition])

SEG_DEPENDENT_LB_URIS =\
    set([UrlSnips.snat_translation_address, UrlSnips.snatpool,
         UrlSnips.fdb_tunnel, UrlSnips.tenant_selfip,
         UrlSnips.partition_tunnel, UrlSnips.virtual_address])

SEG_INDEPENDENT_LB_URIS_COMMON_NET =\
    set([UrlSnips.common_snat_translation_address, UrlSnips.snatpool,
         UrlSnips.common_selfip, UrlSnips.virtual_address])

SEG_LISTENER_URIS = \
    set([UrlSnips.virtual])

NOSEG_LB_URIS =\
    set([UrlSnips.virtual_address])

NOSEG_LISTENER_URIS =\
    set([UrlSnips.virtual])

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
    icontroldriver.connect()

    return icontroldriver


def logcall(lh, call, *cargs, **ckwargs):
    return call(*cargs, **ckwargs)


@pytest.fixture
def bigip():
    LOG.debug(pytest.symbols)
    LOG.debug(pytest.symbols.bigip_floating_ips[0])
    return \
        ManagementRoot(pytest.symbols.bigip_floating_ips[0], 'admin', 'admin')


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
        remove_elements(bigip)
        # SEG_INDEPENDENT_LB_URIS |
        # SEG_DEPENDENT_LB_URIS |
        # SEG_LISTENER_URIS |
        # AGENT_INIT_URIS,
        # vlan=True)
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
    if icd_configuration['f5_global_routed_mode'] is False:
        my_set = UrlSnips.strip_version(set(start_registry.keys()) -
                                        set(init_registry.keys()))
        assert my_set == AGENT_INIT_URIS
    return icontroldriver, start_registry


def test_featureoff_withsegid_lb(track_bigip_cfg, setup_l2adjacent_test,
                                 bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(SEGID_CREATELB)

    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.get_port_by_name.call_args_list == [
        call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c-01b91d66af20'.format(
                icontrol_fqdn)),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_withsegid_lb(track_bigip_cfg, setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(SEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.get_port_by_name.call_args_list == [
        call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c-01b91d66af20'.format(
            icontrol_fqdn)),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_featureoff_withsegid_listener(track_bigip_cfg, setup_l2adjacent_test,
                                       bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(SEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
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
        call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c-01b91d66af20'.format(
            icontrol_fqdn)),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]


def test_featureoff_nosegid_lb(track_bigip_cfg, setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(NOSEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ERROR', 'OFFLINE')
    ]


def test_featureoff_nosegid_listener(track_bigip_cfg, setup_l2adjacent_test,
                                     bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_OFF)
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ERROR', 'OFFLINE')
    ]


def test_withsegid_listener(track_bigip_cfg, setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(SEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
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
        call(port_name=u'local-{}-ce69e293-56e7-43b8-b51c-01b91d66af20'.format(
            icontrol_fqdn)),
        call(port_name=u'snat-traffic-group-local-only-'
                       'ce69e293-56e7-43b8-b51c-01b91d66af20_0')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_nosegid_lb(track_bigip_cfg, setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(NOSEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert not rpc.update_loadbalancer_status.called


def test_nosegid_listener(track_bigip_cfg, setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = handle_init_registry(bigip, FEATURE_ON)
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == (SEG_INDEPENDENT_LB_URIS)

    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert not rpc.update_listener_status.called
    assert not rpc.update_loadbalancer_status.called


@pytest.mark.skip(reason="The polling will occur in the agent")
def test_nosegid_listener_timeout(track_bigip_cfg, setup_l2adjacent_test,
                                  bigip):
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
        create_uris = UrlSnips.strip_version(set(create_registry.keys()) -
                                             set(start_registry.keys()))
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


@pytest.mark.skip(reason="The polling will occur in the agent")
def test_nosegid_to_segid(track_bigip_cfg, setup_l2adjacent_test, bigip):
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
    create_uris = UrlSnips.strip_version(set(create_registry.keys()) -
                                         set(start_registry.keys()))

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


def test_featureoff_grm_lb(track_bigip_cfg, setup_l2adjacent_test, bigip):
    def create_mock_rpc_plugin():
        mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
        mock_rpc_plugin.get_port_by_name.return_value = [
            {'fixed_ips': [{'ip_address': '10.2.2.134'}]}
        ]
        mock_rpc_plugin.get_all_loadbalancers.return_value = \
            [{'lb_id': u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
              'tenant_id': u'128a63ef33bc4cf891d684fad58e7f2d'}]
        return mock_rpc_plugin

    icontroldriver, start_registry = handle_init_registry(
        bigip, FEATURE_OFF_GRM, create_mock_rpc_plugin)

    service = deepcopy(SEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    empty_set = set()

    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS_GRM | NOSEG_LB_URIS

    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()

    # rpc = icontroldriver.plugin_rpc

    service = deepcopy(SEGID_DELETELB)

    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service, True)

    after_destroy_registry = register_device(bigip)
    post_destroy_uris = (set(after_destroy_registry.keys()) -
                         set(start_registry.keys()))

    assert post_destroy_uris == empty_set


def test_featureoff_grm_listener(track_bigip_cfg, setup_l2adjacent_test,
                                 bigip):
    def create_mock_rpc_plugin():
        mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
        mock_rpc_plugin.get_port_by_name.return_value = [
            {'fixed_ips': [{'ip_address': '10.2.2.134'}]}
        ]
        mock_rpc_plugin.get_all_loadbalancers.return_value = \
            [{'lb_id': u'50c5d54a-5a9e-4a80-9e74-8400a461a077',
              'tenant_id': u'128a63ef33bc4cf891d684fad58e7f2d'}]
        return mock_rpc_plugin

    icontroldriver, start_registry = handle_init_registry(
        bigip, FEATURE_OFF_GRM, create_mock_rpc_plugin)

    service = deepcopy(SEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    # empty_set = set()

    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == (SEG_INDEPENDENT_LB_URIS_GRM | NOSEG_LB_URIS |
                           NOSEG_LISTENER_URIS)

    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_VXLAN_TUN not in open(logfilename).read()
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()


def test_featureoff_nosegid_common_lb_net(track_bigip_cfg,
                                          setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = \
        handle_init_registry(bigip, FEATURE_OFF_COMMON_NET)
    service = deepcopy(NOSEGID_CREATELB)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS_COMMON_NET | \
        SEG_INDEPENDENT_LB_URIS | \
        NOSEG_LB_URIS
    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc
    LOG.debug(rpc.method_calls)
    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]


def test_featureoff_nosegid_create_listener_common_lb_net(
            track_bigip_cfg, setup_l2adjacent_test, bigip):
    icontroldriver, start_registry = \
        handle_init_registry(bigip, FEATURE_OFF_COMMON_NET)
    service = deepcopy(NOSEGID_CREATELISTENER)
    logcall(setup_l2adjacent_test,
            icontroldriver._common_service_handler,
            service)
    after_create_registry = register_device(bigip)
    create_uris = UrlSnips.strip_version(set(after_create_registry.keys()) -
                                         set(start_registry.keys()))
    assert create_uris == SEG_INDEPENDENT_LB_URIS_COMMON_NET | \
        SEG_INDEPENDENT_LB_URIS | \
        NOSEG_LB_URIS | NOSEG_LISTENER_URIS

    logfilename = setup_l2adjacent_test.baseFilename
    assert ERROR_MSG_MISCONFIG not in open(logfilename).read()
    rpc = icontroldriver.plugin_rpc

    assert rpc.update_loadbalancer_status.call_args_list == [
        call(u'50c5d54a-5a9e-4a80-9e74-8400a461a077', 'ACTIVE', 'ONLINE')
    ]
    assert rpc.update_listener_status.call_args_list == [
        call(u'105a227a-cdbf-4ce3-844c-9ebedec849e9', 'ACTIVE', 'ONLINE')
    ]
