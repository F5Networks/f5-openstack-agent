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

This directory contains the configuration and code necessary to interface with
the inhouse f5 Boulder buildbot automated test infrastructure.   If data is
contained inside this directory it is for internal use.  Items which are
relevant outside the f5 Boulder buildbot system MUST NOT be placed in this
directory (or its subdirectories).

List of Contents:
  * README.txt -- this file
  * Makefile -- this file provides an interface that buildbot uses. Buildbot always invokes "functest".  This list of rules is:
    $(DEPLOYS)
    functest
    run_{over,under}cloud_tests
    singlebigip
    setup_singlebigip_tests
    run_singlebigip_tests
    cleanup_singlebigip
    run_disconnected_service_tests
    clean

  See comment lines in the Makefile for specifics of each rule.

  * device_version_maps.sh -- this file maps the major device numbers to a
    specific release for a device e.g. 12_1_1 --> bigip-osready-12.1.1.2.0.204

  * scripts/ -- this directory contains core logic for RULEs in the Makefile,
    where possible use the Makefile to set variables, and scripts/RULE.sh to
    specify RULE behavior

  * scripts/install_test_infra.sh -- setup the buildbot workder to have
    necessary packages before Make operations
