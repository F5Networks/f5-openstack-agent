# -*- coding: utf-8 -*-

from f5.bigip import ManagementRoot
from f5_openstack_agent.client.encrypt import decrypt_data
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from oslo_log import log

LOG = log.getLogger(__name__)


def set_bigips(service, conf):
    LOG.info(
        "Builde connection of device %s" %
        service['device']
    )
    bigip_dev = BigipDevice(service['device'])
    service['bigips'] = bigip_dev.get_all_bigips()


def build_connection(host, info):
    LOG.info("Build connection for %s: %s" % (host, info))
    try:
        bigip = ManagementRoot(
            host,
            decrypt_data(info['serial_number'], info['username']),
            decrypt_data(info['serial_number'], info['password']),
            port=info['port'],
            timeout=constants_v2.DEVICE_CONNECTION_TIMEOUT,
            token=True,
            debug=True
        )
        bigip.device_name = info["device_name"]

        # fake info for old functions, they will be cleaned
        # with functions
        bigip.mac_addresses = None
        bigip.device_interfaces = dict()
        bigip.status = 'connected'
        bigip.assured_networks = {}
        bigip.assured_tenant_snat_subnets = {}
        bigip.assured_gateway_subnets = []
    except Exception as exc:
        LOG.error(
            "Could not establish connection with device %s,"
            " the device info is %s."
            % (host, info)
        )
        raise exc

    return bigip


class BigipDevice(object):

    cache_pool = dict()

    def __init__(self, device, conf=None):
        self.device = device
        self.conf = conf
        if self.conf:
            self.device['use_mgmt_ipv6'] = self.conf.use_mgmt_ipv6
        else:
            self.device['use_mgmt_ipv6'] = False
        self.set_all_bigips()

    def set_all_bigips(self):
        self._bigips = dict()

        self.device['bigip'] = {}
        device_members = self.device['device_info']['members']
        for member in device_members:
            if self.device['use_mgmt_ipv6'] and member['mgmt_ipv6']:
                host = member['mgmt_ipv6']
            else:
                host = member['mgmt_ipv4'] or member['mgmt_ipv6']
            # Workaround sdk ipv6 issue
            if ":" in host and not host.startswith("["):
                host = "[" + host + "]"
            self.device['bigip'][host] = member
            self.connect(host, member['device_info'])

    def connect(self, host, info):
        LOG.info(
            "Build connection of device %s for resource config" %
            host
        )
        bigip = build_connection(host, info)
        self._bigips[host] = bigip

        LOG.info("Add and refresh host %s in cache." % host)
        BigipDevice.cache_pool[host] = info

    # only for bigip service configuration
    def get_all_bigips(self, **kwargs):
        return_bigips = self._bigips.values()

        if len(return_bigips) == 0 and \
           kwargs.get('no_bigip_exception') is True:
            raise Exception("No active bigips!")

        return return_bigips
