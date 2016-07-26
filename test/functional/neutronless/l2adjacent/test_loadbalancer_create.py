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
import requests

from f5.utils.testutils.registrytools import register_device
requests.packages.urllib3.disable_warnings()


from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver


CREATE_ADJ_LB_SVC = json.load(open('adjacent_lb_create_svc.json'))
CONFIG_PARAMETERS = json.load(open('basic_l2a_oslo_options.json'))

CREATIONURISET =\
    set([u'https://localhost/mgmt/tm/ltm/snat-translation/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~snat-traffic-group-local-only'
         '-ce69e293-56e7-43b8-b51c-01b91d66af20_0?ver=11.6.0',

         u'https://localhost/mgmt/tm/ltm/snatpool/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d~tunnel-vxlan-45?ver=11.5.0',

         u'https://localhost/mgmt/tm/net/route-domain/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/self/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~tunnel-vxlan-45?ver=11.6.0',

         u'https://localhost/mgmt/tm/sys/folder/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0'])


class ConfFake(object):
    def __init__(self, params):
        self.__dict__ = params
        for k, v in self.__dict__.items():
            if isinstance(v, unicode):
                self.__dict__[k] = v.encode('utf-8')

    def __repr__(self):
        return repr(self.__dict__)


def test_loadbalancer_create(setup_neutronless_test, bigip):
    mock_rpc_plugin = mock.MagicMock()
    mock_rpc_plugin.get_port_by_name.return_value =\
        [{'fixed_ips': [{'ip_address': '10.2.2.134'}]}]
    start_registry = register_device(bigip)
    icontroldriver = iControlDriver(ConfFake(CONFIG_PARAMETERS),
                                    registerOpts=False)
    icontroldriver.plugin_rpc = mock_rpc_plugin
    start_folders = bigip.tm.sys.folders.get_collection()
    # check that the bigip partitions are correct pre-create
    assert len(start_folders) == 2
    for sf in start_folders:
        assert sf.name == '/' or sf.name == 'Common'
    # Initialize lb and wait for confirmation from neutron
    icontroldriver._common_service_handler(CREATE_ADJ_LB_SVC)

    active_folders = bigip.tm.sys.folders.get_collection()
    assert len(active_folders) == 3
    for sf in active_folders:
        assert sf.name == '/' or\
            sf.name == 'Common' or\
            sf.name.startswith('TEST_')
    # Test show and update
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == CREATIONURISET
