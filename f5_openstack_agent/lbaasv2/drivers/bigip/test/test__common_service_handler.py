import copy
import json
import mock
import os
from pprint import pprint as pp
import pytest
from pytest import symbols
import requests

from oslo_config import cfg

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver

requests.packages.urllib3.disable_warnings()

opd = os.path.dirname
DISTRIBUTIONROOT = opd(opd(opd(opd(opd(opd(__file__))))))
del opd
SERVICELIBDIR = os.path.join(DISTRIBUTIONROOT,
                             'devtools',
                             'sample_data',
                             'service_library')
CREATE = json.load(open(os.path.join(SERVICELIBDIR, 'create.json'), 'r'))


def test__common_service_handler(bigip, neutronless_wrappedicontroldriver):
    mgmt_rt = bigip
    nless_wicd = neutronless_wrappedicontroldriver
    print(type(symbols))
    print(symbols.debug)
    print(nless_wicd.hostnames)
    #pp(CREATE)
    partition_names = [x.name for x in mgmt_rt.tm.sys.folders.get_collection()]
    pp(partition_names)
    original_create = copy.deepcopy(CREATE) 
    
    nless_wicd._common_service_handler(CREATE)
    try:
        print('after _common_service_handler: %r' % CREATE['traffic_group'])
    except KeyError:
        pass
    pp(nless_wicd.plugin_rpc.call_args_list)
