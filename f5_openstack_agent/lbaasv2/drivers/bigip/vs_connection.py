# -*- coding: utf-8 -*-

import eventlet

from f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 import \
    FLAVOR_CONN_MAP
from f5_openstack_agent.lbaasv2.drivers.bigip import \
    resource_helper
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class VSConnectionHelper(object):

    def __init__(self):
        self.conf = cfg.CONF
        self.vs_helper = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.virtual
        )
        self.adapter = ServiceModelAdapter(self.conf)

    def get_vss(self, bigip, loadbalancer):
        self.partition = self.adapter.get_folder_name(
            loadbalancer['tenant_id']
        )

        partition_vss = self.vs_helper.get_resources(
            bigip, partition=self.partition)

        lb_vss = [
            vs for vs in partition_vss
            if loadbalancer['id'] in vs.destination
        ]
        return lb_vss

    def refresh_con_limit(self, bigip, loadbalancer):
        flavor = loadbalancer.get('flavor')

        if flavor is not None:
            vss = self.get_vss(bigip, loadbalancer)
            vss_nums = len(vss)
            value = FLAVOR_CONN_MAP[str(flavor)][
                'connection_limit']

            if vss_nums != 0:
                limit = value // vss_nums

                LOG.info(
                    "Refresh connection limit %s for virtual servers of "
                    " loadbalancer %s." % (limit, loadbalancer['name'])
                )

                pool = eventlet.greenpool.GreenPool()
                for vs in vss:
                    try:
                        pool.spawn(vs.modify, connectionLimit=limit)
                    except Exception as ex:
                        LOG.error(
                            "Fail to refresh virtual server %s"
                            " connection limit %s." % (vs.name, limit)
                        )
                        raise ex
                pool.waitall()
