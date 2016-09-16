# Copyright 2015-2106 F5 Networks Inc.
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

import decorator
import pytest

from f5_openstack_agent.lbaasv2.drivers.bigip.network_helper import \
    NetworkHelper
from f5_openstack_agent.lbaasv2.drivers.bigip.system_helper import \
    SystemHelper
from pprint import pprint
from requests.exceptions import HTTPError


network_helper = NetworkHelper()
system_helper = SystemHelper()
default_partition = 'test'


def log_test_call(func):
    def wrapper(func, *args, **kwargs):
        print("\nRunning %s" % func.func_name)
        return func(*args, **kwargs)
    return decorator.decorator(wrapper, func)


def delete_resource(resource):
    try:
        resource.delete()
    except HTTPError as err:
        if err.response.status_code != 404:
            raise


def add_resource_teardown(request, resource):
    def teardown():
        delete_resource(resource)
    request.addfinalizer(teardown)


class ExecTestEnv(object):
    def __init__(self):
        pass


@pytest.fixture
def setup(request, bigip):
    def teardown():
        system_helper.delete_folder(bigip, default_partition)
    request.addfinalizer(teardown)

    system_helper.create_folder(bigip, {'name': default_partition,
                                        'subPath': '/'})
    assert system_helper.folder_exists(bigip, default_partition)

    te = ExecTestEnv
    te.bigip = bigip
    te.request = request
    te.partition = default_partition
    return te


@log_test_call
def test_gre_profile(setup):
    te = setup
    name = 'test_gre_profile'
    profile = network_helper.create_l2gre_multipoint_profile(te.bigip, name,
                                                             te.partition)
    add_resource_teardown(te.request, profile)
    params = {'params': {'$filter': 'partition eq %s' % te.partition}}
    gc = te.bigip.net.tunnels.gres
    profiles = gc.get_collection(requests_params=params)
    profile_names = (r.name for r in profiles)
    assert(name in profile_names)
    p = te.bigip.net.tunnels.gres.gre
    p.load(name=name, partition=te.partition)
    payload = NetworkHelper.l2gre_multipoint_profile_defaults
    for k in payload.keys():
        if k == 'partition':
            continue
        assert(p.__dict__[k] == profile.__dict__[k])


@log_test_call
def test_vxlan_profile(setup):
    te = setup
    name = 'test_vxlan_profile'
    profile = network_helper.create_vxlan_multipoint_profile(te.bigip, name,
                                                             te.partition)
    add_resource_teardown(te.request, profile)
    params = {'params': {'$filter': 'partition eq %s' % te.partition}}
    vc = te.bigip.net.tunnels.vxlans
    profiles = vc.get_collection(requests_params=params)
    profile_names = (r.name for r in profiles)
    assert(name in profile_names)
    p = te.bigip.net.tunnels.vxlans.vxlan
    p.load(name=name, partition=te.partition)
    payload = NetworkHelper.vxlan_multipoint_profile_defaults
    for k in payload.keys():
        if k == 'partition':
            continue
        assert(p.__dict__[k] == profile.__dict__[k])


@log_test_call
def test_get_gre_tunnel_key(setup):
    te = setup
    name = 'test_tunnel'
    profile = 'gre'  # pre-exiting profile on BIGIP
    local_ip = '192.168.102.1'
    remote_ip = '192.168.102.2'
    t = te.bigip.net.tunnels.tunnels.tunnel
    t.create(name=name, partition=te.partition,
             localAddress=local_ip, remoteAddress=remote_ip, profile=profile)
    add_resource_teardown(te.request, t)
    key = network_helper.get_l2gre_tunnel_key(te.bigip, name, te.partition)
    assert(key == t.key)


