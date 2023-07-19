# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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

from f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager_lite \
    import LbaasAgentManager
from f5_openstack_agent.lbaasv2.drivers.bigip \
    import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip import opts
from neutron.common import rpc

LOG = oslo_logging.getLogger(__name__)


def register_opts():
    opts.register_f5_opts()


def main():
    """F5 LBaaS agent for OpenStack."""

    register_opts()

    mgr = LbaasAgentManager(cfg.CONF)

    if cfg.CONF.connection_rate_limit_ratio and \
            cfg.CONF.connection_rate_limit_ratio <= 0:
        LOG.info('seems wrong, set connection_rate_limit_ratio to 1.')
        cfg.CONF.connection_rate_limit_ratio = 1

    if cfg.CONF.f5_bandwidth_default < 0:
        LOG.info("set default bandwidth from %d to 200MB",
                 cfg.CONF.f5_bandwidth_default)
        cfg.CONF.f5_bandwidth_default = 200

    if cfg.CONF.f5_bandwidth_max < 0:
        LOG.info("set max bandwidth from %d to 120000MB",
                 cfg.CONF.f5_bandwidth_max)
        cfg.CONF.f5_bandwidth_max = 120000

    if cfg.CONF.f5_bandwidth_default > cfg.CONF.f5_bandwidth_max:
        LOG.info("set default bandwidth %dMB to max bandwidth %dMB",
                 cfg.CONF.f5_bandwidth_default, cfg.CONF.f5_bandwidth_max)
        cfg.CONF.f5_bandwidth_default = cfg.CONF.f5_bandwidth_max

    svc = rpc.Service(
        host=mgr.agent_host,
        topic=constants_v2.TOPIC_LOADBALANCER_AGENT_V2,
        manager=mgr
    )

    service_launch = service_launcher.F5ServiceLauncher(cfg.CONF)
    service_launch.launch_service(svc)
    service_launch.wait()


if __name__ == '__main__':
    main()
