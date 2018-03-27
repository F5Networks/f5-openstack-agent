# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


import collections
import netaddr


class InvalidArgumentError(ValueError):
    pass


def track_call(func):
    def wrapper(*f_args, **f_kwargs):

        arg_names = func.func_code.co_varnames[:func.func_code.co_argcount]
        args = f_args[:len(arg_names)]
        zipped_args = zip(arg_names, args)
        all_args = dict(zipped_args + f_kwargs.items())

        obj = f_args[0]
        obj.record_call(func.func_name, all_args)

        return func(*f_args, **f_kwargs)
    return wrapper


class FakeRPCPlugin(object):

    def __init__(self, services):
        self._subnets = {}
        self._ports = {}
        self._loadbalancers = {}
        # The following is a bit of a hack, it allows us to handle 
        # two types of service objects.  For back compatibility we need to
        # support services-as-lists.
        if isinstance(services, collections.OrderedDict):
            self._services = services.values()
        else:
            self._services = services[:]
        self._current_service = 0
        self._initialize_subnets(self._services)
        self._initialize_loadbalancers(self._services)
        self._calls = {}

    def _initialize_loadbalancers(self, services):
        pass

    def _init_subnet_addr_generator(self, subnet_id, subnet):
        def ip_generator(ip_list):
            for ip in ip_list:
                yield ip

        if not subnet:
            self._subnets[subnet_id] = ip_generator([])

        allocation_pools = subnet.get('allocation_pools', None)
        for pool in allocation_pools:
            start = pool['start']
            end = pool['end']
            ip_list = list(str(ip) for ip in
                           netaddr.iter_iprange(start, end))

        self._subnets[subnet_id] = ip_generator(
            [ip for ip in ip_list])

    def _initialize_subnets(self, services):
        for service in services:
            for subnet in service['subnets']:
                self._init_subnet_addr_generator(
                    subnet,
                    service['subnets'].get(subnet, None))

    def record_call(self, method, call_args):
        history = self._calls.get(method, [])
        history.append(call_args)
        self._calls[method] = history

    def get_calls(self, method):
        return self._calls.get(method, [])

    def get_call_count(self, method):
        return len(self._calls.get(method, []))

    def set_current_service(self, service_id):
        self._current_service = service_id

    def get_ports_for_mac_addresses(self, mac_addresses=list()):
        return list()

    @track_call
    def create_port_on_subnet(self,
                              subnet_id=None,
                              mac_address=None,
                              name=None,
                              fixed_address_count=1,
                              device_id=None,
                              vnic_type=None,
                              binding_profile={}):

        # Enforce specific call parameters
        if not subnet_id:
            raise InvalidArgumentError
        if mac_address:
            raise InvalidArgumentError
        if not name:
            raise InvalidArgumentError
        if fixed_address_count != 1:
            raise InvalidArgumentError
        if vnic_type != "baremetal":
            raise InvalideArgumentError

        ip_address = next(self._subnets[subnet_id])

        retval = {'fixed_ips': [{'ip_address': ip_address}]}
        self._ports[name] = [retval]

        return retval

    @track_call
    def create_port_on_network(self,
                               network_id=None,
                               mac_address=None,
                               name=None,
                               host=None):
        # Enforce specific call parameters
        if not network_id:
            raise InvalidArgumentError
        if mac_address:
            raise InvalidArgumentError
        if not name:
            raise InvalidArgumentError

        ip_address = "127.0.0.1"

        retval = {'fixed_ips': [{'ip_address': ip_address}]}
        self._ports[name] = [retval]

        return retval

    @track_call
    def get_port_by_name(self, port_name=None):
        if not port_name:
            raise InvalidArgumentError
        retval = self._ports.get(port_name, [])
        return retval

    @track_call
    def delete_port_by_name(self, port_name=None):
        if not port_name:
            raise InvalidArgumentError
        self._ports.pop(port_name, None)

    @track_call
    def update_loadbalancer_status(self, lb_id,
                                   provisioning_status="ERROR",
                                   operating_status="OFFLINE"):
        pass

    @track_call
    def update_listener_status(self, listener_id,
                               provisioning_status="ERROR",
                               operating_status="OFFLINE"):
        pass

    @track_call
    def update_pool_status(self, pool_id,
                           provisioning_status="ERROR",
                           operating_status="OFFLINE"):
        pass

    @track_call
    def update_member_status(self, member_id,
                             provisioning_status="ERROR",
                             operating_status="OFFLINE"):
        pass

    @track_call
    def update_health_monitor_status(self, health_monitor_id,
                                     provisioning_status="ERROR",
                                     operating_status="OFFLINE"):
        pass

    @track_call
    def update_l7policy_status(self, l7policy_id,
                                     provisioning_status="ERROR",
                                     operating_status="OFFLINE"):
        pass

    @track_call
    def update_l7rule_status(self, l7rule_id, l7policy_id,
                                   provisioning_status="ERROR",
                                   operating_status="OFFLINE"):
        pass

    @track_call
    def health_monitor_destroyed(self, id):
        pass

    @track_call
    def loadbalancer_destroyed(self, lb_id):
        pass

    @track_call
    def listener_destroyed(self, id):
        pass

    @track_call
    def pool_destroyed(self, id):
        pass

    @track_call
    def member_destroyed(self, id):
        pass

    @track_call
    def l7policy_destroyed(self, id):
        pass

    @track_call
    def get_all_loadbalancers(self, env=None, group=None, host=None):
        return_value = [
            {'lb_id': u'50c5d54a-5a9e-4a80-9e74-8400a461a077'}
        ]
        return return_value

    @track_call
    def get_service_by_loadbalancer_id(self, lb_id):
        return self._services[self._current_service]
