# coding=utf-8
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
"""In addition to pytest fixtures this module also contains general classes.

    These classes are TestConfig, and Resource4TestTracker.

    TestConfig:  This is a Python class designed to contain the configurable
state and methods generally needed during testing.  The general approach is
to provide a configuration specific to some test needs via the TestConfig
objects methods (primarily, __init__, but also others e.g. "load_esd").

   The expected caller of the TestConfig object is an Experiment fixture, where
the experiment instantiates, and configures, a particular TestConfig instance,
before handing off to the test code.   Examples of "Experiments" can be found
in esd/conftest.py.
"""

import collections
from collections import deque
from collections import namedtuple
from copy import deepcopy
from inspect import currentframe as cf
from inspect import getframeinfo as gfi
from inspect import getouterframes as gof
import json
import os
from os.path import dirname as opd
from os.path import join as opj
import pytest
import re
import sys
import traceback

from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver

from .bigip_interaction import BigIpInteraction
from .testlib.bigip_client import BigIpClient
from .testlib.fake_rpc import FakeRPCPlugin
from .testlib.resource_validator import ResourceValidator

DEBUG = True  # sys.flags.debug

DATADIR = opj(opd(opd(os.path.abspath(__file__))), "testdata")
CONFIGDIR = opj(opd(DATADIR), "config")
ESD_dir = opj(DATADIR, "esds")
req_services_dir = opj(DATADIR, "service_requests")
OSLOCONF = 'overcloud_basic_agent_config.json'


