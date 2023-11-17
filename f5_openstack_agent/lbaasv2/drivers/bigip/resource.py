# coding=utf-8
# Copyright (c) 2023, F5 Networks, Inc.
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

from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType

LOG = logging.getLogger(__name__)


class BigIPResource(object):

    def __init__(self, **kwargs):
        pass

    def create(self, bigip, model, ret=False, overwrite=False,
               ignore=[409], suppress=[]):
        return self.helper.create(bigip, model, ret, overwrite,
                                  ignore, suppress)

    def exists(self, bigip, name=None, partition=None):
        return self.helper.exists(bigip, name=name, partition=partition)

    def load(self, bigip, name=None, partition=None,
             expand_subcollections=False):
        return self.helper.load(bigip, name=name, partition=partition,
                                expand_subcollections=expand_subcollections)

    def update(self, bigip, model):
        return self.helper.create(bigip, model)

    def delete(self, bigip, name=None, partition=None):
        self.helper.delete(bigip, name=name, partition=partition)

    def get_resources(self, bigip, partition=None,
                      expand_subcollections=False):
        return self.helper.get_resources(
            bigip, partition=partition,
            expand_subcollections=expand_subcollections)


class Folder(BigIPResource):
    def __init__(self, **kwargs):
        super(Folder, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.folder)


class Device(BigIPResource):
    def __init__(self, **kwargs):
        super(Device, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.device)


class VirtualAddress(BigIPResource):
    def __init__(self, **kwargs):
        super(VirtualAddress, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.virtual_address)


class VirtualServer(BigIPResource):
    def __init__(self, **kwargs):
        super(VirtualServer, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.virtual)


class SelfIP(BigIPResource):
    def __init__(self, **kwargs):
        super(SelfIP, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.selfip)


class RouteDomain(BigIPResource):
    def __init__(self, **kwargs):
        super(RouteDomain, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.route_domain)

    def add_vlan(self, rd, vlan_name):
        self.helper.add_to_list(rd, "vlans", vlan_name)

    def add_vlan_by_name(self, bigip, rd_name, vlan_name, partition="Common"):
        rd = self.helper.load(bigip, name=rd_name, partition=partition)
        self.helper.add_to_list(rd, "vlans", vlan_name)

    def add_vlan_by_id(self, bigip, rd_id, vlan_name, partition="Common"):
        rds = self.helper.get_resources(bigip, partition=partition)
        for rd in rds:
            if rd.id == rd_id:
                self.add_vlan(rd, vlan_name)
                break


class Vlan(BigIPResource):
    def __init__(self, **kwargs):
        super(Vlan, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.vlan)

    def add_interface(self, vlan, interface_model):
        self.helper.add_to_subcollection(vlan, "interfaces", interface_model)

    def add_interface_by_name(self, bigip, vlan_name, interface_model,
                              partition="Common"):
        vlan = self.helper.load(bigip, name=vlan_name, partition=partition)
        self.add_interface(vlan, interface_model)


class Route(BigIPResource):
    def __init__(self, **kwargs):
        super(Route, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.route)


class Node(BigIPResource):
    def __init__(self, **kwargs):
        super(Node, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.node)


class CipherGroup(BigIPResource):
    def __init__(self, **kwargs):
        super(CipherGroup, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.cipher_group)


class CipherRule(BigIPResource):
    def __init__(self, **kwargs):
        super(CipherRule, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.cipher_rule)
