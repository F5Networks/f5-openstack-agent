# coding=utf-8
import json
import logging as std_logging

from f5.bigip import ManagementRoot
from oslo_log import log as logging
import requests
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from f5_openstack_agent.lbaasv2.drivers.bigip.cluster_manager \
    import ClusterManager
from f5_openstack_agent.lbaasv2.drivers.bigip \
    import constants_v2 as f5const
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper \
    import SystemHelper

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
std_logging.getLogger("requests.packages.urllib3").setLevel(std_logging.ERROR)
LOG = logging.getLogger(__name__)


class IControlClient(object):
    def __init__(self, icontrol_hostname, icontrol_username,
                 icontrol_password, icontrol_port):
        self.icontrol_hostname = icontrol_hostname
        self.icontrol_username = icontrol_username
        self.icontrol_password = icontrol_password
        self.icontrol_port = icontrol_port
        self.bigip = self._open_bigip()
        self.cluster_manager = ClusterManager()
        self.system_helper = SystemHelper()

    def _open_bigip(self):
        bigip = ManagementRoot(self.icontrol_hostname,
                               self.icontrol_username,
                               self.icontrol_password,
                               port=self.icontrol_port,
                               timeout=f5const.DEVICE_CONNECTION_TIMEOUT)
        return bigip

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
        dynamic_info = {
            "version": self.system_helper.get_version(self.bigip)
            if self.bigip else "",
            "device_name": self.cluster_manager.get_device_name(self.bigip)
            if self.bigip else "",
            "platform": self.system_helper.get_platform(self.bigip)
            if self.bigip else "",
            "serial_number": self.system_helper.get_serial_number(self.bigip)
            if self.bigip else "",
            "license": self._get_bigip_license() if self.bigip else "",
            "status": "active" if self.bigip else "error",
            "status_message": "BIG-IP ready for provisioning"
            if self.bigip else "Fail to connect to BIG-IP",
            "failover_state": self.get_failover_state() if self.bigip else "",
        }
        return dynamic_info

    def _get_bigip_license(self):
        license = {}
        modules = self.system_helper.get_active_modules(self.bigip)
        for module in modules:
            a = module.find(",")
            b = module.find("|")
            if a > 0 and a + 2 < b:
                license[module[0:a]] = module[a + 2:b]
        return license

    def get_failover_state(self):
        try:
            fs = self.bigip.tm.sys.dbs.db.load(name='failover.state')
            return fs.value
        except Exception as exc:
            LOG.exception('Error getting %s failover state, error: %s'
                          % (self.bigip.hostname, str(exc)))
            return ""

    def _get_base_mac(self):
        url = "https://" + self.icontrol_hostname + "/mgmt/tm/util/bash"
        payload = {
            "command": "run",
            "utilCmdArgs": "-c \"tmsh show sys hardware" +
                           " field-fmt | grep base-mac\""
        }
        auth = HTTPBasicAuth(self.icontrol_username, self.icontrol_password)
        verify = False
        resp = requests.post(url, json=payload, verify=verify, auth=auth)
        data = json.loads(resp.content)
        base_mac = data['commandResult'].split()[1]
        LOG.debug('base mac is %s' % base_mac)
        return base_mac

    def _hex_binary(self, value):
        int_value = int(value, base=16)
        bin_value = bin(int_value)[2:].zfill(8)
        return bin_value

    def _binary_hex(self, value):
        int_value = int(value, base=2)
        hex_value = hex(int_value)[2:].zfill(2)
        return hex_value

    def _gen_masquerade_mac(self):
        mac = self._get_base_mac()
        temp_mac = mac.split(":")

        first_byte = temp_mac[0]
        binary = self._hex_binary(first_byte)
        binary = binary[:6] + "1" + binary[-1]
        hexa = self._binary_hex(binary)

        temp_mac = [hexa] + temp_mac[1:]
        masquerade_mac = ":".join(temp_mac)
        return masquerade_mac

    def get_traffic_group_1(self):
        traffic_groups = self.bigip.tm.cm.traffic_groups.get_collection()
        for group in traffic_groups:
            if group.name == 'traffic-group-1':
                return group

    def update_traffic_group1_mac(self, masquerade_mac=None):
        if not masquerade_mac:
            masquerade_mac = self._gen_masquerade_mac()
        traffic_group_1 = self.get_traffic_group_1()
        LOG.debug('traffic-group-1 original mac is %s' % traffic_group_1.mac)
        traffic_group_1.modify(mac=masquerade_mac)
        LOG.debug('traffic-group-1 masquerade mac is %s' % masquerade_mac)
        return masquerade_mac
