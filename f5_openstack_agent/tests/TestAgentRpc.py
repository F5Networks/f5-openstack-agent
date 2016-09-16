
import datetime
import json
import netaddr
import sys
from time import time
import uuid
from pprint import pprint

from oslo_config import cfg
import oslo_messaging as messaging

from neutron.api.v2 import attributes
from neutron.common import constants as q_const
from neutron.common import rpc as q_rpc
from neutron.context import get_admin_context
from neutron.db import agents_db
from neutron.plugins.common import constants

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2

from neutron_lbaas.services.loadbalancer.drivers.abstract_driver \
    import LoadBalancerAbstractDriver  # @UnresolvedImport @Reimport
from neutron_lbaas.extensions \
    import lbaas_agentscheduler  # @UnresolvedImport @Reimport
from neutron_lbaas.db.loadbalancer import loadbalancer_db as lb_db
from oslo_log import log as logging
from oslo_utils import importutils
from neutron_lbaas.extensions.loadbalancer \
    import MemberNotFound  # @UnresolvedImport @Reimport
from neutron_lbaas.extensions.loadbalancer \
    import PoolNotFound  # @UnresolvedImport @Reimport
from neutron_lbaas.extensions.loadbalancer \
    import VipNotFound  # @UnresolvedImport @Reimport
from neutron_lbaas.extensions.loadbalancer \
    import HealthMonitorNotFound  # @UnresolvedImport @Reimport

import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 

def make_msg(method, **kwargs):
    return {'method': method,
            'args': kwargs}

if __name__ == '__main__':

    with open('service.json') as service_data:
        data = json.load(service_data)

    service = data['service']
    loadbalancer_id = service['loadbalancer']['id']

    topic = '%s.%s' % (constants_v2.TOPIC_LOADBALANCER_AGENT_V2, cfg.CONF.host)
    topic = 'f5-lbaasv2-process-on-agent_Test.ubuntu-devstack-2:b33cd191-4ea1-5ee8-bc88-7ded6c72f2c7'
    #topic = 'f5-lbaasv2-process-on-controller_Test.ubuntu-devstack-2:b33cd191-4ea1-5ee8-bc88-7ded6c72f2c7'
    default_version = '1.0'

    q_rpc.init(cfg.CONF)

    transport = messaging.get_transport(cfg.CONF)
    target = messaging.Target(topic=topic)

    client = messaging.RPCClient(transport, target)

    ctxt={}
    arg="hello agent"
    ret = client.cast(ctxt, 'test_rpc', arg=arg)

    ret = client.call(ctxt, 'test_rpc', arg=arg)
    print ret

    message = make_msg('create_loadbalancer', loadbalancer=loadbalancer_id, service=service)

    client.cast(ctxt, 'create_loadbalancer',  loadbalancer=loadbalancer_id, service=service)

