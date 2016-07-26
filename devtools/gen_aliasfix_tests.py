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
import os

TESTTEMPLATE = '''def test_{}_for_aliases():
    #tree = ast.parse(open(
    #    '/root/devenv/f5-openstack-agent/f5_openstack_agent'
    #    '/lbaasv2/drivers/bigip/icontrol_driver.py').read())
    tree = ast.parse(open(
        '/root/devenv/f5-openstack-agent/f5_openstack_agent'
        '/lbaasv2/drivers/bigip/{}.py').read())
    #tree = ast.parse(open(DISTROOT+'/ast_example.py').read())
    clv = CreateLoadValidator()
    clv.visit(tree)
    for urde in clv.urde_calls:
        clv.check_for_cl_call(urde.func.value)
    assert clv.anti_patterns == []

'''


fnames = os.listdir('/root/devenv/f5-openstack-agent/f5_openstack_agent/lbaasv2/drivers/bigip')


for fn in fnames:
    if fn[-3:] == '.py':
        print(TESTTEMPLATE.format(fn[:-3], fn[:-3]))