class TestConfig(object):
    """A configuration tool, Experiment fixtures use the public interface."""

    def __init__(self,
                 service_requests_file,
                 oslo_config_file):
        """Neutronless tests expect the state specified here.

        self.oslo_config:  A faked interface to the oslo configuration system
        self.TENANT_ID:    Usually a static fake specific to our test regime.
        self.SERVICES:     Obtained by running replay scripts against neutron,
        we use these services to patch out neutron, by playing them through
        the icontrol_driver._common_service_handler.
        self.fake_rpc_OBJ: We can observe messages intended for neutron by
        monitoring this.
        self.ENV_PREFIX -FOLDER -OSLO_CONF:  Values set up for integration
        tests (these tests run against a real bigip).
        self.bigip:  The _agent's_ interface to a device (wraps the SDK).
        self.validator:   A useful object that checks specific configurations
        of the bigip according to agent-derived rules.
        self.icontrol_driver:  An agent-internal method that submits service
        objects (from neutron) to be interpreted and applied to the device.
        """
        self.oslo_config = json.load(open(opj(CONFIGDIR, oslo_config_file)))
        self.TENANT_ID, self.SERVICES =\
            self.load_service(service_requests_file)
        self.fake_rpc_OBJ = self.fake_plugin_rpc()
        self.ENV_PREFIX, self.FOLDER, self.OSLO_CONF = self.icd_config()
        self.bigip, self.validator = self.bigip()
        self.icontrol_driver = self.icontrol_driver()

    def load_service(self, service_file_name):
        """Load testdata services that were produced by scripting neutron."""
        neutron_services_filename = opj(req_services_dir, service_file_name)
        SERVICE = json.load(open(neutron_services_filename),
                            object_pairs_hook=collections.OrderedDict)
        TENANT_ID = SERVICE["create_loadbalancer"]["loadbalancer"]["tenant_id"]
        return TENANT_ID, SERVICE

    def load_esd(self, esd_file):
        """Obtain an esd for test, and attach it to an internal object."""
        self.esd = json.load(open(opj(ESD_dir, esd_file)))
        self.icontrol_driver.lbaas_builder.esd.esd_dict = self.esd

    def define_esd_services(self, request):
        """Extract the test name and process it as described above."""
        literal_esd_name = request.function.__name__.partition('test_esd_')[2]
        self.full_esd_name = 'f5_ESD_' + literal_esd_name
        self.apply_esd = deepcopy(self.SERVICES["apply_ABSTRACT_ESD"])
        self.remove_esd = deepcopy(self.SERVICES["remove_ABSTRACT_ESD"])
        self.apply_esd['l7policies'][0]['name'] = self.full_esd_name
        self.remove_esd['l7policies'][0]['name'] = self.full_esd_name

    def fake_plugin_rpc(self):
        """Return an object to patch out the RPC Plugin with."""
        rpcObj = FakeRPCPlugin(self.SERVICES)

        return rpcObj

    def icd_config(self):
        """Configure the icontrol_driver by mocking an historic oslo confg."""
        config = deepcopy(self.oslo_config)
        config['icontrol_hostname'] = pytest.symbols.bigip_floating_ips[0]
        config['icontrol_username'] = pytest.symbols.bigip_username
        config['icontrol_password'] = pytest.symbols.bigip_password
        ENV_PREFIX = config['environment_prefix']
        FOLDER = '{0}_{1}'.format(ENV_PREFIX, self.TENANT_ID)
        return ENV_PREFIX, FOLDER, config

    def bigip(self):
        """Return a device-connected, agent-style, BigIpClient."""
        bigip = BigIpClient(pytest.symbols.bigip_floating_ips[0],
                            pytest.symbols.bigip_username,
                            pytest.symbols.bigip_password)
        VALIDATOR = ResourceValidator(bigip, self.ENV_PREFIX)
        return bigip, VALIDATOR

    def icontrol_driver(self):
        """Return a patched icontrol_driver. Conf and RPC_plugin are fakes."""
        class ConfFake(object):
            """A configuration Fake that matches the oslo conf interface."""

            def __init__(self, params):
                self.__dict__ = params
                for k, v in self.__dict__.items():
                    if isinstance(v, unicode):
                        self.__dict__[k] = v.encode('utf-8')

            def __repr__(self):
                return repr(self.__dict__)

        icd = iControlDriver(ConfFake(self.OSLO_CONF),
                             registerOpts=False)

        icd.plugin_rpc = self.fake_plugin_rpc()
        icd.connect()
        return icd

    def create_loadbalancer(self):
        """Config the device, via the agent, with the fake neutron message."""
        service = self.SERVICES['create_loadbalancer']
        self.icontrol_driver._common_service_handler(service)
        assert self.bigip.folder_exists(self.FOLDER)

    def create_listener(self):
        """Config the device, via the agent, with the fake neutron message."""
        service = self.SERVICES['create_listener']
        self.listener = service['listeners'][0]
        self.icontrol_driver._common_service_handler(service)
        self.validator.assert_virtual_valid(self.listener, self.FOLDER)

    def create_pool(self):
        """Config the device, via the agent, with the fake neutron message."""
        service = self.SERVICES['create_pool']
        self.pool = service['pools'][0]
        self.icontrol_driver._common_service_handler(service)
        self.validator.assert_pool_valid(self.pool, self.FOLDER)

    def delete_pool(self):
        """Config the device, via the agent, with the fake neutron message."""
        service = self.SERVICES['delete_pool']
        self.icontrol_driver._common_service_handler(service)
        self.validator.assert_pool_deleted(self.pool, None, self.FOLDER)

    def delete_listener(self):
        """Config the device, via the agent, with the fake neutron message."""
        service = self.SERVICES['delete_listener']
        self.icontrol_driver._common_service_handler(service)
        self.validator.assert_virtual_deleted(self.listener, self.FOLDER)

    def delete_loadbalancer(self):
        """Config the device, via the agent, with the fake neutron message."""
        service = self.SERVICES['delete_loadbalancer']
        self.icontrol_driver._common_service_handler(service,
                                                     delete_partition=True)
        assert not self.bigip.folder_exists(self.FOLDER)


