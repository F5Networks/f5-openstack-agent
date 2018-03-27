# Copyright (c) 2016-2018, F5 Networks, Inc.
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
import logging

import pytest
import requests


from ..conftest import OSLOCONF
from ..conftest import TestConfig

requests.packages.urllib3.disable_warnings()
LOG = logging.getLogger(__name__)


@pytest.fixture
def demo_policy(request, bigip):
    """create a `demo_policy` in `Common` partition."""
    mgmt_root = bigip.bigip
    name = "demo_policy"
    partition = "Common"

    rules = [
        dict(
            name='demo_rule',
            ordinal=0,
            actions=[],
            conditions=[])
    ]

    def teardown_policy():
        if mgmt_root.tm.ltm.policys.policy.exists(
                name=name, partition=partition):
            pol = mgmt_root.tm.ltm.policys.policy.load(
                name=name, partition=partition)
            pol.delete()

    pc = mgmt_root.tm.ltm.policys

    # setting legacy to True inorder for the test
    # to work for BIGIP versions 11.5, 11.6, 12.1 and 13

    policy = pc.policy.create(name=name, partition=partition,
                              strategy="first-match",
                              rules=rules, legacy=True)
    request.addfinalizer(teardown_policy)
    return policy


@pytest.fixture
def Experiment(request):
    """Build/Remove an invariant test environment.

    NOTE:  This fixture is modfiying the state of the BigIP device.  That is
    it's purpose and the "place" where tests require a constant environment.

    This fixture creates the requisite loadbalancer, listener, and pool, on the
    device prior to test initiation, and removes them after the ESD test is
    performed.   It also invokes the introspection necessary to customize test
    behavior as a function of the function name. The logic for this step is in
    the define_esd_services method.
    """
    testconfig = TestConfig('l7_esd.json', OSLOCONF)
    # create loadbalancer
    testconfig.create_loadbalancer()
    # create listener
    testconfig.create_listener()
    # create pool
    testconfig.create_pool()

    def teardown():
        """Teardown and verify removal of the testbed."""
        # delete pool (and member, node)
        testconfig.delete_pool()
        # delete listener
        testconfig.delete_listener()
        # delete loadbalancer
        testconfig.delete_loadbalancer()

    request.addfinalizer(teardown)
    return testconfig


@pytest.fixture
def ESD_Experiment(Experiment, request):
    """Run tests in a single tag-per-ESD regime, the base (control) case."""
    testconfig = Experiment
    testconfig.load_esd("demo.json")
    testconfig.define_esd_services(request)
    return testconfig


@pytest.fixture
def ESD_GRF_False_Experiment(Experiment, request):
    """Run tests in a single tag-per-ESD regime, the base (control) case."""
    testconfig = Experiment
    testconfig.OSLO_CONF["f5_global_routed_mode"] = False
    testconfig.load_esd("demo.json")
    testconfig.define_esd_services(request)
    return testconfig


@pytest.fixture
def ESD_Pairs_Experiment(Experiment, request):
    """Run tests in a regime run ESDs that contain pairs of tags."""
    testconfig = Experiment
    testconfig.load_esd("esd_pairs.json")
    testconfig.define_esd_services(request)
    return testconfig


def apply_validate_remove_validate(testconfig):
    """Apply an ESD, validate application, remove ESD, validate removal."""
    t = testconfig
    # apply ESD
    t.icontrol_driver._common_service_handler(t.apply_esd)
    t.validator.assert_esd_applied(t.esd[t.full_esd_name],
                                   t.listener,
                                   t.FOLDER)

    # remove ESD
    t.icontrol_driver._common_service_handler(t.remove_esd)
    t.validator.assert_virtual_valid(t.listener, t.FOLDER)
    t.validator.assert_esd_removed(t.esd[t.full_esd_name],
                                   t.listener,
                                   t.FOLDER)
