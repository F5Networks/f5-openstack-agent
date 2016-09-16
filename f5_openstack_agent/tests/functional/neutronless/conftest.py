# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import mock
import os
import pytest
import time

from f5.utils.testutils.registrytools import register_device
from f5_os_test.order_utils import AGENT_LB_DEL_ORDER
from f5_os_test.order_utils import order_by_weights
from icontrol.exceptions import iControlUnexpectedHTTPError

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver


class MatchFilter(logging.Filter):
    def __init__(self, match_strings):
        self.match_strings = match_strings

    def filter(self, record):
        msg = record.getMessage()
        for match in self.match_strings:
            if match in msg:
                return True
        return False


error_filter = MatchFilter(['ERROR',
                            'error',
                            'Error',
                            'Exception',
                            'exception'])


@pytest.fixture(scope='module')
def makelogdir(request):
    logtime = '%0.0f' % time.time()
    dirname = os.path.dirname(request.module.__file__)
    modfname = request.module.__name__
    logdirname = os.path.join(dirname, 'logs', modfname, logtime)
    os.makedirs(logdirname)
    return logdirname


def _get_nolevel_handler(logname):
    rootlogger = logging.getLogger()
    for h in rootlogger.handlers:
        rootlogger.removeHandler(h)
    rootlogger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(logname)
    fh.setLevel(logging.DEBUG)
    rootlogger.addHandler(fh)
    return fh


def remove_elements(bigip, uris):
    for t in bigip.tm.net.fdb.tunnels.get_collection():
        if t.name != 'http-tunnel' and t.name != 'socks-tunnel':
            t.update(records=[])
    registry = register_device(bigip)
    ordered = order_by_weights(uris, AGENT_LB_DEL_ORDER)
    for selfLink in ordered:
        try:
            if selfLink in registry:
                registry[selfLink].delete()
        except iControlUnexpectedHTTPError as exc:
            if exc.response.status_code == 404:
                logging.debug(exc.response.status_code)
            else:
                raise


def setup_neutronless_test(request, bigip, makelogdir):
    pretest_snapshot = frozenset(register_device(bigip))

    logname = os.path.join(makelogdir, request.function.__name__)
    loghandler = _get_nolevel_handler(logname)

    def remove_test_created_elements():
        posttest_registry = register_device(bigip)
        created = frozenset(posttest_registry) - pretest_snapshot
        remove_elements(bigip, created)
        rootlogger = logging.getLogger()
        rootlogger.removeHandler(loghandler)

    request.addfinalizer(remove_test_created_elements)
    return loghandler


@pytest.fixture
def configure_icd():
    class ConfFake(object):
        '''minimal fake config object to replace oslo with controlled params'''
        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    def _icd(icd_config):
        mock_rpc_plugin = mock.MagicMock()
        mock_rpc_plugin.get_port_by_name.return_value =\
            [{'fixed_ips': [{'ip_address': '10.2.2.134'}]}]
        icontroldriver = iControlDriver(ConfFake(icd_config),
                                        registerOpts=False)
        icontroldriver.plugin_rpc = mock_rpc_plugin
        return icontroldriver
    return _icd