class Resource4TestTracker(object):
    """Creates an object meant for tracking states assigned to the BIG-IP

    This testing object will track the states that are assigned by the test
    from inside of the service operations on the agent.  Upon closure, it will
    destroy the objects in the revere order of the states that were assigned.

    Additionally, it will take the service object and attempt the cleanup of
    the provided cleanup# order.  Thus, if there is a set of keys:
        ['cleanup0', 'cleanup10', 'cleanup2']
    It will perform cleanup0, cleanup2, cleanup10 in that order.

    As a last attempt to cleanup the environment on the BIG-IP, it will provide
    the agent with a standard, empty configuration.
    """
    __entered = deque()
    _empty_config = {
        "loadbalancer": {}, "healthmonitors": [], "listeners": [],
        "members": [], "networks": {}, "pools": [], "subnets": {}}
    expected_chain = ['loadbalancer', 'listener', 'pool', 'member']

    def __init__(self, service, icontrol_driver, expected_chain=None):
        """obj = Resource4TestTracker(service, icontrol_driver)

        The typical use case of this object is to encapsulate it within a
        'with' statement:
            expected_chain = ['loadbalancer', 'listener', 'pool', 'member']
            with Resource4TestTracker(states, icontrol_driver,
                                      expected_chain=expected_chain) as handle:
                handle.deploy_next()
                # test against handle.state

                handle.cleanup()
                # test against cleaned state (proper destruction)

            # We are now stateless on the BIG-IP.

        OPTIONS:
            service - a dict that contains a set of keys that each represent
                a state for the BIG-IP to be in.  Each KVP contains a dict that
                then provides the BIG-IP with a state to be entering into.
            icontrol_driver - a (typically mocked or modified) instance of the
                agent's icontrol_driver.
            expected_chain - The expected state workflow that the test will
                require coming from the input data (service).
        """
        clean_re = re.compile("cleanup(\d+)")
        found = service.keys()
        expected_chain = expected_chain if expected_chain else \
            self.expected_chain
        possible = service.keys()
        cleanup_queue = list()
        for item in expected_chain:
            assert item in found, "{} not in service!".format(item)
            possible.remove(item)
        for item in possible:
            match = clean_re.search(item)
            if match:
                cleanup_queue.append(match)
        cleanup_queue.sort(key=lambda x: int(x.group(1)))
        self.cleanup_queue = map(lambda x: x.group(0), cleanup_queue)
        self.expected_chain = expected_chain
        self._set_service(service)
        self.icontrol_driver = icontrol_driver
        self._steps = iter(expected_chain)

    def __enter__(self):
        # there's nothing to construct, simply a process aspect at this time...
        return self

    def __exit__(self, *args, **kargs):
        # cleanup appropriately...
        self.cleanup()

    def __clear(self):
        # destroys in the derived order...
        exceptions = deque()
        Except = namedtuple('Except', 'type, message, stacktrace')
        while True:
            try:
                state_name = self.__entered.popleft()
            except IndexError:
                break
            state = self.service.get(self.__state_reflection(state_name), None)
            try:
                assert state, \
                    "{} not in service!  Cannot cleanup!".format(state_name)
                debug_msg("clearing with state({})".format(
                    self.__state_reflection(state_name)))
                self.icontrol_driver._common_service_handler(state)
            except AssertionError as Err:
                print(str(Err))
            except Exception as Error:
                exceptions.append(Except(str(type(Error)), str(Error),
                                  traceback.format_exc()))
        if exceptions:
            stacks = str()
            fmt = "{}({})\n{}\n"
            for error in exceptions:
                stacks = stacks + fmt.format(error.type, error.message,
                                             error.stacktrace)
            raise AssertionError("Teardown failed:\n{}".format(stacks))

    def __deploy_state(self, state_name, keep_state=True):
        # deploys a state-by-string
        state = self.service.get(state_name, None)
        assert state, "{} does not exist in service!".format(state_name)
        debug_msg("deploying state({})".format(state_name))
        self.icontrol_driver._common_service_handler(state)
        if keep_state:
            self._append(state_name, state)

    def __state_reflection(self, state):
        # This returns the expected delete format of the state given
        if 'cleanup' in state:
            return state
        return "delete_{}".format(state)

    def __triage_order(self):
        # return the extended cleanup order...
        self.__entered.extend(self.cleanup_queue)

    def _append(self, state_name, state):
        # add the state to the top of the FILO
        self.state = state
        self.state_name = state_name
        self.__entered.appendleft(state_name)

    def _set_service(self, service):
        # assigns the service attribute, this should be a dict of states
        assert isinstance(service, dict), "service is not a dict()!"
        self.__service = service

    def destroy_previous(self):
        """Destroys the previous state

        This will take from the queue of states and destroy it.  This means
        that the delete_<state> of the previous state will be executed on the
        BIG-IP.

        Returns:
            True - destroy state was deployed
            False - out of states that were deployed
        """
        try:
            state = self.__state_reflection(self.__entered.popleft())
        except IndexError:
            return False
        try:
            p_state = self.__entered.popleft()
            self._append(p_state, self.service[p_state])
        except IndexError:
            self.state = None
        self.__deploy_state(state, keep_state=False)
        return True

    def get_service(self):
        """Returns the service attribute."""
        return self.__service

    def cleanup(self):
        """Based upon the queued states, destroys the setup on the BIG-IP.

        This will execute a thorough cleanup of the agent's setup on the BIG-IP
        using normal operation paradigmes.
        """
        self.__triage_order()
        self.__clear()
        self.icontrol_driver._common_service_handler(self._empty_config)
        self.__entered.clear()
        self.cleanup_queue = list()

    def deploy_next(self):
        """Deploys the next state in the expected_chain """
        self.__deploy_state(self._steps.next())

    def enter_state(self, state_name):
        """Hard-set the BIG-IP to a given state

        This still depends on the object's originally-given service dict.  This
        method will take the given state and assign it to the BIG-IP.

        USE AT YOUR OWN RISK!  If things are out of order, you may get
        unpredictable results, though we are supposed to handle this.
        """
        self.__deploy_state(state_name)

    service = property(get_service, _set_service)


