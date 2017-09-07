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


#### These commands are invoked by the CI worker during automated tests.
#    The invocation at the time of this writing is in the "functest" rule
#    in ../Makefile
apt-get update
apt-get install -y libssl-dev
apt-get install -y libffi-dev
pip install --upgrade pip
# - install testenv-all first because it has a bunch of pinned dependencies
pip install git+ssh://git@gitlab.pdbld.f5net.com/bdo/testenv-all.git
pip install git+ssh://git@gitlab.pdbld.f5net.com/tools/pytest-meta.git
pip install git+ssh://git@gitlab.pdbld.f5net.com/tools/pytest-autolog.git
pip install git+ssh://git@gitlab.pdbld.f5net.com/tools/pytest-symbols.git
pip install tox virtualenv virtualenvwrapper

# - list installed python packages
pip freeze | tee python-pkgs.txt
