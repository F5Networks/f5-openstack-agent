from oslo_config import cfg
from oslo_utils import importutils
from oslo_log import log as logging
import socket
import collections
import sys

import errno
import inspect
import sys

import f5_openstack_agent.lbaasv2.drivers.bigip.exceptions as exceptions

from oslo_config import cfg
from oslo_log import log as oslo_logging
from oslo_service import service

from neutron.agent.linux import interface
from neutron.agent.common import config
from neutron.common import config as common_config
from neutron.common import rpc as n_rpc

import f5_openstack_agent.lbaasv2.drivers.bigip.icontrol_driver as driver
import f5_openstack_agent.lbaasv2.drivers.bigip.agent_manager as manager
import f5_openstack_agent.lbaasv2.drivers.bigip.agent as agent
import f5_openstack_agent.lbaasv2.drivers.bigip.constants_v2 as f5constants




LOG = logging.getLogger(__name__)


class BaseAction(object):


    def __init__(self,namespace):
        # append appends config paths to defaults... not what we intend
        if len(namespace.config) > 2:
            self.config_files = namespace.config[2:]
        else:
            self.config_files = namespace.config

        self.conf = cfg.CONF

        config_files = []

        for s in self.config_files:
            config_files.append("--config-file")
            config_files.append(s)

        common_config.init(config_files)

        cfg.CONF.register_opts(manager.OPTS)
        cfg.CONF.register_opts(interface.OPTS)
        cfg.CONF.register_opts(agent.OPTS)
        cfg.CONF.register_opts(driver.OPTS)
        config.register_agent_state_opts_helper(cfg.CONF)
        config.register_root_helper(cfg.CONF)

        self.host = socket.gethostname()

        if namespace.log:
            common_config.setup_logging()


        self.manager = manager.LbaasAgentManager(cfg.CONF)
        self.manager.lbdriver.make_bigips_operational()
        self.driver = self.manager.lbdriver


    def replace_dict_value(self,obj,key,new_value):
        if isinstance(obj,dict):
            for k, v in obj.iteritems():
                if k == key or isinstance(v,dict) or isinstance(v,list):
                    obj[k] = self.replace_dict_value(v,key,new_value)
            result = obj
        elif isinstance(obj,list):
            result  = []
            for v in obj:
               result.append(self.replace_dict_value(v, key, new_value))

        else:
            result= new_value

        return result



