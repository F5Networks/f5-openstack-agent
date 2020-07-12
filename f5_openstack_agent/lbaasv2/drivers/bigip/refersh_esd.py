#!/usr/bin/python

# Copyright (c) 2014-2018, F5 Networks, Inc.
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
import signal
import subprocess


def refresh_esd():

    cmd = ['pgrep', '-f', 'f5-oslbaasv2-ag']
    child_process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    resp = child_process.communicate()[0].split()

    for pid in resp:
        os.kill(int(pid), signal.SIGUSR1)
        print(("Refreshed ESD for f5-oslbaasv2-agent (PID): %s." % pid))
