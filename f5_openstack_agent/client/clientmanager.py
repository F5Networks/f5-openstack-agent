import os
import logging as std_logging

from oslo_log import log as logging
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2 as f5const
from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager import ClusterManager
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import SystemHelper

std_logging.getLogger("requests.packages.urllib3").setLevel(std_logging.ERROR)
LOG = logging.getLogger(__name__)


def build_session():
    auth_url = os.environ['OS_AUTH_URL']
    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    project_name = os.environ['OS_PROJECT_NAME']
    user_domain_name = os.environ.get('OS_USER_DOMAIN_NAME', None)
    project_domain_name = os.environ.get('OS_PROJECT_DOMAIN_NAME', None)
    LOG.debug("f5agent session,auth_url: %s, username: %s, password: %s, project_name: %s, user_domain_name: %s, "
              "project_domain_name: %s" % (auth_url, username, password, project_name, user_domain_name,
                                           project_domain_name))
    auth = v3.Password(auth_url=auth_url, username=username, password=password, project_name=project_name,
                       user_domain_name=user_domain_name, project_domain_name=project_domain_name)

    sess = session.Session(auth=auth)
    return sess


def make_client():
    return client.Client(session=build_session())


class IControlClient:
    def __init__(self, icontrol_hostname, icontrol_username, icontrol_password, icontrol_port):
        self.icontrol_hostname = icontrol_hostname
        self.icontrol_username = icontrol_username
        self.icontrol_password = icontrol_password
        self.icontrol_port = icontrol_port
        self.bigip = self._open_bigip()
        self.cluster_manager = ClusterManager()
        self.system_helper = SystemHelper()

    def _open_bigip(self):
        try:
            bigip = ManagementRoot(self.icontrol_hostname,
                                   self.icontrol_username,
                                   self.icontrol_password,
                                   port=self.icontrol_port,
                                   timeout=f5const.DEVICE_CONNECTION_TIMEOUT)
            return bigip
        except Exception as exc:
            LOG.error('could not communicate with ' + 'iControl device: %s, error: %s' %
                      (self.icontrol_hostname, str(exc)))
            return None

    def get_bigip_info(self):
        info = {
            "username": self.icontrol_username,
            "password": self.icontrol_password,
            "port": self.icontrol_port,
        }
        return info

    def get_refresh_info(self):
        info = self.get_bigip_info()
        info.update(self._get_dynamic_info())
        return info

    def _get_dynamic_info(self):
        device_info = {
            "version": self.system_helper.get_version(self.bigip) if self.bigip else "",
            "device_name": self.cluster_manager.get_device_name(self.bigip) if self.bigip else "",
            "platform": self.system_helper.get_platform(self.bigip) if self.bigip else "",
            "serial_number": self.system_helper.get_serial_number(self.bigip) if self.bigip else "",
            "license": self._get_bigip_license() if self.bigip else "",
            "status": "active" if self.bigip else "error",
            "status_message": "BIG-IP ready for provisioning" if self.bigip else "Fail to connect to BIG-IP",
            "failover_state": self._get_failover_state() if self.bigip else "",
        }
        return device_info

    def _get_bigip_license(self):
        license = {}
        modules = self.system_helper.get_active_modules(self.bigip)
        for module in modules:
            a = module.find(",")
            b = module.find("|")
            if a > 0 and a + 2 < b:
                license[module[0:a]] = module[a + 2:b]
        return license

    def _get_failover_state(self):
        try:
            fs = self.bigip.tm.sys.dbs.db.load(name='failover.state')
            return fs.value
        except Exception as exc:
            LOG.exception('Error getting %s failover state, error: %s' % (self.bigip.hostname, str(exc)))
            return ""
