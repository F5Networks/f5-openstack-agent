"""Utility classes and functions."""
# Copyright (c) 2014-2018, F5 Networks, Inc.
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
from time import time
import uuid

from distutils.version import LooseVersion
from eventlet import greenthread
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
OBJ_PREFIX = 'uuid_'


class IpNotInCidrNotation(Exception):
    pass


def strip_domain_address(ip_address):
    """Return the address or address/netmask from a route domain address.

    When an address is retrieved from the BIG-IP that has a route domain
    it contains a %<number> in it.  We need to strip that out so we are
    just dealing with an IP address or IP address/mask.

    Examples:
        192.168.1.1%20 ==> 192.168.1.1
        192.168.1.1%20/24 ==> 192.168.1.1/24
    """
    mask_index = ip_address.find('/')
    if mask_index > 0:
        return ip_address[:mask_index].split('%')[0] + ip_address[mask_index:]
    else:
        return ip_address.split('%')[0]


def serialized(method_name):
    """Outer wrapper in order to specify method name."""
    def real_serialized(method):
        """Decorator to serialize calls to configure via iControl."""
        def wrapper(*args, **kwargs):
            """Necessary wrapper."""
            # args[0] must be an instance of iControlDriver
            service_queue_map = args[0].service_queue_map
            service_queue = service_queue_map["default"]
            my_request_id = uuid.uuid4()

            service = None
            if len(args) > 0:
                last_arg = args[-1]
                if isinstance(last_arg, dict) and ('loadbalancer' in last_arg):
                    service = last_arg

            if 'service' in kwargs:
                service = kwargs['service']

            # Construct a queue for each device
            if "device" in service:
                device_id = service["device"]["id"]
                if device_id not in service_queue_map:
                    service_queue_map[device_id] = []
                service_queue = service_queue_map[device_id]

            # Consolidate create_member requests for the same pool.
            #
            # NOTE: The following block of code alters the state of
            # a queue that other greenthreads are waiting behind.
            # This code assumes it will not be preempted by another
            # greenthread while running. It does not do I/O or call any
            # other monkey-patched code which might cause a context switch.
            # To avoid race conditions, DO NOT add logging to this code
            # block.

            req = (my_request_id, method_name, service)
            service_queue.append(req)
            reqs_ahead_of_us = request_index(service_queue, my_request_id)
            while reqs_ahead_of_us != 0:
                if reqs_ahead_of_us == 1:
                    # it is almost our turn. get ready
                    waitsecs = .01
                else:
                    waitsecs = reqs_ahead_of_us * .5
                if waitsecs > .01:
                    LOG.debug('%s request %s is blocking'
                              ' for %.2f secs - queue depth: %d'
                              % (str(method_name), my_request_id,
                                 waitsecs, len(service_queue)))
                greenthread.sleep(waitsecs)
                reqs_ahead_of_us = request_index(service_queue, my_request_id)
            try:
                LOG.debug('%s request %s is running with queue depth: %d'
                          % (str(method_name), my_request_id,
                             len(service_queue)))
                start_time = time()
                result = method(*args, **kwargs)
                LOG.debug('%s request %s took %.5f secs'
                          % (str(method_name), my_request_id,
                             time() - start_time))
            except Exception:
                LOG.error('%s request %s FAILED'
                          % (str(method_name), my_request_id))
                raise
            finally:
                service_queue.pop(0)
            return result
        return wrapper
    return real_serialized


def request_index(request_queue, request_id):
    """Get index of request in request queue.

    If we are not in the queue return the length of the list.
    """
    for request in request_queue:
        if request[0] == request_id:
            return request_queue.index(request)
    return len(request_queue)


def get_filter(bigip, key, op, value):
    if LooseVersion(bigip.tmos_version) < LooseVersion('11.6.0'):
        return '$filter=%s+%s+%s' % (key, op, value)
    else:
        return {'$filter': '%s %s %s' % (key, op, value)}


