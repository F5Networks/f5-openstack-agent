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

import sys

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import service

from neutron.agent.common import config
from neutron.agent.linux import interface
from neutron.common import config as common_config
from neutron.common import rpc as n_rpc

import f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager as manager
import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 as f5constants

LOG = logging.getLogger(__name__)

OPTS = [
    cfg.IntOpt(
        'periodic_interval',
        default=10,
        help='Seconds between periodic task runs'
    )
]


class F5AgentService(n_rpc.Service):
    """F5 Agent service class."""

    def start(self):
        """Start the F5 agent service."""
        self.tg.add_timer(
            cfg.CONF.periodic_interval,
            self.manager.run_periodic_tasks,
            None,
            None
        )   # Hmmm....  "tg"?
        super(F5AgentService, self).start()


def main():
    """F5 LBaaS agent for OpenStack."""
    cfg.CONF.register_opts(OPTS)
    cfg.CONF.register_opts(manager.OPTS)
    cfg.CONF.register_opts(interface.OPTS)

    config.register_agent_state_opts_helper(cfg.CONF)
    config.register_root_helper(cfg.CONF)

    common_config.init(sys.argv[1:])
    # alias for common_config.setup_logging()...
    config.setup_logging()

    mgr = manager.LbaasAgentManager(cfg.CONF)

    svc = F5AgentService(
        host=mgr.agent_host,
        topic=f5constants.TOPIC_LOADBALANCER_AGENT_V2,
        manager=mgr
    )
    service.launch(cfg.CONF, svc).wait()

if __name__ == '__main__':
    main()
