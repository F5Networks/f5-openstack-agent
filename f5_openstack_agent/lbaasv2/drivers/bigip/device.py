# -*- coding: utf-8 -*-

class BigipDevice(object):

    def __init__(device):
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
                timeout=f5const.DEVICE_CONNECTION_TIMEOUT,
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
            # if error happens, agent cant start up ?
            # signal.alarm(0)

    def get_all_bigips(self, **kwargs):
        # replace
        # get_bigip()
        return_bigips = self._bigips.values()

        if len(return_bigips) == 0 and \
           kwargs.get('no_bigip_exception') is True:
            raise Exception("No active bigips!")

        return return_bigips

    # member update related
    def get_active_bigip(self):
        return self._bigips[0]

    # these are the refactored methods
    def get_active_bigips(self):
        return self.get_all_bigips()

    def get_host_bigip(self, host):
        return self._bigips.get(host)
