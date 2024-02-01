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

from datetime import datetime
import random
from requests import HTTPError
from time import sleep
import uuid

from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BigIPResource(object):

    def __init__(self, **kwargs):
        pass

    def create(self, bigip, model, ret=False, overwrite=False,
               ignore=[409], suppress=[]):
        return self.helper.create(bigip, model, ret, overwrite,
                                  ignore, suppress)

    def exists(self, bigip, name="", partition=""):
        return self.helper.exists(bigip, name=name, partition=partition)

    def load(self, bigip, name="", partition="",
             expand_subcollections=False, ignore=[]):
        return self.helper.load(
            bigip, name=name, partition=partition, ignore=ignore,
            expand_subcollections=expand_subcollections)

    def update(self, bigip, model):
        return self.helper.create(bigip, model)

    def delete(self, bigip, name="", partition=""):
        self.helper.delete(bigip, name=name, partition=partition)

    def get_resources(self, bigip, partition="",
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

    def lock_route_domain(self, bigip, rd_id):
        # NOTE(qzhao): Vlans is a list property of route domain iControl API,
        # which does not support "insert" operation. We have to overwrite all
        # vlans of route domain, so that it will probably conflict with the
        # overwriting of other jobs in the same route domain. We will have to
        # create a "lock" to guarantee the consistency. Utilize internal data
        # group as a lock file here.
        dg = InternalDataGroup()
        dg_name = "rd_" + str(rd_id) + "_vlans_modify"
        lock_id = str(uuid.uuid4())
        model = {
            "name": dg_name,
            "type": "string",
            "records": [lock_id]
        }
        max_wait = 30
        lock_wait = 5
        attempt = 0
        locked = False
        another_lock = "unknown"
        start_time = datetime.utcnow()
        lock_time = start_time
        while not locked:
            attempt += 1
            try:
                dg.create(bigip, model, ignore=[], suppress=[409])
                locked = True
            except HTTPError as ex1:
                if ex1.response.status_code == 409:
                    # Another job is also modifying this route domain.
                    try:
                        dg_file = dg.load(bigip, name=dg_name)
                        if len(dg_file.records) > 0:
                            if dg_file.records[0] != another_lock:
                                another_lock = dg_file.records[0]
                                lock_time = datetime.utcnow()
                        else:
                            # Invalid data. Should not happen.
                            LOG.debug("Invalid lock data. Delete it.")
                            another_lock = "unknown"
                            lock_time = datetime.utcnow()
                            dg.delete(bigip, dg_name)
                            continue
                    except HTTPError as ex2:
                        if ex2.response.status_code == 404:
                            # Data group is removed by another job.
                            another_lock = "unknown"
                            lock_time = datetime.utcnow()
                            continue
                        else:
                            raise ex2

                    end_time = datetime.utcnow()
                    if (end_time - start_time).total_seconds() < max_wait:
                        if (end_time - lock_time).total_seconds() < lock_wait:
                            # Wait up to half second
                            interval = random.uniform(0.1, 0.5)
                            sleep(interval)
                        else:
                            # Timeout to wait that job.
                            # Attempt to delete data group.
                            dg.delete(bigip, dg_name)
                    else:
                        LOG.error("Timeout to lock route domain %s", rd_id)
                        LOG.exception(ex1)
                        raise ex1
                else:
                    LOG.error("Fail to lock route domain %s", rd_id)
                    raise ex1

    def unlock_route_domain(self, bigip, rd_id):
        dg = InternalDataGroup()
        dg_name = "rd_" + str(rd_id) + "_vlans_modify"
        dg.delete(bigip, dg_name)

    def add_vlan_by_name(self, bigip, rd_name, vlan_name, rd_id=None,
                         partition="Common"):
        if not rd_id:
            rd = self.helper.load(bigip, name=rd_name, partition=partition)
            rd_id = rd.id

        self.lock_route_domain(bigip, rd_id)
        try:
            rd = self.helper.load(bigip, name=rd_name, partition=partition)
            self.helper.add_to_list(rd, "vlans", vlan_name)
        finally:
            self.unlock_route_domain(bigip, rd_id)

    def add_vlan_by_id(self, bigip, rd_id, vlan_name, partition="Common"):
        rds = self.helper.get_resources(bigip, partition=partition)
        for rd in rds:
            if rd.id == rd_id:
                self.add_vlan_by_name(bigip, rd.name, vlan_name, rd_id=rd_id,
                                      partition=partition)
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


class InternalDataGroup(BigIPResource):
    def __init__(self, **kwargs):
        super(InternalDataGroup, self).__init__(**kwargs)
        self.helper = BigIPResourceHelper(ResourceType.internal_data_group)
