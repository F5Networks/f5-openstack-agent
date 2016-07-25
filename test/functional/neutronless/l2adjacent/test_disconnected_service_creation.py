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


import json
import mock
import pytest
import requests
import time

from f5.utils.testutils.registrytools import register_device
requests.packages.urllib3.disable_warnings()


from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import\
    iControlDriver

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Toggle feature on/off configurations
OSLO_CONFIGS = json.load(open('oslo_confs.json'))
FEATURE_ON = OSLO_CONFIGS["feature_on"]
FEATURE_OFF = OSLO_CONFIGS["feature_off"]


# LIbrary of services as received from the neutron server
NEUTRON_SERVICES = json.load(open('neutron_services.json'))
SEGID_CREATELB = NEUTRON_SERVICES["create_connected_loadbalancer"]
NOSEGID_CREATELB = NEUTRON_SERVICES["create_disconnected_loadbalancer"]
SEGID_CREATELISTENER = NEUTRON_SERVICES["create_connected_listener"]
NOSEGID_CREATELISTENER = NEUTRON_SERVICES["create_disconnected_listener"]

# BigIP device states observed via f5sdk.
SEG_INDEPENDENT_LB_URIS =\
    set([u'https://localhost/mgmt/tm/sys/folder/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/route-domain/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver=11.5.0',

         'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~disconnected_network?ver=11.6.0'])

SEG_DEPENDENT_LB_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/snat-translation/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~snat-traffic-group-local-only'
         '-ce69e293-56e7-43b8-b51c-01b91d66af20_0?ver=11.6.0',

         u'https://localhost/mgmt/tm/ltm/snatpool/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/fdb/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d~tunnel-vxlan-46?ver=11.5.0',

         u'https://localhost/mgmt/tm/net/self/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~local-bigip1-ce69e293-56e7-43b8-b51c-01b91d66af20?ver=11.6.0',

         u'https://localhost/mgmt/tm/net/tunnels/tunnel/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~tunnel-vxlan-46?ver=11.6.0'])

LISTENER_SPECIFIC_URIS =\
    set([u'https://localhost/mgmt/tm/ltm/virtual-address/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~10.2.2.140%251?ver=11.6.0',

         u'https://localhost/mgmt/tm/ltm/virtual/'
         '~TEST_128a63ef33bc4cf891d684fad58e7f2d'
         '~SAMPLE_LISTENER?ver=11.6.0'])


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


def test_featureoff_withsegid_lb(setup_neutronless_test, configure_icd, bigip):
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_OFF)
    icontroldriver._common_service_handler(SEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS


@pytest.mark.skip(reason="This test will not pass until the feature short'\
    ' circuits prior to network service initialization, in the absence of'\
    ' a segid.")
def test_featureoff_nosegid_lb(setup_neutronless_test, configure_icd, bigip):
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_OFF)
    icontroldriver._common_service_handler(NOSEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS


def test_withsegid_lb(setup_neutronless_test, configure_icd, bigip):
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_ON)
    icontroldriver._common_service_handler(SEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS | SEG_DEPENDENT_LB_URIS


def test_nosegid_lb(setup_neutronless_test, configure_icd, bigip):
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_ON)
    icontroldriver._common_service_handler(NOSEGID_CREATELB)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris == SEG_INDEPENDENT_LB_URIS


@pytest.mark.skip(reason="This test will not pass until triggering the'\
    ' timeout condition logs a message with the appropriate literal string.'\
    ' Perhaps this will occur when the short-circuit-for-segless bug is'\
    ' fixed.")
def test_nosegid_lb_timeout(setup_neutronless_test, configure_icd, bigip):
    # Configure
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_ON)
    gtimeout = icontroldriver.conf.f5_network_segment_gross_timeout
    poll_interval = icontroldriver.conf.f5_network_segment_polling_interval
    # Set timers
    start_time = time.time()
    timeout = start_time + gtimeout
    # Configure logging
    logger.propagate = False
    logger.removeHandler(logger.handlers[0])
    logger.setLevel(logging.ERROR)
    logfilename = '/root/devenv/f5-openstack-agent/test/functional/'\
                  'neutronless/l2adjacent/logtimeout.txt'
    timeoutfh = logging.FileHandler(logfilename)
    timeoutfh.setLevel(logging.ERROR)
    logger.addHandler(timeoutfh)
    # Begin operations
    while time.time() < (timeout + (2*poll_interval)):
        time.sleep(poll_interval)
        icontroldriver._common_service_handler(NOSEGID_CREATELB)
        create_registry = register_device(bigip)
        new_uris = set(create_registry.keys()) - set(start_registry.keys())
        assert new_uris == SEG_INDEPENDENT_LB_URIS
    timeoutfh.close()
    logger.removeHandler(logger.handlers[0])
    assert "TIMEOUT: failed to connect " in open(logfilename).read()


def test_nosegid_to_segid(setup_neutronless_test, configure_icd, bigip):
    # Configure
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_ON)
    rdscache = icontroldriver.network_builder.rds_cache
    logger.info(rdscache)
    gtimeout = icontroldriver.conf.f5_network_segment_gross_timeout
    poll_interval = icontroldriver.conf.f5_network_segment_polling_interval
    # Set timers
    start_time = time.time()
    timeout = start_time + gtimeout
    # Begin operations
    while time.time() < (timeout - (2*poll_interval)):
        time.sleep(poll_interval)
        icontroldriver._common_service_handler(NOSEGID_CREATELB)
        create_registry = register_device(bigip)
        new_uris = set(create_registry.keys()) - set(start_registry.keys())
        assert new_uris == SEG_INDEPENDENT_LB_URIS
    # Before gtimeout
    time.sleep(poll_interval)
    icontroldriver._common_service_handler(SEGID_CREATELISTENER)
    logger.info(rdscache)
    create_registry = register_device(bigip)
    new_uris = set(create_registry.keys()) - set(start_registry.keys())

    assert new_uris ==\
        SEG_INDEPENDENT_LB_URIS |\
        SEG_DEPENDENT_LB_URIS |\
        LISTENER_SPECIFIC_URIS


@pytest.mark.skip(reason="When run subsequent to the 'test_nosegid_to_segid'\
    ' test above this test fails implying a 'StateFul agent bug. I will'\
    ' attempt to replicate on liberty.")
def test_segid_listener_create(setup_neutronless_test, configure_icd, bigip):
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_ON)
    rdscache = icontroldriver.network_builder.rds_cache
    logger.info(rdscache)
    icontroldriver._common_service_handler(SEGID_CREATELISTENER)
    logger.info(rdscache)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris ==\
        SEG_INDEPENDENT_LB_URIS |\
        SEG_DEPENDENT_LB_URIS |\
        LISTENER_SPECIFIC_URIS


@pytest.mark.skip(reason="When run subsequent to the 'test_nosegid_to_segid'\
    ' test above this test fails implying a 'StateFul agent bug. I will'\
    ' attempt to replicate on liberty.")
def test_route_domain_naming(setup_neutronless_test, configure_icd, bigip):
    start_registry = register_device(bigip)
    icontroldriver = configure_icd(FEATURE_ON)
    rdscache = icontroldriver.network_builder.rds_cache
    logger.info(rdscache)
    icontroldriver._common_service_handler(SEGID_CREATELISTENER)
    logger.info(rdscache)
    after_create_registry = register_device(bigip)
    new_uris = set(after_create_registry.keys()) - set(start_registry.keys())
    assert new_uris ==\
        SEG_INDEPENDENT_LB_URIS |\
        SEG_DEPENDENT_LB_URIS |\
        LISTENER_SPECIFIC_URIS
