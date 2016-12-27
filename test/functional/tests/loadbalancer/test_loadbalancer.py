from copy import deepcopy
from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver
import json
import logging
import mock
import os
import pytest
import requests
from ..testlib.mock_rpc import MockRPCPlugin
from ..testlib.bigip_client import BigIpClient

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import ResourceType

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

oslo_config_filename =\
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../config/basic_agent_config.json')
OSLO_CONFIGS = json.load(open(oslo_config_filename))


@pytest.fixture
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/create_delete_lb.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture
def icd_config():
    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password
    config['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name

    return config


@pytest.fixture
def bigip():
    LOG.debug(pytest.symbols)
    LOG.debug(pytest.symbols.bigip_mgmt_ip)
    return BigIpClient(pytest.symbols.bigip_mgmt_ip, 'admin', 'admin')


@pytest.fixture
def mock_plugin_rpc(services):

    rpcObj = MockRPCPlugin(services)
    rpcMock = mock.Mock(return_value=rpcObj)

    return rpcMock()


@pytest.fixture
def icontrol_driver(icd_config, mock_plugin_rpc):
    class ConfFake(object):
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    icd = iControlDriver(ConfFake(icd_config),
                         registerOpts=False)

    icd.plugin_rpc = mock_plugin_rpc

    return icd


def test_create_delete_lb(bigip, services, icontrol_driver):

    service_iter = iter(services)

    # Create the loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service)

    folder = OSLO_CONFIGS['environment_prefix'] + '_' + \
             service['loadbalancer']['tenant_id']

    assert bigip.folder_exists(folder)

    if not OSLO_CONFIGS['f5_global_routed_mode']:
        tunnel = 'tunnel-' + OSLO_CONFIGS['advertised_tunnel_types'][0]
        assert bigip.folder_exists(folder)
        assert bigip.resource_exists(ResourceType.snat_translation,
                                     '^snat-traffic-group-local-only')
        assert bigip.resource_exists(ResourceType.selfip,
                                     '^local-bigip')
        assert bigip.resource_exists(ResourceType.tunnel, tunnel)
        assert bigip.resource_exists(ResourceType.route_domain, folder)

    # Delete the loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)

    # folder should be deleted; error if not
    if bigip.folder_exists(folder):
        if not OSLO_CONFIGS['f5_global_routed_mode']:
            # see which config item still exists
            tunnel = 'tunnel-' + OSLO_CONFIGS['advertised_tunnel_types'][0]
            assert not bigip.resource_exists(ResourceType.snat_translation,
                                         '^snat-traffic-group-local-only')
            assert not bigip.resource_exists(ResourceType.selfip,
                                         '^local-bigip')
            assert not bigip.resource_exists(ResourceType.tunnel, tunnel)
            assert not bigip.resource_exists(ResourceType.route_domain, folder)
        else:
            raise Exception('Folder not deleted.')