@log_test_call
def test_get_vxlan_tunnel_key(setup):
    te = setup
    name = 'test_tunnel'
    profile = 'vxlan'  # pre-exiting profile on BIGIP
    local_ip = '224.0.0.1'
    remote_ip = '224.0.0.2'
    t = te.bigip.net.tunnels.tunnels.tunnel
    t.create(name=name, partition=te.partition,
             localAddress=local_ip, remoteAddress=remote_ip, profile=profile)
    add_resource_teardown(te.request, t)
    key = network_helper.get_vxlan_tunnel_key(te.bigip, name, te.partition)
    assert(key == t.key)


@log_test_call
def test_get_vlan_id(setup):
    te = setup
    name = 'test_vlan'
    v = te.bigip.net.vlans.vlan
    v.create(name=name, partition=te.partition)
    add_resource_teardown(te.request, v)
    id = network_helper.get_vlan_id(te.bigip, name, te.partition)
    assert(id == v.tag)


def create_selfip(te, vname, index):
    sname = 'test_selfip_%s' % index
    saddr = '192.168.101.%s/32' % index
    s = te.bigip.net.selfips.selfip
    s.create(name=sname, partition=te.partition, address=saddr,
             vlan=vname)
    add_resource_teardown(te.request, s)
    return s


@log_test_call
def test_get_selfip_addr(setup):
    te = setup
    vname = 'test_internal'
    v = te.bigip.net.vlans.vlan
    v.create(name=vname, partition=te.partition)
    add_resource_teardown(te.request, v)
    s = create_selfip(te, vname, 1)
    addr = network_helper.get_selfip_addr(te.bigip, s.name, te.partition)
    assert(addr == s.address)


@log_test_call
def test_get_selfips(setup):
    te = setup
    vname = 'test_internal'
    v = te.bigip.net.vlans.vlan
    v.create(name=vname, partition=te.partition)
    add_resource_teardown(te.request, v)
    num_selfips = 5
    exp_selfip_name_list = []
    for i in range(0, num_selfips):
        s = create_selfip(te, vname, i)
        exp_selfip_name_list.append(s.name)
    selfips = network_helper.get_selfips(te.bigip, te.partition, vname)
    selfip_names_list = [selfip.name for selfip in selfips]
    assert(num_selfips == len(selfip_names_list))
    for exp_selfip_name in exp_selfip_name_list:
        assert(exp_selfip_name in selfip_names_list)


@log_test_call
def test_delete_selfip(setup):
    te = setup
    vname = 'test_internal'
    v = te.bigip.net.vlans.vlan
    v.create(name=vname, partition=te.partition)
    add_resource_teardown(te.request, v)
    s = create_selfip(te, vname, 1)
    sname = s.name  # cache since the attr might disappear from the object
    network_helper.delete_selfip(te.bigip, sname, te.partition)
    assert not s.exists(name=sname, partition=te.partition)


