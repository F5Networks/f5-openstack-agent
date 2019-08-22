# -*- coding: utf-8 -*-

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

from oslo_service import service
from oslo_service import systemd


class F5ServiceLauncher(service.ServiceLauncher):

    def __init__(self, conf):
        super(F5ServiceLauncher, self).__init__(conf)

    def handle_signal(self):
        self.signal_handler.add_handler('SIGTERM', self._graceful_shutdown)
        self.signal_handler.add_handler('SIGINT', self._fast_exit)
        self.signal_handler.add_handler('SIGHUP', self._reload_service)
        self.signal_handler.add_handler('SIGALRM', self._on_timeout_exit)

    def wait(self):
        systemd.notify_once()
        while True:
            self.handle_signal()
            status, signo = self._wait_for_exit_or_signal()
            if not service._is_sighup_and_daemon(signo):
                break
            self.restart()

        self.services.wait()
        return status
