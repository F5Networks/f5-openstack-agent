#!/usr/bin/python
import getopt
import logging
import sys

from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2

from neutron.common import rpc as q_rpc

from oslo_config import cfg

import oslo_messaging as messaging

try:
    from neutron_lib import context as ncontext
except ImportError:
    from neutron import context as ncontext


logging.basicConfig()


def __usage():
    print("update-lb <lb-id> <status: [active|error]> -u [url]"
          " -e [exchange] -p [prefix]")


def update_lb():

    argv = sys.argv[1:]

    number = len(argv)
    if number < 2:
        __usage()
        return

    lb_id = argv[0]
    lb_status = argv[1]
    prefix = 'Project'
    exchange = 'neutron'
    url = None

    argv = argv[2:]

    try:
        opts, args = getopt.getopt(argv, "e:p:u:")
    except getopt.GetoptError:
        __usage()
        return

    for opt, arg in opts:
        if opt == '-e':
            exchange = arg
        elif opt == '-p':
            prefix = arg
        elif opt == '-u':
            url = arg
        else:
            __usage()
            return
    lb_status = lb_status.upper()
    if lb_status == 'ACTIVE':
        status = constants_v2.F5_ACTIVE
        operating_status = constants_v2.F5_ONLINE
    elif lb_status == 'ERROR':
        status = constants_v2.F5_ERROR
        operating_status = constants_v2.F5_OFFLINE
    else:
        print("We only suppport Active and Error status")
        return

    q_rpc.init(cfg.CONF)
    topic = '%s_%s' % (constants_v2.TOPIC_PROCESS_ON_HOST_V2, prefix)
    messaging.set_transport_defaults(control_exchange=exchange)
    transport = messaging.get_transport(cfg.CONF, url)
    target = messaging.Target(topic=topic,
                              version=constants_v2.RPC_API_VERSION)
    # client = q_rpc.get_client(target, version_cap=None)
    client = messaging.RPCClient(transport, target)

    ctxt = ncontext.get_admin_context().to_dict()
    client.call(ctxt, 'update_loadbalancer_status',
                loadbalancer_id=lb_id,
                status=status,
                operating_status=operating_status)
    transport.cleanup()
