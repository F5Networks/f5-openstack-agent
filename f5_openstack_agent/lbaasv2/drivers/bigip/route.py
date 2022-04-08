# -*- coding: utf-8 -*-


from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class RouteServiceBuilder(object):

    def __init__(self):
        self.route_manager = BigIPResourceHelper(ResourceType.route)

    def create_route(self, bigip, payload):
        if payload:
            try:
                self.route_manager.create(
                    bigip, payload
                )
            except Exception as err:
                if err.response.status_code == 409:
                    LOG.info("Route %s has existed.", payload)
                else:
                    LOG.error("Fail to create route %s", payload)
                    raise err

    def delete_route(self, bigip, name, partition):
        if name:
            try:
                self.route_manager.delete(
                    bigip, partition=partition, name=name)
            except Exception as err:
                if err.response.status_code == 404:
                    LOG.info(
                        "Route %s is not existed in partition %s",
                        name, partition
                    )
                else:
                    LOG.error(
                        "Fail to delete route %s in partition %s",
                        name, partition
                    )
                    raise err

    def routes(self, bigip, partition, name=None):
        if name:
            return self.route_manager.load(
                bigip, partition=partition, name=name)
        return self.route_manager.get_resources(
            bigip, partition=partition)
