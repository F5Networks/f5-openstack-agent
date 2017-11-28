# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""This is the test infrastructure for test_name driven testing.

   'Experiments' are 'Test Regimes', i.e. specific combinations of services
   and ESDs of interest.
   The tests baseed on this approach load and apply ESDs from an example ESD
config:

   Each test looks up the specific ESD appended to the "test_esd_" string in
the test name, it then takes the resulting suffix, and prepends "f5_ESD_" to it
such that the result matches on of the example ESD names.
   For example "def test_esd_lbaas_ctcp" is processed in the following way:
      test_esd_lbaas_ctcp --> lbaas_ctcp --> f5_ESD_lbaas_ctcp

   The final "f5_ESD_${NAME}" string is then used to index into the ESD object.

   The test uses the customized (test specific) name to construct a pair of
custom service objects "apply_service" and "remove_service" that specify
the ESD named in the test-name.  That is, the "apply_service" object in the
"test_esd_lbaas_ctcp" test contains the ESD name "f5_ESD_lbaas_ctcp".

   The "apply_service" is then acted on by passing it as the argument to the
icontrol_driver._commen_service_handler method.  The effect is validated (or
the test FAILs), and the "remove_service" is then effected, and validated.

   It's not impossible that a FAIL at this point in the test could cause an
