# -*- coding: utf-8 -*-

from f5_openstack_agent.lbaasv2.drivers.bigip.resync.collector import \
    bigip_collector
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.collector import \
    lbaas_collector
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.db import queries
from f5_openstack_agent.lbaasv2.drivers.bigip.service_adapter import \
    ServiceModelAdapter


def get_collectors(collector_type, conf):

    collectors = []
    collector = dict()

    if collector_type == "lbaas":
        db_query = queries.Queries()
        collector['lbaas'] = lbaas_collector.LbassDBCollector(
            db_query, conf.f5_agent)
        collectors.append(collector)

    elif collector_type == "bigip":
        service_adapter = ServiceModelAdapter(conf)
        ips = conf.icontrol_hostname
        hostnames = parse_hostnames(ips)

        for hostname in hostnames:
            source = bigip_collector.BigIPSource(
                hostname, conf.icontrol_username, conf.icontrol_password
            )
            collector[hostname] = bigip_collector.BigIPCollector(
                source.connection,
                service_adapter)
            collectors.append(collector)
            collector = dict()

    else:
        raise Exception("collector type %s is not registered", collector_type)

    return collectors


def parse_hostnames(hostname_str):
    hostnames = hostname_str.split(',')
    hostnames = [item.strip() for item in hostnames]
    return set(hostnames)
