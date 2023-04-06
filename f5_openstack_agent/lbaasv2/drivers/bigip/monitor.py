# coding=utf-8
# Copyright (c) 2016-2023, F5 Networks, Inc.
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

import service_launcher

from oslo_config import cfg
from oslo_log import log as oslo_logging

from f5_openstack_agent.lbaasv2.drivers.bigip \
    import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip.monitor_manager \
    import LbaasMonitorManager
from f5_openstack_agent.lbaasv2.drivers.bigip import opts
from neutron.common import rpc

LOG = oslo_logging.getLogger(__name__)


def register_opts():
    opts.register_f5_opts()


def main():
    """LBaaS monitor for OpenStack."""

    register_opts()

    mgr = LbaasMonitorManager(cfg.CONF)

    if cfg.CONF.member_update_interval == 0:
        LOG.info("set member update interval to 60s",
                 cfg.CONF.member_update_interval)
        cfg.CONF.member_update_interval = 60

    if cfg.CONF.member_update_agent_number <= 0:
        LOG.info("set member update agent number %d to 1",
                 cfg.CONF.member_update_agent_number)
        cfg.CONF.member_update_agent_number = 1

    if cfg.CONF.member_update_agent_order >= \
            cfg.CONF.member_update_agent_number:

        LOG.info("set member update agent order %d to %d",
                 cfg.CONF.member_update_agent_order,
                 cfg.CONF.member_update_agent_number - 1)

        cfg.CONF.member_update_agent_order = \
            cfg.CONF.member_update_agent_number - 1

    svc = rpc.Service(
        host=mgr.agent_host,
        topic=constants_v2.TOPIC_LOADBALANCER_MONITOR,
        manager=mgr
    )

    service_launch = service_launcher.F5ServiceLauncher(cfg.CONF)
    service_launch.launch_service(svc)
    service_launch.wait()


if __name__ == '__main__':
    main()
