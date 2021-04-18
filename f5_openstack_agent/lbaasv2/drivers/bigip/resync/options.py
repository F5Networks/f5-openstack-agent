# -*- coding: utf-8 -*-

from oslo_config import cfg
import sys

import f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager as manager
from f5_openstack_agent.lbaasv2.drivers.bigip import icontrol_driver
from oslo_db import options

tool_opts = [
    cfg.StrOpt("f5-agent",
               short="ag",
               default=None,
               help=("Provide an ID of an agent"))
]

cfg.CONF.register_cli_opts(tool_opts)


def load_options(conf=cfg.CONF):
    conf.register_opts(manager.OPTS)
    conf.register_opts(icontrol_driver.OPTS)


def load_db_options(conf=cfg.CONF):
    options.set_defaults(conf)


def parse_options(args=sys.argv[1:],
                  conf=cfg.CONF,
                  project="f5-check-tool"):
    conf(args, project)
