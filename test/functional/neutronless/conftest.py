# coding=utf-8
# Copyright 2016-2017 F5 Networks Inc.
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


from .testlib.bigip_client import BigIpClient
from .testlib.fake_rpc import FakeRPCPlugin
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver

from copy import deepcopy
import json
import os
import pytest


@pytest.fixture
def bigip(request):

    bigip = BigIpClient(pytest.symbols.bigip_mgmt_ip_public,
                        pytest.symbols.bigip_username,
                        pytest.symbols.bigip_password)

    def fin():
        bigip.delete_folders()
    request.addfinalizer(fin)

    return bigip


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


@pytest.fixture()
def icd_config():
    relative = get_relative_path()
    basic_agent_config = str("{}/f5-openstack-agent/test/functional/config"
                             "/basic_agent_config.json".format(relative))
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     basic_agent_config)
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password
    try:
        config['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name
    except AttributeError:
        config['f5_vtep_selfip_name'] = "selfip.external"
    return config


@pytest.fixture()
def get_relative_path():
    """Discovers the relative path to the start of the repo's path and returns

    This test fixture will find the relative path of the beginning of the repo.
    This path is then returned.  If it is discovered that:
    ./f5-openstack-agent/test/functional/neutronless/

    Is not a full path, then it will raise and AssertionError.  If the user
    executes this within a non-existent or partial repo that is fake or
    unexpected, then it is assumed any subsequent test would fail.

    The purpose of this code is to free up some tests from having to be run
    from an explicit point of reference from within the repo's many possible
    paths or tributaries.
    """
    current = os.getcwd()
    repo_name = "f5-openstack-agent"
    expected_relative = [repo_name, 'test', 'functional', 'neutronless']
    relative_path = list()
    for level in current.split("/"):
        if level == repo_name:
            break
        relative_path.append(level)
    else:
        raise AssertionError(
            "{} is not in your path! Please be "
            "within the repo!".format(repo_name))
    found = list(relative_path)
    found.extend(expected_relative)
    discovered = '/'.join(found)
    assert os.path.isdir('/'.join(found)), \
        "{} does not exist!".format(discovered)
    return '/'.join(relative_path)
