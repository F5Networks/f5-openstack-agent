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
BUNDLE_SCRIPT_PATH = '/usr/bin/f5/debug_bundler.py'


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
    tar_dest = os.path.join(SCRIPT_PATH, 'output')
    os.makedirs(tar_dest)

    def teardown():
        shutil.rmtree(tar_dest)

    request.addfinalizer(teardown)
    margs_dict = {
        'tar_dest': tar_dest,
        'log_dir': setup_bundle_logfiles,
        'config_dir': setup_bundle_cfgfiles
    }
    return margs_dict


def test_produce_bundle(setup_bundle_test):
    margs = setup_bundle_test
    subprocess.call(
        [
            'python',
            BUNDLE_SCRIPT_PATH,
            '--log-dir', margs['log_dir'],
            '--config-dir', margs['config_dir'],
            margs['tar_dest']
        ]
    )
    tar_file = os.path.join(margs['tar_dest'], 'debug_bundle.tar.gz')
    assert os.path.exists(tar_file) is True
    assert tarfile.is_tarfile(tar_file) is True
    with tarfile.open(tar_file, 'r:gz') as tar:
        assert sorted(tar.getnames()) == sorted(TAR_FILE_LIST)


def test_produce_bundle_no_cfgs(setup_bundle_test):
    margs = setup_bundle_test
    subprocess.call(
        [
            'python',
            BUNDLE_SCRIPT_PATH,
            '--log-dir', margs['log_dir'],
            '--config-dir', margs['config_dir'],
            '--no-config-files',
            margs['tar_dest']
        ]
    )

    tar_file = os.path.join(margs['tar_dest'], 'debug_bundle.tar.gz')
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
    margs = setup_bundle_test
    subprocess.call(
        [
            'python',
            BUNDLE_SCRIPT_PATH,
            '--log-dir', margs['log_dir'],
            '--config-dir', margs['config_dir'],
            '--no-log-files',
            margs['tar_dest']
        ]
    )
    tar_file = os.path.join(margs['tar_dest'], 'debug_bundle.tar.gz')
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


def test_produce_bundle_file_not_found(setup_bundle_test):
    margs = setup_bundle_test
    os.remove(os.path.join(margs['log_dir'], 'server.log'))
    output = subprocess.check_output(
        [
            'python',
            BUNDLE_SCRIPT_PATH,
            '--log-dir', margs['log_dir'],
            '--config-dir', margs['config_dir'],
            margs['tar_dest']
        ]
    )
    print(output)
    assert 'File to add to tarfile does not exist:' in output
    assert 'server.log' in output


def test_produce_bundle_subprocess(setup_bundle_test):
    margs = setup_bundle_test
    subprocess.call(
        [
            'python',
            BUNDLE_SCRIPT_PATH,
            '--log-dir', margs['log_dir'],
            '--config-dir', margs['config_dir'],
            margs['tar_dest']
        ]
    )
    tar_file = os.path.join(margs['tar_dest'], 'debug_bundle.tar.gz')
    assert os.path.exists(margs['tar_dest']) is True
    with tarfile.open(tar_file, 'r:gz') as tar:
        assert sorted(tar.getnames()) == sorted(TAR_FILE_LIST)
        tar.extract('pip_list.txt', margs['tar_dest'])
        with open(
                os.path.join(margs['tar_dest'], 'pip_list.txt'), 'r'
        ) as pip_file:
            assert os.stat(
                os.path.join(margs['tar_dest'], 'pip_list.txt')
            ).st_size > 0
            # One more check for good measure
            assert len(pip_file.read()) > 0
