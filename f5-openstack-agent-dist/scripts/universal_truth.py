#!/usr/bin/env python
# Copyright (c) 2017,2018, F5 Networks, Inc.
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
import traceback

import configure
import construct_setups

"""{}:

A simple script that will configure the stdeb.cfg and the setup.cfg to
appropriate dependencies from the setup_requirements.txt.

Requirements:
    - Be within the f5-openstack-agent repo
"""


def get_relative_dir():
    cwd = os.getcwd()
    path = cwd.split('/')
    relative = ''
    for item in path:
        relative += '/' + item
        if item == 'f5-openstack-agent':
            break
    return cwd, relative


def config():
    cfg = configure.get_env()
    return cfg


def edit_setups(cfg):
    construct_setups._construct_cfgs_from_json(cfg)


def main():
    current, relative = get_relative_dir()
    os.chdir(relative)
    cfg = config()
    edit_setups(cfg)
    os.chdir(current)


if __name__ == '__main__':
    try:
        main()
    except Exception as Error:
        # SystemExit's will be ignored
        traceback.print_exc()
        print("An error occurred: {}".format(Error))
