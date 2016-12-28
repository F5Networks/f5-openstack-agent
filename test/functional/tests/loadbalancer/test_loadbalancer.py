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
from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.service_reader import LoadbalancerReader


from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper import ResourceType

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def services():
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/create_delete_lb.json')
    )
    return (json.load(open(neutron_services_filename)))


@pytest.fixture()
def icd_config():
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../config/basic_agent_config.json')
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password
    config['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name

    return config


@pytest.fixture(scope="module")
def bigip():

    return BigIpClient(pytest.symbols.bigip_mgmt_ip,
                       pytest.symbols.bigip_username,
                       pytest.symbols.bigip_password)


@pytest.fixture
def fake_plugin_rpc(services):

    rpcObj = FakeRPCPlugin(services)

    return rpcObj


@pytest.fixture
def icontrol_driver(icd_config, fake_plugin_rpc):
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

    icd.plugin_rpc = fake_plugin_rpc

    return icd


def test_create_delete_basic_lb(bigip, services, icd_config, icontrol_driver):

    service_iter = iter(services)
    service = service_iter.next()
    lb_reader = LoadbalancerReader(service)
    env_prefix = icd_config['environment_prefix']
    
    folder = '%s_%s' % (env_prefix, lb_reader.tenant_id())

    # Make sure we are starting clean.
    # assert not bigip.folder_exists(folder)
    
    # Create the loadbalancer
    icontrol_driver._common_service_handler(service)

    # Assert folder created
    assert bigip.folder_exists(folder)

    # Assert tunnel created.
    tunnel_name = 'tunnel-%s-%d' % (lb_reader.network_type(),
                                    lb_reader.network_seg_id())
    fq_tunnel_name = '/%s/%s' % (folder, tunnel_name)
    assert bigip.resource_exists(ResourceType.tunnel, tunnel_name)
    tunnel = bigip.get_resource(ResourceType.tunnel, tunnel_name, partition=folder)
    assert tunnel

    # Assert route domain created
    rd_name = folder
    assert bigip.resource_exists(ResourceType.route_domain, rd_name)
    rd = bigip.get_resource(ResourceType.route_domain, rd_name, partition=folder)

    # Assert route domain properties
    assert rd
    assert rd.id == 1
    assert rd.strict == "disabled"
    assert fq_tunnel_name in  rd.vlans

    # Assert disconnected network created.
    assert bigip.resource_exists(ResourceType.tunnel, "disconnected_network")

    # Assert that a self ip was created.
    selfip_name = "local-bigip1-%s" % (lb_reader.subnet_id())
    assert bigip.resource_exists(ResourceType.selfip, selfip_name)
    selfip = bigip.get_resource(ResourceType.selfip, selfip_name, partition=folder)
    assert selfip
    assert selfip.vlan == fq_tunnel_name
    assert selfip.address == "10.2.2.100%1/24"

    # Assert that a snat pool was created.
    snatpool_name = folder
    assert bigip.resource_exists(ResourceType.snatpool, snatpool_name)
    snatpool = bigip.get_resource(ResourceType.snatpool, snatpool_name, partition=folder)
    assert snatpool
    snat_members = snatpool.members

    # Assert snat transtion pool members
    for i in range(icd_config['f5_snat_addresses_per_subnet']):
        snat_xlation = "snat-traffic-group-local-only-%s_%s" % (lb_reader.subnet_id(), i)
        snat_xlation_fq = "/%s/%s" % (folder, snat_xlation)
        assert bigip.resource_exists(ResourceType.snat_translation, snat_xlation)
        assert snat_xlation_fq in snat_members
        snat_member = bigip.get_resource(ResourceType.snat_translation,
                                         snat_xlation,
                                         partition=folder
        )
        assert snat_member
        assert snat_member.trafficGroup == "/Common/traffic-group-local-only"        
        # Another test for mult snats should be more configurable
        assert snat_member.address == "10.2.2.101%1"


    # Assert virtual address
    virtual_addr_name = "%s_%s" % (env_prefix, lb_reader.id())
    assert bigip.resource_exists(ResourceType.virtual_address, virtual_addr_name)
    virtual_addr = bigip.get_resource(ResourceType.virtual_address,
                                      virtual_addr_name, partition=folder)
    assert virtual_addr
    assert virtual_addr.address == "10.2.2.112%1"
    assert virtual_addr.trafficGroup == "/Common/traffic-group-1"
    assert virtual_addr.autoDelete == "false"

    # Delete the loadbalancer
    service = service_iter.next()
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(folder)

    # folder should be deleted; error if not
    # if bigip.folder_exists(folder):
    #     if not OSLO_CONFIGS['f5_global_routed_mode']:
    #         # see which config item still exists
    #         tunnel = 'tunnel-' + OSLO_CONFIGS['advertised_tunnel_types'][0]
    #         assert not bigip.resource_exists(ResourceType.snat_translation,
    #                                      '^snat-traffic-group-local-only')
    #         assert not bigip.resource_exists(ResourceType.selfip,
    #                                      '^local-bigip')
    #         assert not bigip.resource_exists(ResourceType.tunnel, tunnel)
    #         assert not bigip.resource_exists(ResourceType.route_domain, folder)
    #     else:
    #         raise Exception('Folder not deleted.')
