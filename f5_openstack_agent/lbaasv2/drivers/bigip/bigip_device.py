# -*- coding: utf-8 -*-

import functools

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from oslo_log import log

LOG = log.getLogger(__name__)


def set_bigips(method):

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        service = kwargs['service']
        bigip_dev = BigipDevice(service['device'])
        service['bigips'] = bigip_dev.get_all_bigips()
        method(*args, **kwargs)
    return wrapper


class BigipDevice(object):

    def __init__(self, device):
        self.device = device
        self.set_all_bigips()

    def set_all_bigips(self):
        self._bigips = dict()

        device_items = self.device['bigip'].items()
        for host, info in device_items:
            self.connect(host, info)

    def connect(self, host, info):
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

            self._bigips[host] = bigip

        except Exception as exc:
            LOG.error(
                "Could not establish connection with device %s,"
                " the device info is %s."
                % (host, info)
            )
            raise exc

            # if error happens, agent cant start up ?
            # signal.alarm(0)

    # only for bigip service configuration
    def get_all_bigips(self, **kwargs):
        return_bigips = self._bigips.values()

        if len(return_bigips) == 0 and \
           kwargs.get('no_bigip_exception') is True:
            raise Exception("No active bigips!")

        return return_bigips
