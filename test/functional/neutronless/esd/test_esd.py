# coding=utf-8
# Copyright 2017 F5 Networks Inc.
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
"""These are tests of the ESD (Enhanced Services Definition) feature.

ESDs are defined here:

https://devcentral.f5.com/articles/customizing-openstack-lbaasv2-using-enhanced-services-definitions-25681

Classes of tests in this module include:

* Basic Functionality Tests:
   These tests load and apply ESDs from an example ESD config:
    f5-openstack-agent/etc/neutron/services/f5/esd/demo.json

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
from requests.packages import urllib3

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver

from ..testlib.bigip_client import BigIpClient
from ..testlib.fake_rpc import FakeRPCPlugin
from ..testlib.resource_validator import ResourceValidator
from ..testlib.service_reader import LoadbalancerReader

urllib3.disable_warnings()
LOG = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def services():
    """Load testdata services that were produced by scripting neutron."""
    neutron_services_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/service_requests/l7_esd.json')
    )
    s = json.load(open(neutron_services_filename),
                  object_pairs_hook=collections.OrderedDict)
    return s


@pytest.fixture()
def icd_config():
    """Configure the icontrol_driver by mocking an historical oslo confg."""
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../config/overcloud_basic_agent_config.json')
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password

    return config


@pytest.fixture(scope="module")
def bigip():
    """Return a device-connected, agent-style, BigIpClient."""
    return BigIpClient(pytest.symbols.bigip_mgmt_ip_public,
                       pytest.symbols.bigip_username,
                       pytest.symbols.bigip_password)


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
    return icd


@pytest.fixture
def esd():
    """Return an esd dict containing state specced in demo.json."""
    esd_file = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '../../testdata/esds/demo.json')
    )
    return (json.load(open(esd_file)))


TESTINFRA = collections.namedtuple(
    "TESTINFRA", ('apply_service', 'remove_service', 'icontrol_driver', 'esd',
                  'validator', 'folder', 'listener', 'esd_name')
)


@pytest.fixture
def setup(request, bigip, services, icd_config, icontrol_driver, esd):
    """Build/Remove an invariant test environment.

    NOTE:  This fixture is modfiying the state of the BigIP device.  That is
    it's purpose and the "place" where tests require a constant environment.

    This fixture creates the requisite loadbalancer, listener, and pool, on the
    device prior to test initiation, and removes them after the ESD test is
    performed.   It also invokes the introspection necessary to customize test
    behavior as a function of the function name. The logic for this step is in
    the _set_esd function.
    """
    icontrol_driver.lbaas_builder.esd.esd_dict = esd
    env_prefix = icd_config['environment_prefix']
    validator = ResourceValidator(bigip, env_prefix)

    # create loadbalancer
    service = services['create_loadbalancer']
    lb_reader = LoadbalancerReader(service)
    folder = '{0}_{1}'.format(env_prefix, lb_reader.tenant_id())
    icontrol_driver._common_service_handler(service)
    assert bigip.folder_exists(folder)

    # create listener
    service = services['create_listener']
    listener = service['listeners'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_virtual_valid(listener, folder)

    # create pool
    service = services['create_pool']
    pool = service['pools'][0]
    icontrol_driver._common_service_handler(service)
    validator.assert_pool_valid(pool, folder)

    def teardown():
        """Teardown and verify removal of the testbed."""
        # delete pool (and member, node)
        service = services['delete_pool']
        icontrol_driver._common_service_handler(service)
        validator.assert_pool_deleted(pool, None, folder)

        # delete listener
        service = services['delete_listener']
        icontrol_driver._common_service_handler(service)
        validator.assert_virtual_deleted(listener, folder)

        # delete loadbalancer
        service = services['delete_loadbalancer']
        icontrol_driver._common_service_handler(service, delete_partition=True)
        assert not bigip.folder_exists(folder)

    request.addfinalizer(teardown)
    apply_service, remove_service, esd_name = _set_esd(services, request)
    ti = TESTINFRA(apply_service,
                   remove_service,
                   icontrol_driver,
                   esd,
                   validator,
                   folder,
                   listener,
                   esd_name)
    return ti


def _set_esd(services, request):
    """Extract the test name and process it as described above."""
    literal_esd_name = request.function.__name__.partition('test_esd_')[2]
    full_esd_name = 'f5_ESD_' + literal_esd_name
    new_apply_esd = deepcopy(services["apply_ABSTRACT_ESD"])
    new_remove_esd = deepcopy(services["remove_ABSTRACT_ESD"])
    new_apply_esd['l7policies'][0]['name'] = full_esd_name
    new_remove_esd['l7policies'][0]['name'] = full_esd_name
    return new_apply_esd, new_remove_esd, full_esd_name


def _apply_validate_remove_validate(infra):
    """Apply an ESD, validate application, remove ESD, validate removal."""
    i = infra
    # apply ESD
    i.icontrol_driver._common_service_handler(i.apply_service)
    i.validator.assert_esd_applied(i.esd[i.esd_name], i.listener, i.folder)

    # remove ESD
    i.icontrol_driver._common_service_handler(i.remove_service)
    i.validator.assert_virtual_valid(i.listener, i.folder)
    i.validator.assert_esd_removed(i.esd[i.esd_name], i.listener, i.folder)


def test_setup_teardown(setup):
    """Stub test that sanity checks setup and teardown."""
    pass


def test_esd_two_irules(setup):
    """Refactor of an historical test of a 2 irule ESD."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


# Single tag tests, each individual tag is tested.
def test_esd_lbaas_ctcp(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_stcp(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_cssl_profile(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_sssl_profile(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_irule(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_policy(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_persist(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_lbaas_fallback_persist(setup):
    """Test a single tag."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)


def test_esd_full_8_tag_set(setup):
    """Test of a full tag set.  Tags specifics are historical."""
    infrastructure = setup
    _apply_validate_remove_validate(infrastructure)
