#! /bin/bash

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


#### These commands are invoked by the buildbot worker during automated tests.
#    The invocation at the time of this writing is in the "functest" rule
#    in ../Makefile
sudo -E apt-get update &&
sudo -E apt-get install -y libssl-dev &&
sudo -E apt-get install -y libffi-dev &&
sudo -E -H pip install --upgrade pip &&
sudo -E -H pip install tox &&
sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/testenv.git &&
sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/velcro/systest-common.git &&
sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-meta.git &&
sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-autolog.git &&
sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-symbols.git