ERROR in teardown.
"""
import collections
from copy import deepcopy
import json
import logging
import os

import pytest
import requests

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver

from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.resource_validator import ResourceValidator

requests.packages.urllib3.disable_warnings()
LOG = logging.getLogger(__name__)


global TENANT_ID
global FOLDER
global ENV_PREFIX
global VALIDATOR


@pytest.fixture(scope="module")
def services():
    """Load testdata services that were produced by scripting neutron.

    WARNING: THIS FUNCTION SETS A MODULE_LEVEL GLOBAL!
    """
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/l7_esd.json')
    )
    s = json.load(open(neutron_services_filename),
                  object_pairs_hook=collections.OrderedDict)
    global TENANT_ID
    TENANT_ID = s["create_loadbalancer"]["loadbalancer"]["tenant_id"]
    return s


@pytest.fixture(scope="module")
def icd_config(services):
    """Configure the icontrol_driver by mocking an historical oslo confg.

    WARNING: THIS FUNCTION SETS A MODULE_LEVEL GLOBAL!
    """
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../config/overcloud_basic_agent_config.json')
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password
    global ENV_PREFIX
    ENV_PREFIX = config['environment_prefix']
    global FOLDER
    FOLDER = '{0}_{1}'.format(ENV_PREFIX, TENANT_ID)
    return config


@pytest.fixture(scope="module")
def bigip(icd_config):
    """Return a device-connected, agent-style, BigIpClient."""
    bigip = BigIpClient(pytest.symbols.bigip_mgmt_ip_public,
                        pytest.symbols.bigip_username,
                        pytest.symbols.bigip_password)
    global VALIDATOR
    VALIDATOR = ResourceValidator(bigip, ENV_PREFIX)
    return bigip


@pytest.fixture
def fake_plugin_rpc(services):
    """Return an object to patch out the RPC Plugin with."""
    rpcObj = FakeRPCPlugin(services)

    return rpcObj


@pytest.fixture
def icontrol_driver(icd_config, fake_plugin_rpc):
    """Return a patched icontrol_driver. Config and RPC_plugin are fakes."""
    class ConfFake(object):
        """A configuration Fake that matches the oslo conf interface."""

        def __init__(self, params):
            self.__dict__ = params
            for k, v in self.__dict__.items():
                if isinstance(v, unicode):
                    self.__dict__[k] = v.encode('utf-8')

        def __repr__(self):
            return repr(self.__dict__)

    icd = iControlDriver(ConfFake(icd_config),
                         registerOpts=False)

    icd.plugin_rpc = fake_plugin_rpc
    icd.connect()

    return icd


def load_esd(target_esd):
    """Return an esd dict containing state specced in demo.json."""
    osd = os.path.dirname
    ESDDIRNAME = os.path.join(osd(osd(osd(os.path.abspath(__file__)))),
                              "testdata",
                              "esds")
    esd_file = os.path.join(ESDDIRNAME, target_esd)
    return (json.load(open(esd_file)))


TESTINFRA = collections.namedtuple(
    "TESTINFRA", ('apply_service', 'remove_service', 'icontrol_driver', 'esd',
                  'listener', 'esd_name')
)


def _create_loadbalancer(services, icontrol_driver, bigip):
    service = services['create_loadbalancer']
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(FOLDER)


def _create_listener(services, icontrol_driver):
    service = services['create_listener']
    listener = service['listeners'][0]
    icontrol_driver._common_service_handler(service)
    VALIDATOR.assert_virtual_valid(listener, FOLDER)
    return listener


def _create_pool(services, icontrol_driver):
    service = services['create_pool']
    pool = service['pools'][0]
    icontrol_driver._common_service_handler(service)
    VALIDATOR.assert_pool_valid(pool, FOLDER)
    return pool


def _delete_pool(services, icontrol_driver, pool):
    service = services['delete_pool']
    icontrol_driver._common_service_handler(service)
    VALIDATOR.assert_pool_deleted(pool, None, FOLDER)


def _delete_listener(services, icontrol_driver, listener):
    service = services['delete_listener']
    icontrol_driver._common_service_handler(service)
    VALIDATOR.assert_virtual_deleted(listener, FOLDER)


def _delete_loadbalancer(services, icontrol_driver, bigip):
    service = services['delete_loadbalancer']
    icontrol_driver._common_service_handler(service, delete_partition=True)
    assert not bigip.folder_exists(FOLDER)


def _set_esd(services, request):
    """Extract the test name and process it as described above."""
    literal_esd_name = request.function.__name__.partition('test_esd_')[2]
    full_esd_name = 'f5_ESD_' + literal_esd_name
    new_apply_esd = deepcopy(services["apply_ABSTRACT_ESD"])
    new_remove_esd = deepcopy(services["remove_ABSTRACT_ESD"])
    new_apply_esd['l7policies'][0]['name'] = full_esd_name
    new_remove_esd['l7policies'][0]['name'] = full_esd_name
    return new_apply_esd, new_remove_esd, full_esd_name


Context = collections.namedtuple("Context", ("listener", "pool"))


@pytest.fixture
def Experiment(request, bigip, services, icd_config, icontrol_driver):
    """Build/Remove an invariant test environment.

    NOTE:  This fixture is modfiying the state of the BigIP device.  That is
    it's purpose and the "place" where tests require a constant environment.

    This fixture creates the requisite loadbalancer, listener, and pool, on the
    device prior to test initiation, and removes them after the ESD test is
    performed.   It also invokes the introspection necessary to customize test
    behavior as a function of the function name. The logic for this step is in
    the _set_esd function.
    """
    # create loadbalancer
    _create_loadbalancer(services, icontrol_driver, bigip)
    # create listener
    listener = _create_listener(services, icontrol_driver)
    # create pool
    pool = _create_pool(services, icontrol_driver)

    def teardown():
        """Teardown and verify removal of the testbed."""
        # delete pool (and member, node)
        _delete_pool(services, icontrol_driver, pool)
        # delete listener
        _delete_listener(services, icontrol_driver, listener)
        # delete loadbalancer
        _delete_loadbalancer(services, icontrol_driver, bigip)

    request.addfinalizer(teardown)
    return Context(listener, pool)


@pytest.fixture
def ESD_Experiment(Experiment, request, services, icontrol_driver):
    """Run tests in a single tag-per-ESD regime, the base (control) case."""
    demo_esd = load_esd("demo.json")
    icontrol_driver.lbaas_builder.esd.esd_dict = demo_esd
    apply_service, remove_service, esd_name = _set_esd(services, request)
    ti = TESTINFRA(apply_service,
                   remove_service,
                   icontrol_driver,
                   demo_esd,
                   Experiment.listener,
                   esd_name)
    return ti


@pytest.fixture
def ESD_Pairs_Experiment(Experiment, request, services, icontrol_driver):
    """Run tests in a regime run ESDs that contain pairs of tags."""
    demo_esd = load_esd("esd_pairs.json")
    icontrol_driver.lbaas_builder.esd.esd_dict = demo_esd
    apply_service, remove_service, esd_name = _set_esd(services, request)
    ti = TESTINFRA(apply_service,
                   remove_service,
                   icontrol_driver,
                   demo_esd,
                   Experiment.listener,
                   esd_name)
    return ti


def apply_validate_remove_validate(infra):
    """Apply an ESD, validate application, remove ESD, validate removal."""
    i = infra
    # apply ESD
    i.icontrol_driver._common_service_handler(i.apply_service)
    VALIDATOR.assert_esd_applied(i.esd[i.esd_name], i.listener, FOLDER)

    # remove ESD
    i.icontrol_driver._common_service_handler(i.remove_service)
    VALIDATOR.assert_virtual_valid(i.listener, FOLDER)
    VALIDATOR.assert_esd_removed(i.esd[i.esd_name], i.listener, FOLDER)
