# -*- coding: utf-8 -*-

from f5.bigip import ManagementRoot
from f5_openstack_agent.client.encrypt import decrypt_data
from f5_openstack_agent.lbaasv2.drivers.bigip.confd import F5OSClient
from f5_openstack_agent.lbaasv2.drivers.bigip.confd import LAG
from f5_openstack_agent.lbaasv2.drivers.bigip.confd import Tenant
from f5_openstack_agent.lbaasv2.drivers.bigip import constants_v2
from f5_openstack_agent.lbaasv2.drivers.bigip.resource_helper \
    import retry_icontrol

from oslo_log import log

LOG = log.getLogger(__name__)


def set_bigips(service, conf):
    LOG.info(
        "Builde connection of device %s" %
        service['device']
    )
    bigip_dev = BigipDevice(service['device'], conf)
    service['bigips'] = bigip_dev.get_all_bigips()


@retry_icontrol
def build_connection(host, info, token=False):
    LOG.info("Build connection for %s: %s" % (host, info))
    try:
        bigip = ManagementRoot(
            host,
            decrypt_data(info['serial_number'], info['username']),
            decrypt_data(info['serial_number'], info['password']),
            port=info['port'],
            timeout=constants_v2.DEVICE_CONNECTION_TIMEOUT,
            token=token,
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

        bigip.f5os_client = None
        bigip.ve_tenant = None
        bigip.lag = None

        confd = info.get("confd", {})
        if confd.get("confd_username") and confd.get("confd_password") and confd.get("confd_hostname") and confd.get("confd_port"):  # noqa
            f5os_client = F5OSClient(
                host=confd.get("confd_hostname"),
                port=confd.get("confd_port"),
                user=decrypt_data(info['serial_number'], confd.get("confd_username")),  # noqa
                password=decrypt_data(info['serial_number'], confd.get("confd_password"))  # noqa
            )
            bigip.f5os_client = f5os_client

            if confd.get("lag_interface"):
                lag = LAG(f5os_client, name=confd.get("lag_interface"))
                bigip.lag = lag

            if confd.get("ve_tenant"):
                ve_tenant = Tenant(f5os_client, name=confd.get("ve_tenant"))
                bigip.ve_tenant = ve_tenant

    except Exception:
        LOG.error(
            "Could not establish connection with device %s,"
            " the device info is %s."
            % (host, info)
        )
        raise

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
        bigip = build_connection(host, info, self.conf.icontrol_token)
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
