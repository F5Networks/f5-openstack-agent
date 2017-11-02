# coding=utf-8
# Copyright 2017 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from copy import deepcopy
import json
import logging
import os

import pytest
import requests
from filepath import FilePath

from ....lbaasv2.drivers.bigip.icontrol_driver import iControlDriver
from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.service_reader import LoadbalancerReader
from ..testlib.resource_validator import ResourceValidator

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    neutron_services_fp = FilePath(__file__)\
                            .parent()\
                            .parent()\
                            .child("testdata")\
                            .child("service_requests")\
                            .child("l7_esd.json")
    return (json.load(neutron_services_fp.open()))


@pytest.fixture()
def icd_config():
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../config/overcloud_basic_agent_config.json')
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password

    return config


@pytest.fixture(scope="module")
def bigip():

    return BigIpClient(pytest.symbols.bigip_mgmt_ip_public,
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


@pytest.fixture
def esd():
    esd_file = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../../../etc/neutron/services/f5/esd/demo.json')
    )
    return (json.load(open(esd_file)))


def test_esd(bigip, services, icd_config, icontrol_driver, esd):
    env_prefix = icd_config['environment_prefix']
    validator = ResourceValidator(bigip, env_prefix)

    # create loadbalancer
    service = services[0]
    lb_reader = LoadbalancerReader(service)
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)

    # create listener
    service = services[1]
    listener = service['listeners'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_valid(listener, folder)

    # create pool
    service = services[2]
    pool = service['pools'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool, folder)

    # apply ESD
    service = services[3]
    icontrol_driver._common_service_handler(service)
    validator.assert_esd_applied(esd['esd_demo_1'], listener, folder)

    # remove ESD
    service = services[4]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_valid(listener, folder)
    validator.assert_esd_removed(esd['esd_demo_1'], listener, folder)

    # apply another ESD
    service = services[5]
    icontrol_driver._common_service_handler(service)
    validator.assert_esd_applied(esd['esd_demo_2'], listener, folder)

    # remove ESD
    service = services[6]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_valid(listener, folder)
    validator.assert_esd_removed(esd['esd_demo_2'], listener, folder)

    # delete pool (and member, node)
    service = services[7]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_deleted(pool, None, folder)

    # delete listener
    service = services[8]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_deleted(listener, folder)

    # delete loadbalancer
    service = services[9]
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(folder)
