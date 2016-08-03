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

import argparse
import fnmatch
import os
import pip
import tarfile


class TarAdditionNonExtant(Exception):
    pass


class DebugBundle(object):

    def __init__(self, command_args):
        self.config_dir = command_args.config_dir
        self.log_dir = command_args.log_dir
        self.tar_dest = command_args.tar_dest
        self.no_config_files = command_args.no_config_files
        self.no_log_files = command_args.no_log_files

    def _save_pip_list(self, tar):
        '''Dump a pip list, containing packages and versions.

        :param dest: unicode -- directory of dumped pip list
        :param tar: tarfile object -- tar where pip list dump will be added
        '''

        pkgs = pip.get_installed_distributions()
        sorted_pkgs = sorted(pkgs, key=lambda pkg: pkg._key)
        sorted_pkg_names = [str(pkg) for pkg in sorted_pkgs]
        pip_list_file = os.path.join(self.tar_dest, 'pip_list.txt')
        with open(pip_list_file, 'w') as pip_file:
            pip_file.write('\n'.join(sorted_pkg_names))
        self._add_file_to_tar(self.tar_dest, 'pip_list.txt', tar)
        os.remove(pip_list_file)
        return sorted_pkgs

    def _tar_config_files(self, tar):
        '''Add config files specified to tarfile

        :param tar: tarfile object -- tar where config files will be added
        '''

        lbaas_config_dir = os.path.join(self.config_dir, 'services', 'f5')
        config_files = [
            (self.config_dir, 'neutron.conf'),
            (self.config_dir, 'neutron_lbaas.conf'),
            (lbaas_config_dir, 'f5-openstack-agent.ini')
        ]
        for cfg_dir, cfg_file in config_files:
            self._add_file_to_tar(cfg_dir, cfg_file, tar)

    def _tar_log_files(self, tar):
        '''Add log files specified to tarfile

        :param tar: tarfile object -- tar where log files will be added
        '''

        log_files = [
            (self.log_dir, 'server.log'),
            (self.log_dir, 'f5-openstack-agent.log')
        ]
        for log_dir, log_file in log_files:
            self._add_file_to_tar(log_dir, log_file, tar)
            self._tar_archived_log_files(log_dir, log_file, tar)

    def _tar_archived_log_files(self, log_dir, log_file, tar):
        '''Add archived log files to tarfile

        :param log_dir: unicode -- directory where log resides
        :param log_file: unicode -- filename of log
        :param tar: tarfile object -- tar where log files will be added
        '''

        for log in os.listdir(log_dir):
            if fnmatch.fnmatch(log, log_file + '.[0-9].gz'):
                self._add_file_to_tar(log_dir, log, tar)

    def _add_file_to_tar(self, log_dir, log_file, tar):
        '''Add a specific file to the tarfile

        :param file_dir: unicode -- directory where file resides
        :param file_name: unicode -- name of file to add to tarfile
        :param tar: tarfile object -- tar where a specific file will be added
        :raises: TarAdditionNonExtant
        '''

        log_path = os.path.join(log_dir, log_file)
        if os.path.exists(log_path):
            tar.add(log_path, arcname=log_file)
        else:
            msg = 'File to add to tarfile does not exist: {}'.format(log_path)
            raise TarAdditionNonExtant(msg)

    def produce_bundle(self):
        '''Create a tarred, gzipped bundle of files useful for debugging

        :param args: argparse args -- argument given by user
        '''

        bundle = os.path.join(self.tar_dest, 'debug_bundle.tar.gz')
        with tarfile.open(bundle, 'w:gz') as tar:
            if not self.no_config_files:
                self._tar_config_files(tar)
            if not self.no_log_files:
                self._tar_log_files(tar)
            self._save_pip_list(tar)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Bundle important info for troubleshooting purposes.'
    )
    parser.add_argument(
        '--no-config-files',
        action='store_true',
        help='Include this option if you would not like configuration '
        'files included in your bundle (they will by default).'
    )
    parser.add_argument(
        '--no-log-files',
        action='store_true',
        help='Include this option if you would not like log files included '
        'in your bundle (they will by default).'
    )
    parser.add_argument(
        'tar_dest', help='Directory of bundle produced by this script.'
    )
    parser.add_argument(
        '--log-dir',
        default='/var/log/neutron/',
        help='Override default log directory location.'
    )
    parser.add_argument(
        '--config-dir',
        default='/etc/neutron/',
        help='Override default config directory location.'
    )
    args = parser.parse_args()
    bundle = DebugBundle(args)
    bundle.produce_bundle(args)
