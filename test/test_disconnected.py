# Copyright 2106 F5 Networks Inc.
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
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from f5.bigip import BigIP
from f5_openstack_agent.lbaasv2.drivers.bigip.disconnected_service import \
    DisconnectedService
from f5_openstack_agent.lbaasv2.drivers.bigip.listener_service import \
    ListenerServiceBuilder
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter

# Note: symbols_data provided through commandline json file.
from pytest import symbols as symbols_data


class DummyConf(object):
    def __init__(self):
        self.environment_prefix = 'Project'
        self.f5_snat_mode = True


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
disconnected_service = DisconnectedService()
service_adapter = ServiceModelAdapter(DummyConf())
listener_builder = ListenerServiceBuilder(service_adapter)
folder_helper = BigIPResourceHelper(ResourceType.folder)
bigips = [BigIP(symbols_data.bigip_ip,
                symbols_data.bigip_username,
                symbols_data.bigip_password)]


def deploy_service(service_file):
    service = {
        'listeners': []
    }

    folder = None
    try:
        service = json.load(open(service_file))["service"]

        # create partition
        folder = service_adapter.get_folder(service)
        for bigip in bigips:
            folder_helper.create(bigip, folder)
            disconnected_service.create_network(bigip, folder['name'])
            assert disconnected_service.network_exists(bigip, folder['name'])

        # create BIG-IP virtual servers
        for listener in service["listeners"]:
            # create a service object in form expected by builder
            svc = {"loadbalancer": service["loadbalancer"],
                   "listener": listener,
                   "networks": service["networks"]}
            # create
            listener_builder.create_listener(svc, bigips)
            # validate
            l = listener_builder.get_listener(svc, bigips[0])
            assert l.name == listener["name"]
            virtual = service_adapter.get_virtual_name(svc)
            if disconnected_service.is_service_connected(svc):
                assert disconnected_service.is_virtual_connected(virtual,
                                                                 bigips)
            else:
                assert not disconnected_service.is_virtual_connected(virtual,
                                                                     bigips)
    finally:
        for listener in service["listeners"]:
            svc = {"loadbalancer": service["loadbalancer"],
                   "listener": listener,
                   "networks": service["networks"]}
            listener_builder.delete_listener(svc, bigips)
        if folder:
            for bigip in bigips:
                disconnected_service.delete_network(bigip, folder['name'])
                assert not disconnected_service.network_exists(bigip,
                                                               folder['name'])
                folder_helper.delete(bigip, folder['name'])


def test_service_connected():
    deploy_service("connected_service.json")


def test_service_disconnected():
    deploy_service("disconnected_service.json")
