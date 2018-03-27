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


import re
import urllib

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import cluster_manager
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip import system_helper


class BigIpClient(object):
    def __init__(self, hostname, username, password):
        self.bigip = ManagementRoot(hostname, username, password)
        self.syshelper = system_helper.SystemHelper()

    def purge_folder_contents(self, folder):
        self.syshelper.purge_folder_contents(self.bigip, folder)

    def delete_folder(self, folder):
        self.purge_folder_contents(folder)
        self.syshelper.purge_folder(self.bigip, folder)

    def delete_folders(self):
        folders = [
            folder.name for folder in
            self.bigip.tm.sys.folders.get_collection()]

        folders.remove('/')
        folders.remove('Common')
        if 'Drafts' in folders:
            try:
                folders.remove('Drafts')
            except Exception:
                pass

        # for folder in folders:
        for folder in folders:
            print ("\nDeleting folder on test exit: %s" % folder)
            self.delete_folder(folder)

    def folder_exists(self, folder):
        return self.bigip.tm.sys.folders.folder.exists(name=folder)

    def resource_exists(self, resource_type, resource_name, partition=None):
        helper = resource_helper.BigIPResourceHelper(resource_type)
        resources = helper.get_resources(self.bigip, partition=partition)
        for resource in resources:
            if re.match(resource_name, resource.name):
                return True

        return False

    def get_resource(self, resource_type, resource_name, partition=None):
        helper = resource_helper.BigIPResourceHelper(resource_type)
        obj = helper.load(self.bigip, name=resource_name, partition=partition)
        return obj

    def get_nodes(self, partition):
        return self.bigip.tm.ltm.nodes.get_collection(partition=partition)

    def node_exists(self, node_name, partition):
        return self.bigip.tm.ltm.nodes.node.exists(
            name=urllib.quote(node_name), partition=partition)

    def member_exists(self, pool_name, member_name, partition=None):
        helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)
        if helper.exists(self.bigip, pool_name, partition=partition):
            p = helper.load(self.bigip, name=pool_name, partition=partition)
            m = p.members_s.members
            return m.exists(name=urllib.quote(member_name),
                            partition=partition)

        return False

    def get_device_name(self):
        cm = cluster_manager.ClusterManager()
        return cm.get_device_name(self.bigip)
