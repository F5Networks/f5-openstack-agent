# coding=utf-8
# Copyright 2016 F5 Networks Inc.
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