class TestRouteDomain(object):

    @log_test_call
    def test_route_domain_CRUD(self, setup):
        te = setup
        rd_create = network_helper.create_route_domain(te.bigip, te.partition)
        add_resource_teardown(te.request, rd_create)
        rd_read = network_helper.get_route_domain(te.bigip, te.partition)
        assert(rd_read.name == rd_read.name)
        rdc = te.bigip.net.route_domains
        params = {'params': {'$filter': 'partition eq %s' % te.partition}}
        route_domains = rdc.get_collection(requests_params=params)
        rd_names = (rd.name for rd in route_domains)
        assert(rd_create.name in rd_names)
        assert(network_helper.route_domain_exists(te.bigip, te.partition))
        network_helper.delete_route_domain(te.bigip, te.partition,
                                           rd_create.name)

    @log_test_call
    def test_route_domain_get_ids(self, setup):
        te = setup
        num_route_domains = 5
        exp_rd_ids = []
        for i in range(0, num_route_domains):
            rd = network_helper.create_route_domain(te.bigip, te.partition,
                                                    is_aux=True)
            add_resource_teardown(te.request, rd)
            exp_rd_ids.append(rd.id)
        rd_ids = network_helper.get_route_domain_ids(te.bigip, te.partition)
        assert(num_route_domains == len(rd_ids))
        for exp_rd_id in exp_rd_ids:
            assert(exp_rd_id in rd_ids)

    @log_test_call
    def test_route_domain_get_names(self, setup):
        te = setup
        num_route_domains = 5
        exp_rd_names = []
        for i in range(0, num_route_domains):
            rd = network_helper.create_route_domain(te.bigip, te.partition,
                                                    is_aux=True)
            add_resource_teardown(te.request, rd)
            exp_rd_names.append(rd.name)
        rd_names = network_helper.get_route_domain_names(te.bigip,
                                                         te.partition)
        assert(num_route_domains == len(rd_names))
        for exp_rd_name in exp_rd_names:
            assert(exp_rd_name in rd_names)

    @log_test_call
    def test_route_domain_get_vlans_by_id(self, setup):
        te = setup
        vname = 'test_internal'
        v = te.bigip.net.vlans.vlan
        v.create(name=vname, partition=te.partition)
        add_resource_teardown(te.request, v)
        rd = network_helper.create_route_domain(te.bigip, te.partition)
        add_resource_teardown(te.request, rd)
        network_helper.add_vlan_to_domain(te.bigip, vname,
                                          te.partition)
        vlans = network_helper.get_vlans_in_route_domain(te.bigip,
                                                         te.partition)
        vpath = "/%s/%s" % (te.partition, vname)
        assert(vpath in vlans)


def create_arp(te, name, ipaddr, macaddr):
    a = te.bigip.net.arps.arp
    a.create(name=name, partition=te.partition, ipAddress=ipaddr,
             macAddress=macaddr)
    add_resource_teardown(te.request, a)
    return a


def print_arps(te):
    ac = te.bigip.net.arps
    params = {'params': {'$filter': 'partition eq %s' % te.partition}}
    arps = ac.get_collection(requests_params=params)
    for arp in arps:
        pprint(arp.__dict__)


@log_test_call
def test_arp_delete_by_network(setup):
    te = setup
    #  iteration 0, subnet with mask=None which should return empty list
    create_arp(te, 'test_arp_0', '192.168.101.1', 'ff:ee:dd:cc:bb:aa')
    create_arp(te, 'test_arp_1', '192.168.101.2', 'ff:aa:bb:cc:dd:ee')
    subnet = '192.168.101.1'
    deleted_macs = network_helper.arp_delete_by_subnet(te.bigip, subnet, None,
                                                       te.partition)
    assert(len(deleted_macs) == 0)
    #  iteration 1, subnet = CIDR which should return non-empty list
    create_arp(te, 'test_arp_2', '192.168.102.1', 'ff:ee:dd:cc:bb:aa')
    create_arp(te, 'test_arp_3', '192.168.102.2', 'ff:aa:bb:cc:dd:ee')
    subnet = '192.168.102.1/32'
    deleted_macs = network_helper.arp_delete_by_subnet(te.bigip, subnet, None,
                                                       te.partition)
    assert(len(deleted_macs) == 1)
    assert(deleted_macs[0] == 'ff:ee:dd:cc:bb:aa')
    #  iteration 2, subnet with mask which should return non-empty list
    create_arp(te, 'test_arp_4', '192.168.103.1', 'ff:ee:dd:cc:bb:aa')
    create_arp(te, 'test_arp_5', '192.168.103.2', 'ff:aa:bb:cc:dd:ee')
    subnet = '192.168.103.1'
    mask = '24'
    deleted_macs = network_helper.arp_delete_by_subnet(te.bigip, subnet, mask,
                                                       te.partition)
    deleted_macs = sorted(deleted_macs)
    assert(len(deleted_macs) == 2)
    assert(deleted_macs[0] == 'ff:aa:bb:cc:dd:ee')
    assert(deleted_macs[1] == 'ff:ee:dd:cc:bb:aa')
