# coding=utf-8
#
# Copyright 2014-2016 F5 Networks Inc.
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

import ast
import os
from pprint import pprint as pp

osd = os.path.dirname
DISTROOT = osd(osd(osd(osd(osd(__file__)))))
del osd

class UnexpectedCallNodeFuncType(Exception):
    pass


class CreateLoadValidator(ast.NodeVisitor):
    def __init__(self):
        self.cl_calls = []
        self.cl_assignments = []
        self.urd_calls = []
        self.anti_patterns = []


    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and\
            isinstance(node.func.ctx, ast.Load):
            if node.func.attr == 'create' or node.func.attr == 'load':
                self.cl_calls.append(node)
            elif node.func.attr == 'update' or\
                 node.func.attr == 'refresh' or\
                 node.func.attr == 'delete':
                self.urd_calls.append(node)
        self.generic_visit(node)

    def visit_Assign(self, node):
        rhs = node.value
        if isinstance(rhs, ast.Call):
            if isinstance(rhs.func, ast.Attribute):
                if rhs.func.attr == 'create' or rhs.func.attr == 'load':
                    if isinstance(rhs.func.ctx, ast.Load):
                        self.cl_assignments.append(node.targets[0])
        self.generic_visit(node)

    def check_for_cl_call(self, node):
        while not isinstance(node, ast.Name):
            if isinstance(node, ast.Call):
                if node.func.attr == 'load' or node.func.attr == 'create':
                    return True
                
            elif isinstance(node, ast.Attribute):
                node = node.value
            else:
                raise UnexpectedCallNodeFuncType(node)
        for assigned_node in self.cl_assignments:
            if assigned_node.lineno <= node.lineno:
                if assigned_node.col_offset <= node.col_offset:
                    if assigned_node.id == node.id:
                        return True
        self.anti_patterns.append((node.lineno))
        return False


def test_lbaas_driver_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/lbaas_driver.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_barbican_cert_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/barbican_cert.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_fdb_connector_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/fdb_connector.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_cluster_manager_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/cluster_manager.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_icontrol_driver_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test___init___for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/__init__.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_listener_service_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/listener_service.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_tenants_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/tenants.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_fdb_connector_ml2_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/fdb_connector_ml2.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_agent_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/agent.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_cert_manager_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/cert_manager.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_stat_helper_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/stat_helper.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_utils_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/utils.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_pool_service_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/pool_service.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_ssl_profile_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/ssl_profile.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_snats_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/snats.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_vlan_binding_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/vlan_binding.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_system_helper_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/system_helper.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_network_service_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/network_service.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_constants_v2_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/constants_v2.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_resource_helper_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/resource_helper.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_vcmp_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/vcmp.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_lbaas_builder_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/lbaas_builder.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_plugin_rpc_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/plugin_rpc.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_exceptions_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/exceptions.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_network_helper_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/network_helper.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_agent_manager_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/agent_manager.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_loadbalancer_service_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/loadbalancer_service.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_l3_binding_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/l3_binding.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_l2_service_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/l2_service.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_service_adapter_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/service_adapter.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


def test_selfips_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/selfips.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urd in clv.urd_calls:
        clv.check_for_cl_call(urd.func.value)
    assert clv.anti_patterns == []


