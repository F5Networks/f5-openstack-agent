from copy import deepcopy
import json
import logging
import mock
import os
import pytest
import requests
import time

from f5.bigip import ManagementRoot
from f5.utils.testutils.registrytools import register_device
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper

from conftest import makelogdir
from conftest import ConfFake
from conftest import setup_neutronless_test

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

# Get the Oslo Config File
curdir = os.path.dirname(os.path.realpath(__file__))
oslo_config_filename = os.path.join(curdir, 'oslo_confs.json')
OSLO_CONFIGS = json.load(open(oslo_config_filename))
TEST_CONFIG = OSLO_CONFIGS['default']

LBAAS_SERVICES = json.load(open(os.path.join(
    curdir, 'lbaas_services.json')))
CREATELB = LBAAS_SERVICES['full_service']


@pytest.fixture
def service_name(request):
    return request.config.getoption("--service-name")


@pytest.fixture
def bigip():
    return ManagementRoot(pytest.symbols.bigip_mgmt_ip, 'admin', 'admin')


@pytest.fixture
def setup_test_wrapper(request, bigip, makelogdir):
    loghandler = setup_neutronless_test(request, bigip, makelogdir, vlan=True)

    return loghandler


@pytest.fixture
def service_adapter():
    return ServiceModelAdapter(ConfFake(TEST_CONFIG))


@pytest.fixture
def system_helper():
    return SystemHelper()


def prepare_service(service):
    member = service['members'][0]
    member_ip = pytest.symbols.server_ip
    member['address'] = member_ip
    member['port']['fixed_ips'][0]['ip_address'] = member_ip

    lb_network_id = service['loadbalancer']['network_id']
    lb_net_seg_id = pytest.symbols.vip_vxlan_segid
    service['networks'][lb_network_id]['provider:segmentation_id'] = (
        lb_net_seg_id
    )

    for member in service['members']:
        member_network_id = member['network_id']
        service['networks'][member_network_id]['provider:segmentation_id'] = (
            pytest.symbols.server_vxlan_segid
        )


def get_listener_status(bigip, listener_name, listener_folder):

    vs_name = listener_name
    vs_folder = listener_folder

    v = bigip.tm.ltm.virtuals.virtual
    if v.exists(name=vs_name, partition=vs_folder):
        v_obj = v.load(name=vs_name, partition=vs_folder)
        v_stats = v_obj.stats.load(name=vs_name, partition=vs_folder)
        if v_stats:
            v_stat_entries = v_stats.entries
            for v_stat_key in v_stat_entries.keys():
                v_stat_nested = (
                    v_stat_entries.get(v_stat_key, None)['nestedStats']
                )

    collected_status = {}
    for entry in ['status.availabilityState', 'status.enabledState']:
        if entry in v_stat_nested['entries']:
            collected_status[entry] = (
                v_stat_nested['entries'][entry]['description']
            )

    return collected_status


@pytest.fixture
def service(request, bigip, service_name, service_adapter, system_helper):
    print("Creating service for %s" % service_name)
    service = deepcopy(LBAAS_SERVICES[service_name])

    prepare_service(service)

    folder_name = service_adapter.get_folder_name(
        service['loadbalancer']['tenant_id'])

    def teardown_service():
        if system_helper.folder_exists(bigip, folder_name):
            system_helper.purge_folder_contents(bigip, folder_name)
            system_helper.delete_folder(bigip, folder_name)

    request.addfinalizer(teardown_service)

    return service


def create_default_mock_rpc_plugin():
    bigip_selfip = pytest.symbols.bigip_selfip
    mock_rpc_plugin = mock.MagicMock(name='mock_rpc_plugin')
    mock_rpc_plugin.get_port_by_name.return_value = [
        {'fixed_ips': [{'ip_address': bigip_selfip}]}
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
    init_registry = register_device(bigip)
    icontroldriver = configure_icd(icd_configuration, create_mock_rpc)
    start_registry = register_device(bigip)

    return icontroldriver, start_registry


def deploy_service(bigip, service_name):
    icontroldriver, start_registry = handle_init_registry(bigip, TEST_CONFIG)

    service = deepcopy(LBAAS_SERVICES[service_name])

    prepare_service(service)

    logcall(setup_test_wrapper,
            icontroldriver._common_service_handler,
            service)


def test_create_config(setup_test_wrapper, bigip, service_name):
    print("Creating service for %s" % service_name)
    deploy_service(bigip, service_name)


def test_cleanup_config(bigip, service_name, service_adapter, system_helper):
    print("Teardown service for %s" % service_name)

    icontroldriver, start_registry = handle_init_registry(bigip, TEST_CONFIG)

    service = deepcopy(LBAAS_SERVICES[service_name])

    folder_name = service_adapter.get_folder_name(
        service['loadbalancer']['tenant_id'])

    if system_helper.folder_exists(bigip, folder_name):
        system_helper.purge_folder_contents(bigip, folder_name)
        system_helper.delete_folder(bigip, folder_name)


def get_listener_name(service, listener, service_adapter, unique_name=False):
    vs_name = listener.get("name", "")
    if not vs_name or unique_name:
        svc = {"loadbalancer": service['loadbalancer'],
               "listener": listener}
        virtual = service_adapter.get_virtual_name(svc)
        vs_name = virtual['name']
    return vs_name


def test_rename_service_objects(bigip, service, service_adapter):

    icontroldriver, start_registry = handle_init_registry(bigip, TEST_CONFIG)

    folder_name = service_adapter.get_folder_name(
        service['loadbalancer']['tenant_id'])

    pre_vs_status = {}
    for listener in service['listeners']:
        vs_name = get_listener_name(service,
                                    listener,
                                    service_adapter)
        pre_vs_status['vs_name'] = get_listener_status(
            bigip,
            vs_name,
            folder_name)

    assert(not icontroldriver.service_exists(service))
    assert(icontroldriver.service_rename_required(service))

    icontroldriver.service_object_teardown(service)

    logcall(setup_test_wrapper,
            icontroldriver._common_service_handler,
            service)

    time.sleep(10)

    assert(icontroldriver.service_exists(service))

    post_vs_status = {}
    for listener in service['listeners']:
        vs_name = get_listener_name(service,
                                    listener,
                                    service_adapter,
                                    unique_name=True)
        post_vs_status['vs_name'] = get_listener_status(
            bigip,
            vs_name,
            folder_name)

    for k, v in pre_vs_status.iteritems():
        assert(v == post_vs_status[k])


def test_no_rename_service_objects(bigip, service, service_name):

    deploy_service(bigip, service_name)

    icontroldriver, start_registry = handle_init_registry(bigip, TEST_CONFIG)

    assert(icontroldriver.service_exists(service))
    assert(not icontroldriver.service_rename_required(service))
