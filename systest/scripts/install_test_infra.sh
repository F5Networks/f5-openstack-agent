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
sudo -E pip install --upgrade pip &&
sudo -E pip install tox &&
sudo -E pip install git+ssh://git@gitlab.pdbld.f5net.com/bdo/testenv-all.git &&
sudo -E pip install git+ssh://git@gitlab.pdbld.f5net.com/tools/pytest-meta.git &&
sudo -E pip install git+ssh://git@gitlab.pdbld.f5net.com/tools/pytest-autolog.git &&
sudo -E pip install git+ssh://git@gitlab.pdbld.f5net.com/tools/pytest-symbols.git