@pytest.fixture
def bigip(request):
    bigip = BigIpClient(pytest.symbols.bigip_floating_ips[0],
                        pytest.symbols.bigip_username,
                        pytest.symbols.bigip_password)

    def fin():
        bigip.delete_folders()
    request.addfinalizer(fin)

    return bigip


@pytest.fixture
def track_bigip_cfg(request):
    request.addfinalizer(BigIpInteraction.check_resulting_cfg)
    BigIpInteraction.backup_bigip_cfg(request.node.name)


def debug_msg(status):
    caller_levels = dict(troubleshoot_cleaner=1, troubleshoot_obj_call=2,
                         troubleshoot_test=3)
    frame = gfi(gof(cf(caller_levels['troubleshoot_test']))[1][0])
    print("{} [filename: {}, line: {}]".format(status, frame.filename,
                                               frame.lineno))


@pytest.fixture
def fake_plugin_rpc(services):

    rpcObj = FakeRPCPlugin(services)

    return rpcObj


@pytest.fixture
def icontrol_driver(icd_config, fake_plugin_rpc):
    class ConfFake(object):
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


@pytest.fixture()
def icd_config():
    relative = get_relative_path()
    basic_agent_config = str("{}/test/functional/config"
                             "/basic_agent_config.json".format(relative))
    oslo_config_filename = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     basic_agent_config)
    )
    OSLO_CONFIGS = json.load(open(oslo_config_filename))

    config = deepcopy(OSLO_CONFIGS)
    config['icontrol_hostname'] = pytest.symbols.bigip_floating_ips[0]
    config['icontrol_username'] = pytest.symbols.bigip_username
    config['icontrol_password'] = pytest.symbols.bigip_password
    try:
        config['f5_vtep_selfip_name'] = pytest.symbols.f5_vtep_selfip_name
    except AttributeError:
        config['f5_vtep_selfip_name'] = "selfip.external"
    return config


def _derive_relative_path_from(expected_relative, current):
    relative_path = list()
    for level in current.split("/"):
        relative_path.append(level)
        if _check_relative_path(expected_relative, relative_path):
            break
    else:
        raise AssertionError(
            "Could not find repo's relative path! Please be "
            "within the repo! (cwd: {})".format(current))
    return tuple(relative_path)


def _check_relative_path(expected_relative, relative_path):
    found = list(relative_path)
    return \
        os.path.isdir("{}/{}".format('/'.join(found), expected_relative))


@pytest.fixture()
def get_relative_path():
    """Discovers the relative path to the start of the repo's path and returns

    This test fixture will find the relative path of the beginning of the repo.
    This path is then returned.  If it is discovered that:
    ./test/functional/neutronless/

    Is not a full path, then it will raise and AssertionError.  If the user
    executes this within a non-existent or partial repo that is fake or
    unexpected, then it is assumed any subsequent test would fail.

    The purpose of this code is to free up some tests from having to be run
    from an explicit point of reference from within the repo's many possible
    paths or tributaries.
    """

    current = os.getcwd()
    expected_relative = 'test/functional/neutronless'
    try:
        relative_path = _derive_relative_path_from(expected_relative, current)
        assert _check_relative_path(expected_relative, relative_path), \
            "The discovered path: {} is not a relative path! (cwd: {})".format(
                relative_path, current)
    except AssertionError as Err:
        # go for the BIG-O >> to see if we can salvage...
        found = False
        for destination in sys.argv[1:]:
            if os.path.isfile(destination) or os.path.isdir(destination):
                try:
                    relative_path = \
                        _derive_relative_path_from(expected_relative,
                                                   destination)
                    if _check_relative_path(expected_relative, relative_path):
                        found = True
                        break
                except AssertionError:
                    continue
        assert found, "Both means failed; args as well as {}".format(Err)
    return '/'.join(relative_path)
