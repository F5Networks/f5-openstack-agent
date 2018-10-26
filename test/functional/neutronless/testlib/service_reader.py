# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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


class LoadbalancerReader(object):
    def __init__(self, service):
        self.service = service
        self.loadbalancer = service.get('loadbalancer', None)
        self.network_id = self.loadbalancer.get('network_id', "")
        self.network = service['networks'][self.network_id]

    def id(self):
        return self.loadbalancer['id']

    def tenant_id(self):
        return self.loadbalancer['tenant_id']

    def vip_address(self):
        return self.loadbalancer['vip_address']

    def network_id(self):
        return self.loadbalancer['network_id']

    def network_type(self):
        return self.network['provider:network_type']

    def network_seg_id(self):
        return self.network['provider:segmentation_id']

    def subnet_id(self):
        return self.loadbalancer['vip_subnet_id']


class ServiceReader(object):

    def __init_(self, service):
        self.service = service

    def get_loadbalancer(self):
        return self.service.get("loadbalancer", None)
