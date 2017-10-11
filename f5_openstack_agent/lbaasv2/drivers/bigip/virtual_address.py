# coding=utf-8
# Copyright 2014-2016 F5 Networks Inc.
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

from oslo_log import log as logging
from requests import HTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper


LOG = logging.getLogger(__name__)


class VirtualAddress(object):
    u"""Class to translate LBaaS loadbalancer objects to BIG-IP virtual address.

    Creates BIG-IP virtual address objects given an LBaaS service object.
    """

    def __init__(self, adapter, loadbalancer):

        self.adapter = adapter
        self.virtual_address = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)

        # Immutable attributes
        self.name = self.adapter.prefix + loadbalancer['id']
        self.partition = self.adapter.get_folder_name(
            loadbalancer['tenant_id'])
        self.address = loadbalancer.get('vip_address', "")

        # Mutable attributes
        self.description = self.adapter.get_resource_description(loadbalancer)
        self.traffic_group = loadbalancer.get('traffic_group', "")

        self.auto_delete = False

        if loadbalancer.get('admin_state_up', True):
            self.enabled = 'yes'
        else:
            self.enabled = 'no'

    def model(self):
        model = {"name": self.name,
                 "partition": self.partition,
                 "address": self.address,
                 "description": self.description,
                 "trafficGroup": self.traffic_group,
                 "autoDelete": self.auto_delete,
                 "enabled": self.enabled}

        return model

    def create(self, bigip, model=None):
        va = None

        if not model:
            model = self.model()

        try:
            va = self.virtual_address.create(
                bigip,
                model)
        except HTTPError as err:
            # If this object already exists
            if err.response.status_code == 409:
                LOG.debug("Virtual address already exists")
                va = self.load(bigip)

        return va

    def exists(self, bigip):
        return self.virtual_address.exists(
            bigip,
            name=self.name,
            partition=self.partition)

    def delete(self, bigip):
        self.virtual_address.delete(
            bigip,
            name=self.name,
            partition=self.partition)

    def load(self, bigip):
        return self.virtual_address.load(
            bigip,
            name=self.name,
            partition=self.partition)

    def update(self, bigip):


        model = self.model()
        remote = self.load(bigip)
        if remote.address != model["address"]:
            # could be route domain or IP has changed
            try:
                self.delete(bigip)
            except:
                LOG.error("Failed to deleted redundant virtual address %s", remote)
            return self.create(bigip)
        else:
            # pop immutables and update
            model.pop("address")
            return  self.virtual_address.update(bigip, model)

    def assure(self, bigip, delete=False):

        if delete:
            self.delete(bigip)
        else:
            if self.exists(bigip):
                self.update(bigip)
            else:
                self.create(bigip)
