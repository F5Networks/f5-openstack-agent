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
from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
OBJ_PREFIX = 'uuid_'
conf = cfg.CONF


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
            # args[0] must have service_queue_map attribute
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
        if phy_net is not None and phy_net == vtep_node_ip:
            return vlanid

    if default_vlanid is not None:
        return default_vlanid

    return network['provider:segmentation_id']


def modify_vtep_vlan(network, vtep_node_ip, seg_id):
    # NOTE(qzhao): only purge need this
    vlanid = None
    default_vlanid = None
    segments = network.get('segments', [])

    for seg in segments:
        phy_net = seg["provider:physical_network"]
        vlanid = seg["provider:segmentation_id"]

        if phy_net == "default":
            default_vlanid = vlanid
            default_seg = seg
        if phy_net is not None and phy_net == vtep_node_ip:
            seg["provider:segmentation_id"] = seg_id
            return

    if default_vlanid is not None:
        default_seg["provider:segmentation_id"] = seg_id
        return

    network['provider:segmentation_id'] = seg_id
    return


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


def is_common_network(network):
    """Returns True if this belongs in the /Common folder

    This object method will return positive if the object
    should be stored under the Common partition on the BIG-IP.
    """
    return network['shared'] or \
        conf.f5_common_networks or \
        (network['id'] in conf.common_network_ids) or \
        ('router:external' in network and
            network['router:external'] and
            conf.f5_common_external_networks)


def get_partition_name(tenant_id):
    prefix = OBJ_PREFIX + '_'
    name = "Common"

    if conf.environment_prefix:
        prefix = conf.environment_prefix + '_'
    if tenant_id is not None:
        name = prefix + tenant_id.replace('/', '')

    return name


def get_vlan_mac(helper, bigip, network, device):

    vtep_node_ip = get_node_vtep(device)
    vlanid = get_vtep_vlan(network, vtep_node_ip)
    vlan_name = "vlan-%d" % (vlanid)

    if is_common_network(network):
        partition = 'Common'
    else:
        partition = get_partition_name(
            network['tenant_id'])

    LOG.info("get MAC of Vlan: %s/%s" % (partition, vlan_name))

    stat_keys = ['macTrue']
    mac = None
    result = None
    count = 0
    while not result:
        try:
            result = helper.get_stats(
                bigip, name=vlan_name,
                partition=partition,
                stat_keys=stat_keys
            )

            LOG.info("get VLAN result: %s" % result)
            mac = result['macTrue']
        except Exception as exc:
            LOG.warning(
                "try %s can not get vlan MAC address of net %s."
                " on host %s. response is %s"
                " except %s" % (
                    count, network["id"], bigip.hostname,
                    result, exc
                )
            )
            result = None

        count += 1
        if count > 2:
            break

    # simplely check if the mac is valid
    if ":" not in mac:
        raise Exception("the Vlan MAC is invalid %s" % mac)

    LOG.info("get VLAN MAC: %s for network %s" %
             (mac, {network["id"]: vlan_name}))

    return mac


def vlan_to_rd_id(name):
    rd_id = name.split("-")[-1]
    return int(rd_id)


def check_port_llinfo(device, port):
    # return the comparsion result of mac and vtep
    # first element is the mac, the second element is the vtep

    # 1. the port may have or not have local_link_information
    # 2. if port have no local_link_information, it means
    #    the old environment port, nothing needs to change.
    # 3. if port have local_link_information, it must contain
    #    "lb_mac" and "node_vtep_ip"
    # 4. device must have local_link_information

    mac = True
    vtep = True

    LOG.debug(
        "check on local_link_information with device %s "
        "and port %s." % (device, port)
    )

    port_bp = port.get("binding:profile", {})
    port_llinfo = port_bp.get("local_link_information", [])
    # some ports in 9.4 do not have local_link_information
    # this is for backward compatible.
    if not port_llinfo or not port_llinfo[0]:
        return mac, vtep

    port_mac = port_llinfo[0].get("lb_mac")
    port_vtep = port_llinfo[0].get("node_vtep_ip")

    device_llinfo = device.get("local_link_information", [])
    # device_llinfo must contain "lb_mac" and "node_vtep_ip"
    device_mac = device_llinfo[0].get("lb_mac")
    device_vtep = device_llinfo[0].get("node_vtep_ip")

    return port_mac == device_mac, port_vtep == device_vtep


def update_port(port, binding_profile, rpc):
    # When a device is designated, and the new bigip hostname is as the
    # original device, the port (selfip/snatip) need to update.

    # either mac or vtep is changed, we update the port

    same_mac, same_vtep = check_port_llinfo(
        binding_profile, port)

    if not all([same_vtep, same_mac]):
        try:
            reserve_dev_owner = port["device_owner"]
            if not reserve_dev_owner:
                reserve_dev_owner = "network:f5lbaasv2"

            LOG.info("smae_mac, same_vtep is changed, reset port device owner")
            port = rpc.update_port_on_subnet(
                port_id=port['id'],
                device_owner=""
            )

            LOG.info("reassign port attrs binding_profile %s, device_owner %s",
                     binding_profile, reserve_dev_owner)
            port = rpc.update_port_on_subnet(
                port_id=port['id'],
                binding_profile=binding_profile,
                device_owner=reserve_dev_owner
            )

        except Exception:
            LOG.exception(
                "fail to update port %s. same_mac is %s, same_vtep is %s." %
                (port, same_mac, same_vtep))
            raise

    return port
