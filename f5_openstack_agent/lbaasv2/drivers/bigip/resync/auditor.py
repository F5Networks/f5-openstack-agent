# -*- coding: utf-8 -*-

from f5_openstack_agent.lbaasv2.drivers.bigip.resync.collector import factory
from f5_openstack_agent.lbaasv2.drivers.bigip.resync import comparator
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.filters import BigIPFilter
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.filters import LbaasFilter
from f5_openstack_agent.lbaasv2.drivers.bigip.resync import options
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.publishers import \
    FilePublisher
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.util \
    import time_logger

from oslo_config import cfg
from oslo_log import log as logging

import datetime
import time

options.load_options()
options.parse_options()
conf = cfg.CONF

logging.setup(conf, __name__)
LOG = logging.getLogger(__name__)


@time_logger(LOG)
def main():

    if conf.f5_agent:
        bigip_filter = BigIPFilter(conf.environment_prefix)
        lbaas_filter = LbaasFilter()

        lbaas_collector = factory.get_collectors("lbaas", conf)[0]
        bigip_collectors = factory.get_collectors("bigip", conf)

        comp = comparator.LbaasToBigIP(lbaas_collector, lbaas_filter)

        for collector in bigip_collectors:
            comp.compare_to(collector, bigip_filter)

            date = datetime.datetime.fromtimestamp(time.time()).strftime(
                '%Y-%m-%d_%H-%M-%S'
            )
            dir_name = collector.keys()[0] + "_" + str(date)
            publisher = FilePublisher(dir_name)

            missing = comp.get_missing_projects()
            if missing:
                publisher.write_json("missing_projects", missing)

            missing = comp.get_missing_loadbalancers()
            if missing:
                publisher.write_json("missing_loadbalancers", missing)

            missing = comp.get_missing_listeners()
            if missing:
                publisher.write_json("missing_listeners", missing)

            missing = comp.get_missing_pools()
            if missing:
                publisher.write_json("missing_pools", missing)

            missing = comp.get_missing_members()
            if missing:
                publisher.write_json("missing_members", missing)

    else:
        raise Exception("Provide an corresponding agent ID "
                        "--f5-agent")


if __name__ == "__main__":
    main()
