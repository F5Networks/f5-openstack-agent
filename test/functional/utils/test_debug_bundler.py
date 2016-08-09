# coding=utf-8
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

from f5_openstack_agent.utils.debug_bundler import DebugBundle
from f5_openstack_agent.utils.debug_bundler import TarAdditionNonExtant

import os
import pytest
import shutil
import subprocess
import tarfile


SCRIPT_PATH = os.path.dirname(__file__)
TAR_FILE_LIST = [
    'neutron.conf', 'neutron_lbaas.conf', 'f5-openstack-agent.ini',
    'server.log', 'f5-openstack-agent.log', 'pip_list.txt',
    'server.log.1.gz', 'server.log.5.gz', 'f5-openstack-agent.log.1.gz'
]


class MockArgs(object):
    def __init__(self, tar_dest, log_dir, cfg_dir, no_cfg, no_log):
        self.tar_dest = tar_dest
        self.log_dir = log_dir
        self.config_dir = cfg_dir
        self.no_config_files = no_cfg
        self.no_log_files = no_log


def create_empty_file(file_path):
    with open(file_path, 'w'):
        pass


@pytest.fixture
def setup_bundle_logfiles(request):
    log_path = os.path.join(SCRIPT_PATH, 'logs')
    os.makedirs(log_path)
    create_empty_file(os.path.join(log_path, 'server.log'))
    create_empty_file(os.path.join(log_path, 'server.log.1.gz'))
    create_empty_file(os.path.join(log_path, 'server.log.5.gz'))
    create_empty_file(os.path.join(log_path, 'f5-openstack-agent.log'))
    create_empty_file(os.path.join(log_path, 'f5-openstack-agent.log.1.gz'))

    def teardown():
        shutil.rmtree(log_path)

    request.addfinalizer(teardown)
    return log_path


@pytest.fixture
def setup_bundle_cfgfiles(request):
    cfg_path = os.path.join(SCRIPT_PATH, 'cfgs')
    os.makedirs(cfg_path)
    lbaas_cfg = os.path.join(cfg_path, 'services', 'f5')
    os.makedirs(lbaas_cfg)
    create_empty_file(os.path.join(cfg_path, 'neutron.conf'))
    create_empty_file(os.path.join(cfg_path, 'neutron_lbaas.conf'))
    create_empty_file(os.path.join(lbaas_cfg, 'f5-openstack-agent.ini'))

    def teardown():
        shutil.rmtree(cfg_path)

    request.addfinalizer(teardown)
    return cfg_path


@pytest.fixture
def setup_bundle_test(request, setup_bundle_cfgfiles, setup_bundle_logfiles):
    out_path = os.path.join(SCRIPT_PATH, 'output')
    os.makedirs(out_path)

    def teardown():
        shutil.rmtree(out_path)

    request.addfinalizer(teardown)
    margs = MockArgs(
        out_path, setup_bundle_logfiles, setup_bundle_cfgfiles, False, False
    )
    return margs, out_path


def test_produce_bundle(setup_bundle_test):
    margs, out_path = setup_bundle_test
    bundle = DebugBundle(margs)
    bundle.produce_bundle()
    tar_file = os.path.join(out_path, 'debug_bundle.tar.gz')
    assert os.path.exists(tar_file) is True
    assert tarfile.is_tarfile(tar_file) is True
    with tarfile.open(tar_file, 'r:gz') as tar:
        assert sorted(tar.getnames()) == sorted(TAR_FILE_LIST)


def test_produce_bundle_no_cfgs(setup_bundle_test):
    margs, out_path = setup_bundle_test
    margs.no_config_files = True
    bundle = DebugBundle(margs)
    bundle.produce_bundle()
    tar_file = os.path.join(out_path, 'debug_bundle.tar.gz')
    assert os.path.exists(tar_file) is True
    assert tarfile.is_tarfile(tar_file) is True
    with tarfile.open(tar_file, 'r:gz') as tar:
        assert sorted(tar.getnames()) == \
            sorted(
                [
                    'f5-openstack-agent.log', 'f5-openstack-agent.log.1.gz',
                    'pip_list.txt', 'server.log', 'server.log.1.gz',
                    'server.log.5.gz'
                ]
            )


def test_produce_bundle_no_logs(setup_bundle_test):
    margs, out_path = setup_bundle_test
    margs.no_log_files = True
    bundle = DebugBundle(margs)
    bundle.produce_bundle()
    tar_file = os.path.join(out_path, 'debug_bundle.tar.gz')
    assert os.path.exists(tar_file) is True
    assert tarfile.is_tarfile(tar_file) is True
    with tarfile.open(tar_file, 'r:gz') as tar:
        assert sorted(tar.getnames()) == \
            sorted(
                [
                    'f5-openstack-agent.ini', 'pip_list.txt',
                    'neutron.conf', 'neutron_lbaas.conf'
                ]
            )


def test_produce_add_nonextant_file(setup_bundle_test):
    margs, out_path = setup_bundle_test
    os.remove(os.path.join(margs.log_dir, 'server.log'))
    bundle = DebugBundle(margs)
    with pytest.raises(TarAdditionNonExtant) as ex:
        bundle.produce_bundle()
    assert 'File to add to tarfile does not exist:' in ex.value.message
    assert 'server.log' in ex.value.message
