# -*- coding: utf-8 -*-

import eventlet
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.db import queries
from f5_openstack_agent.lbaasv2.drivers.bigip.resync import options
from f5_openstack_agent.lbaasv2.drivers.bigip.resync import resync_icontrol
from oslo_config import cfg
import time
eventlet.monkey_patch()

options.load_options()
options.parse_options()
conf = cfg.CONF


def service_exists(lb_id):
    print ("process lb_id: %s" % lb_id)
    db_query = queries.Queries()
    # we do not use db rpc right now
    db_rpcclient = None
    icontrol = resync_icontrol.ResynciControlDriver(
        conf, db_query, db_rpcclient)
    icontrol.connect()
    icontrol.service_exists(lb_id)


def check_resource(loadbalancers, th_pool=1):
    green_pool = eventlet.GreenPool(th_pool)
    for lb in loadbalancers:
        green_pool.spawn(service_exists, lb.id)
    green_pool.waitall()


def check_by_agent(agent_id, th_pool=1):
    query = queries.Queries()
    loadbalancers = query.get_loadbalancers_by_agent_id(agent_id)
    t1 = time.time()
    check_resource(loadbalancers, th_pool)
    t2 = time.time()
    elapse = t2 - t1
    print("Check agent: %s finished, time elapse: %s seconds" % (
        agent_id, elapse))


def check_by_project(project_id, th_pool=1):
    query = queries.Queries()
    loadbalancers = query.get_loadbalancers_by_project_id(project_id)
    t1 = time.time()
    check_resource(loadbalancers, th_pool)
    t2 = time.time()
    elapse = t2 - t1
    print("Check project: %s finished, time elapse: %s seconds" % (
        project_id, elapse))


def check_by_loadbalancer(lb_id, th_pool=1):
    query = queries.Queries()
    loadbalancer = query.get_loadbalancer(lb_id)
    t1 = time.time()
    check_resource([loadbalancer], th_pool)
    t2 = time.time()
    elapse = t2 - t1
    print("Check loadbalancer: %s finished, time elapse: %s seconds" % (
        lb_id, elapse))


def main():
    t1 = time.time()
    th_pool = conf.thread_pool
    if th_pool < 1:
        raise Exception("f5-check-thread cannot be set as: %s", th_pool)

    if conf.f5_agent:
        check_by_agent(conf.f5_agent, th_pool)
    elif conf.f5_project:
        check_by_project(conf.f5_project, th_pool)
    elif conf.f5_loadbalancer:
        check_by_loadbalancer(conf.f5_loadbalancer, th_pool)
    else:
        raise Exception("Provide an ID corresponding to the check level "
                        "--f5-agent/--f5-project/--f5-loadbalancer")
    t2 = time.time()
    elapse = t2 - t1
    print ("all check finishe, time elapse is: %s" % elapse)