def strip_cidr_netmask(ip_address):
    '''Strip the /XX from the end of a CIDR address

    :param ip_address: str -- IP address string
    :returns: str -- IP address without mask
    :raises: IpNotInCidrNotation
    '''

    split_ip = ip_address.split('/')
    if len(split_ip) == 2:
        return split_ip[0]
    else:
        msg = 'The IP address provided was not in CIDR notation.'
        raise IpNotInCidrNotation(msg)


def get_device_info(bigip):
    '''Get device information for the current device being queried

    :param bigip: ManagementRoot object --- device to query
    :returns: ManagementRoot object
    '''

    coll = bigip.tm.cm.devices.get_collection()
    device = [device for device in coll if device.selfDevice == 'true']
    return device[0]


def parse_iface_mapping(bigip, mapping):

    if not mapping:
        raise Exception(
            "Cannot find external_physical_mappings, "
            "VLANs can not be set on any bigip interface."
        )
    iface_mapping = dict()
    mapping = [
        m.strip() for m in mapping.split(',')
    ]

    for m in mapping:
        phy_iface = m.split(':')
        iface = str(phy_iface[1]).strip()
        net_key = str(phy_iface[0]).strip()

        mac = get_iface_mac(bigip, iface)

        iface_mac_map = {iface: mac}
        iface_mapping[net_key] = iface_mac_map

    return iface_mapping


def get_net_iface(iface_mapping, network):
    net_key = network['provider:physical_network']

    if net_key and net_key in iface_mapping:
        iface_mac = iface_mapping[net_key]
        return iface_mac.keys()[0]

    if "default" not in iface_mapping:
        raise Exception(
            'Cannot find bigip interface mapping for '
            'unknown neutron network %s. Please set '
            'default interface mapping for the unknown '
            'network.' % network
        )
    default_iface_mac = iface_mapping["default"]
    return default_iface_mac.keys()[0]


def get_iface_mac(bigip, iface):
    cmd = "-c 'tmsh show sys mac-address | grep \" " + \
        iface + " \"'"
    try:
        resp = bigip.tm.util.bash.exec_cmd(
            command='run',
            utilCmdArgs=cmd
        )
        mac = resp.commandResult.split()[0]
        if not mac:
            raise Exception("found empty MAC")
        return mac
    except Exception as exc:
        LOG.error(
            "Can not get MAC address of interface/trunk: %s."
            " on host %s. Exception: %s.\n Please check "
            "your external_physical_mappings." % (
                iface, bigip.hostname, exc
            )
        )
        raise exc


def get_mac_by_net(bigip, net, device):
    try:
        net_key = net['provider:physical_network']
        iface_mapping = device['bigip'][bigip.hostname][
            'device_info']['external_physical_mappings']

        iface_mac = iface_mapping.get(net_key)

        if not iface_mac and not iface_mapping.get("default"):
            raise Exception(
                "The default interface not found in %s" %
                iface_mapping.get
            )
        else:
            default_iface_mac = iface_mapping.get("default")
            return default_iface_mac.values()[0]

        return iface_mac.values()[0]

    except Exception as exc:
        LOG.error(
            "Can not get MAC address of network: %s."
            "The device is %s." % (net, device)
        )
        raise exc


def get_vtep_vlan(network, vtep_node_ip):
    vlanid = None
    default_vlanid = None
    segments = network.get('segments', [])

    for seg in segments:
        phy_net = seg["provider:physical_network"]
        vlanid = seg["provider:segmentation_id"]

        if phy_net == "default":
            default_vlanid = vlanid
        if phy_net == vtep_node_ip:
            return vlanid

    if default_vlanid is not None:
        return default_vlanid

    return network['provider:segmentation_id']


def get_node_vtep(device):
    if not device:
        raise Exception(
            "device is not provided"
        )

    llinfo = device['device_info'].get('local_link_information')

    if not llinfo:
        return

    vtep_node = llinfo[0].get('node_vtep_ip')
    if vtep_node:
        return vtep_node
