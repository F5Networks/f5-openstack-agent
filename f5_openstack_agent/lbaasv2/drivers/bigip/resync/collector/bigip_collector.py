# -*- coding: utf-8 -*-

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.collector \
    import base
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.util \
    import time_logger
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BigIPSource(object):
    def __init__(self, hostname,
                 icontrol_username,
                 icontrol_password):
        self.__hostname = hostname
        self.__icontrol_username = icontrol_username
        self.__icontrol_password = icontrol_password

        self.connection = self.init_bigip()

    @property
    def hostname(self):
        return self.__hostname

    @property
    def username(self):
        return self.__icontrol_username

    @property
    def password(self):
        return None

    def init_bigip(self):
        bigip = ManagementRoot(self.__hostname,
                               self.__icontrol_username,
                               self.__icontrol_password)
        return bigip


class BigIPCollector(base.Collector):
    def __init__(self, source, service_adapter):
        self.bigip = source
        self.service_adapter = service_adapter

        self.partition_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.partition)
        self.vip_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual_address)
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual)
        self.pool_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.pool)

    @staticmethod
    def convert_member_name(bigip_member_name):
        # remove the routedomain id
        if "%" in bigip_member_name:
            port = bigip_member_name.split(":")[1]
            address = bigip_member_name.split("%")[0]
            bigip_member_name = address + ":" + port

        return bigip_member_name

    @time_logger(LOG)
    def get_projects_on_device(self):
        LOG.info("Get projects on device %s", self.bigip.hostname)
        partitions = self.partition_helper.get_resources(self.bigip)
        return partitions

    @time_logger(LOG)
    def get_project_loadbalancers(self, project_id):
        LOG.info("Get loadbalancers of project: %s", project_id)
        folder_name = self.service_adapter.get_folder_name(project_id)
        loadbalancers = self.vip_helper.get_resources(self.bigip, folder_name)
        return loadbalancers

    @time_logger(LOG)
    def get_project_listeners(self, project_id):
        LOG.info("Get listeners of project: %s", project_id)
        folder_name = self.service_adapter.get_folder_name(project_id)
        listeners = self.vs_helper.get_resources(self.bigip, folder_name)
        return listeners

    @time_logger(LOG)
    def get_project_pools(self, project_id):
        LOG.info("Get pools of project: %s", project_id)
        folder_name = self.service_adapter.get_folder_name(project_id)
        pools = self.pool_helper.get_resources(self.bigip, folder_name, True)
        return pools
