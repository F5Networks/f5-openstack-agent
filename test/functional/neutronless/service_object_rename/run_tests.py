#!/usr/bin/python
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
import json
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--action', metavar="action", default="setup",
        choices=['setup', 'teardown', 'run_test'])
    parser.add_argument(
        '--service-name', metavar="service_name", default="full_service")
    parser.add_argument(
        '--icontrol-hostname', metavar="icontrol_hostname",
        default=os.getenv('icontrol_hostname', "10.1.0.170"))
    parser.add_argument(
        '--member-ip', metavar="member_ip", default=os.getenv('member_ip', "192.168.101.4"))
    parser.add_argument(
        '--bigip-selfip', metavar="bigip_selfip",
        default=os.getenv('bigip_selfip', "192.168.101.5"))
    parser.add_argument(
        '--vni', metavar="vxlan_vni", default=os.getenv('vxlan_vni', "94"))
    parser.add_argument(
        '--test-case', metavar="test_case", default="test_rename_service_objects")
    return parser.parse_args()


def setup_symbols(symbols_file, args):
    with open(symbols_file, "r") as f:
        symbols = json.load(f)
        f.close()

    symbols['bigip_ip'] = args.icontrol_hostname
    symbols['bigip_selfip'] = args.bigip_selfip
    symbols['server_ip'] = args.member_ip
    symbols['server_vxlan'] = args.vni
    symbols['vip_vxlan_segid'] = args.vni

    with open(symbols_file, "w") as f:
        json.dump(symbols, f)
        f.close()


def main(args):
    test_root = "test/functional/neutronless/service_object_rename"
    test_name = "test_service_object_rename.py"
    symbols_file = "%s/conf_symbols.json" % test_root

    # Initialize symbols file
    setup_symbols(symbols_file, args)

    # Build the command to run.
    cmd = "py.test -sv --symbols=%s --service-name=%s %s/%s" % (
        symbols_file,
        args.service_name,
        test_root,
        test_name)

    # Get the test to run.
    if args.action == 'setup':
        print("Setting up service rename tests...")
        test = "test_create_config"
    elif args.action == 'teardown':
        print("Teardown service rename tests...")
        test = "test_cleanup_config"
    elif args.action == 'run_test':
        print("Teardown service rename tests...")
        test = args.test_case
    else:
        print("invalid option")
        sys.exit(1)

    # Build the test case into the command
    cmd = "%s::%s" % (cmd, test)
    try:
        returncode = subprocess.call(cmd.split())
    except subprocess.CalledProcessError as e:
        returncode = e.returncode

    sys.exit(returncode)

if __name__ == '__main__':

    main(parse_args())
