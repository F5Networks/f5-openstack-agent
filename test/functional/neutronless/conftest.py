# coding=utf-8
# Copyright 2016-2017 F5 Networks Inc.
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

import json
import os
import pytest
import re
import traceback
import sys

from inspect import currentframe as cf
from inspect import getframeinfo as gfi
from inspect import getouterframes as gof
from collections import deque
from collections import namedtuple
from copy import deepcopy

from .testlib.bigip_client import BigIpClient
from .testlib.fake_rpc import FakeRPCPlugin
from f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver import \
    iControlDriver

DEBUG = True  # sys.flags.debug


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

    bigip = BigIpClient(pytest.symbols.bigip_mgmt_ip_public,
                        pytest.symbols.bigip_username,
                        pytest.symbols.bigip_password)

    def fin():
        bigip.delete_folders()
    request.addfinalizer(fin)

    return bigip


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
    config['icontrol_hostname'] = pytest.symbols.bigip_mgmt_ip_public
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
