# -*- coding: utf-8 -*-


from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import BigIPResourceHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import ResourceType

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class RouteHelper(object):

    def __init__(self, netinfo, l2_service):
        self.lb_netinfo = netinfo
        self.l2_service = l2_service
        self.route_manager = BigIPResourceHelper(ResourceType.route)

        self.route_domain_id = str(
            self.lb_netinfo['network']['route_domain_id']
        )
        self.partition = self.l2_service.get_network_folder(
            self.lb_netinfo['network']
        )

    def gateway_ip(self, subnet):
        return subnet['gateway_ip'] + '%' + self.route_domain_id

    def route_name(self, subnet):
        if subnet['ip_version'] == 4:
            return 'IPv4_default_route_' + self.route_domain_id
        elif subnet['ip_version'] == 6:
            return 'IPv6_default_route_' + self.route_domain_id
        else:
            raise Exception(
                "Can not get route name "
                "for subent %s\n" % subnet
            )

    def default_route_dst(self, subnet):
        if subnet['ip_version'] == 4:
            return '0.0.0.0' + "%" + self.route_domain_id + '/0'
        elif subnet['ip_version'] == 6:
            return '::' + "%" + self.route_domain_id + '/0'
        else:
            raise Exception(
                "Can not get default route destination "
                "for subent %s\n" % subnet
            )

    def create_route_for_net(self, bigip):
        for subnet in self.lb_netinfo['subnets']:
            self.create_default_route(bigip, subnet)

    def create_default_route(self, bigip, subnet):
        payload = {
            "name": self.route_name(subnet),
            "partition": self.partition,
            "gw": self.gateway_ip(subnet),
            "network": self.default_route_dst(subnet)
        }

        LOG.info(
            "Creating default route for subnet %s.\n"
            "the gateway payload is %s \n" %
            (subnet, payload)
        )

        self.create_route(bigip, payload)

    def remove_default_route(self, bigip, subnet):
        name = self.route_name(subnet)

        LOG.info(
            "Deleting default route for subnet %s.\n"
            "the gateway name is %s \n" %
            (subnet, name)
        )

        self.delete_route(bigip, name, self.partition)

    def create_route(self, bigip, payload):
        if payload:
            try:
                self.route_manager.create(
                    bigip, payload
                )
            except Exception as err:
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
