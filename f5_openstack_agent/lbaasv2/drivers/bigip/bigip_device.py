# -*- coding: utf-8 -*-

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from oslo_log import log

LOG = log.getLogger(__name__)


def set_bigips(service):
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
            info['username'],
            info['password'],
            port=info['port'],
            timeout=constants_v2.DEVICE_CONNECTION_TIMEOUT,
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

    def __init__(self, device):
        self.device = device
        self.set_all_bigips()

    def set_all_bigips(self):
        self._bigips = dict()

        device_items = self.device['bigip'].items()
        for host, info in device_items:
            self.connect(host, info)

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
