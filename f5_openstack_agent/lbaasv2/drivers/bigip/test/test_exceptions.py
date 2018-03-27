#!/usr/bin/env python
# Copyright (c) 2017,2018, F5 Networks, Inc.
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

import inspect
import logging
import pdb
import pytest
import sys
import traceback

import f5_openstack_agent.lbaasv2.drivers.bigip.exceptions as exceptions

from collections import namedtuple
from mock import Mock
from mock import mock_open
from mock import patch


class Test_F5MissingDependencies(object):
    open_name = 'f5_openstack_agent.lbaasv2.drivers.bigip.exceptions.open'

    def setup_iterations(self):
        Options = \
            namedtuple('Options',
                       'errno, message, details, exception, frame')
        set_frame = inspect.getframeinfo(inspect.currentframe())
        items = [Options(None, None, [], None, None),
                 Options(22, 'missing', [31415926], ImportError('foodogzoo'),
                         set_frame),
                 Options(22, 'missing', [31415926], None, set_frame)]
        logging.FileHandler = Mock()
        logging.getLogger = Mock()
        sys.argv.append('f5-openstack-agent.ini')
        return items, set_frame

    def test_iterations(self):
        test_items, set_frame = self.setup_iterations()
        traceback.print_exc = Mock()
        for tset in test_items:
            message = tset.message
            errno = tset.errno
            details = tset.details
            exc = tset.exception
            fr = tset.frame
            read_lines = 'debug = true\n'
            m_open = mock_open(read_data=read_lines)
            with patch(self.open_name, m_open, create=True):
                exception = \
                    exceptions.F5MissingDependencies(*details, message=message,
                                                     errno=errno,
                                                     exception=exc, frame=fr)
            assert traceback.print_exc.called
            with pytest.raises(exceptions.F5MissingDependencies):
                if errno:
                    assert errno == exception.errno, "Errno Set Test"
                else:
                    assert exceptions.F5MissingDependencies.default_errno == \
                        exception.errno, "Errno Not Set Test"
                if details and not exc:
                    for item in details:
                        assert str(item) in str(exception), \
                            "Details Inclusion Test"
                elif exc:
                    assert str(exc) in str(exception), \
                        "Exception Inclusion Test"
                if fr:
                    assert str(set_frame.lineno) in str(exception) and \
                        fr.filename in str(exception), "Frame Inclusion Test"
                raise exception

    def test_debug_false(self):
        traceback.print_exc = Mock()

        read_lines = 'debug = false\n'
        m_open = mock_open(read_data=read_lines)
        with patch(self.open_name, m_open, create=True):
            exceptions.F5MissingDependencies()
        assert not traceback.print_exc.called, 'debug negative test'


def test_F5AgentException():
    with pytest.raises(exceptions.F5AgentException):
        raise getattr(exceptions, 'F5AgentException')()


def test_MinorVersionValidateFailed():
    with pytest.raises(exceptions.MinorVersionValidateFailed):
        raise getattr(exceptions, 'MinorVersionValidateFailed')()


def test_MajorVersionValidateFailed():
    with pytest.raises(exceptions.MajorVersionValidateFailed):
        raise getattr(exceptions, 'MajorVersionValidateFailed')()


def test_ProvisioningExtraMBValidateFailed():
    with pytest.raises(
            exceptions.ProvisioningExtraMBValidateFailed):
        raise getattr(exceptions, 'ProvisioningExtraMBValidateFailed')()


def test_BigIPDeviceLockAcquireFailed():
    with pytest.raises(exceptions.BigIPDeviceLockAcquireFailed):
        raise getattr(exceptions, 'BigIPDeviceLockAcquireFailed')()


def test_BigIPClusterInvalidHA():
    with pytest.raises(exceptions.BigIPClusterInvalidHA):
        raise getattr(exceptions, 'BigIPClusterInvalidHA')()


def test_BigIPClusterSyncFailure():
    with pytest.raises(exceptions.BigIPClusterSyncFailure):
        raise getattr(exceptions, 'BigIPClusterSyncFailure')()


def test_BigIPClusterPeerAddFailure():
    with pytest.raises(exceptions.BigIPClusterPeerAddFailure):
        raise getattr(exceptions, 'BigIPClusterPeerAddFailure')()


def test_BigIPClusterConfigSaveFailure():
    with pytest.raises(exceptions.BigIPClusterConfigSaveFailure):
        raise getattr(exceptions, 'BigIPClusterConfigSaveFailure')()


def test_UnknownMonitorType():
    with pytest.raises(exceptions.UnknownMonitorType):
        raise getattr(exceptions, 'UnknownMonitorType')()


def test_MissingVTEPAddress():
    with pytest.raises(exceptions.MissingVTEPAddress):
        raise getattr(exceptions, 'MissingVTEPAddress')()


def test_MissingNetwork():
    with pytest.raises(exceptions.MissingNetwork):
        raise getattr(exceptions, 'MissingNetwork')()


def test_InvalidNetworkType():
    with pytest.raises(exceptions.InvalidNetworkType):
        raise getattr(exceptions, 'InvalidNetworkType')()


def test_StaticARPCreationException():
    with pytest.raises(exceptions.StaticARPCreationException):
        raise getattr(exceptions, 'StaticARPCreationException')()


def test_StaticARPQueryException():
    with pytest.raises(exceptions.StaticARPQueryException):
        raise getattr(exceptions, 'StaticARPQueryException')()


def test_StaticARPDeleteException():
    with pytest.raises(exceptions.StaticARPDeleteException):
        raise getattr(exceptions, 'StaticARPDeleteException')()


def test_ClusterCreationException():
    with pytest.raises(exceptions.ClusterCreationException):
        raise getattr(exceptions, 'ClusterCreationException')()


def test_ClusterUpdateException():
    with pytest.raises(exceptions.ClusterUpdateException):
        raise getattr(exceptions, 'ClusterUpdateException')()


def test_ClusterQueryException():
    with pytest.raises(exceptions.ClusterQueryException):
        raise getattr(exceptions, 'ClusterQueryException')()


def test_ClusterDeleteException():
    with pytest.raises(exceptions.ClusterDeleteException):
        raise getattr(exceptions, 'ClusterDeleteException')()


def test_DeviceCreationException():
    with pytest.raises(exceptions.DeviceCreationException):
        raise getattr(exceptions, 'DeviceCreationException')()


def test_DeviceUpdateException():
    with pytest.raises(exceptions.DeviceUpdateException):
        raise getattr(exceptions, 'DeviceUpdateException')()


def test_DeviceQueryException():
    with pytest.raises(exceptions.DeviceQueryException):
        raise getattr(exceptions, 'DeviceQueryException')()


def test_DeviceDeleteException():
    with pytest.raises(exceptions.DeviceDeleteException):
        raise getattr(exceptions, 'DeviceDeleteException')()


def test_InterfaceQueryException():
    with pytest.raises(exceptions.InterfaceQueryException):
        raise getattr(exceptions, 'InterfaceQueryException')()


def test_IAppCreationException():
    with pytest.raises(exceptions.IAppCreationException):
        raise getattr(exceptions, 'IAppCreationException')()


def test_IAppQueryException():
    with pytest.raises(exceptions.IAppQueryException):
        raise getattr(exceptions, 'IAppQueryException')()


def test_IAppUpdateException():
    with pytest.raises(exceptions.IAppUpdateException):
        raise getattr(exceptions, 'IAppUpdateException')()


def test_IAppDeleteException():
    with pytest.raises(exceptions.IAppDeleteException):
        raise getattr(exceptions, 'IAppDeleteException')()


def test_L2GRETunnelCreationException():
    with pytest.raises(exceptions.L2GRETunnelCreationException):
        raise getattr(exceptions, 'L2GRETunnelCreationException')()


def test_L2GRETunnelQueryException():
    with pytest.raises(exceptions.L2GRETunnelQueryException):
        raise getattr(exceptions, 'L2GRETunnelQueryException')()


def test_L2GRETunnelUpdateException():
    with pytest.raises(exceptions.L2GRETunnelUpdateException):
        raise getattr(exceptions, 'L2GRETunnelUpdateException')()


def test_L2GRETunnelDeleteException():
    with pytest.raises(exceptions.L2GRETunnelDeleteException):
        raise getattr(exceptions, 'L2GRETunnelDeleteException')()


def test_MemberCreationException():
    with pytest.raises(exceptions.MemberCreationException):
        raise getattr(exceptions, 'MemberCreationException')()


def test_MemberQueryException():
    with pytest.raises(exceptions.MemberQueryException):
        raise getattr(exceptions, 'MemberQueryException')()


def test_MemberUpdateException():
    with pytest.raises(exceptions.MemberUpdateException):
        raise getattr(exceptions, 'MemberUpdateException')()


def test_MemberDeleteException():
    with pytest.raises(exceptions.MemberDeleteException):
        raise getattr(exceptions, 'MemberDeleteException')()


def test_MonitorCreationException():
    with pytest.raises(exceptions.MonitorCreationException):
        raise getattr(exceptions, 'MonitorCreationException')()


def test_MonitorQueryException():
    with pytest.raises(exceptions.MonitorQueryException):
        raise getattr(exceptions, 'MonitorQueryException')()


def test_MonitorUpdateException():
    with pytest.raises(exceptions.MonitorUpdateException):
        raise getattr(exceptions, 'MonitorUpdateException')()


def test_MonitorDeleteException():
    with pytest.raises(exceptions.MonitorDeleteException):
        raise getattr(exceptions, 'MonitorDeleteException')()


def test_NATCreationException():
    with pytest.raises(exceptions.NATCreationException):
        raise getattr(exceptions, 'NATCreationException')()


def test_NATQueryException():
    with pytest.raises(exceptions.NATQueryException):
        raise getattr(exceptions, 'NATQueryException')()


def test_NATUpdateException():
    with pytest.raises(exceptions.NATUpdateException):
        raise getattr(exceptions, 'NATUpdateException')()


def test_NATDeleteException():
    with pytest.raises(exceptions.NATDeleteException):
        raise getattr(exceptions, 'NATDeleteException')()


def test_PoolCreationException():
    with pytest.raises(exceptions.PoolCreationException):
        raise getattr(exceptions, 'PoolCreationException')()


def test_PoolQueryException():
    with pytest.raises(exceptions.PoolQueryException):
        raise getattr(exceptions, 'PoolQueryException')()


def test_PoolUpdateException():
    with pytest.raises(exceptions.PoolUpdateException):
        raise getattr(exceptions, 'PoolUpdateException')()


def test_PoolDeleteException():
    with pytest.raises(exceptions.PoolDeleteException):
        raise getattr(exceptions, 'PoolDeleteException')()


def test_RouteCreationException():
    with pytest.raises(exceptions.RouteCreationException):
        raise getattr(exceptions, 'RouteCreationException')()


def test_RouteQueryException():
    with pytest.raises(exceptions.RouteQueryException):
        raise getattr(exceptions, 'RouteQueryException')()


def test_RouteUpdateException():
    with pytest.raises(exceptions.RouteUpdateException):
        raise getattr(exceptions, 'RouteUpdateException')()


def test_RouteDeleteException():
    with pytest.raises(exceptions.RouteDeleteException):
        raise getattr(exceptions, 'RouteDeleteException')()


def test_RouteDomainCreationException():
    with pytest.raises(exceptions.RouteDomainCreationException):
        raise getattr(exceptions, 'RouteDomainCreationException')()


def test_RouteDomainQueryException():
    with pytest.raises(exceptions.RouteDomainQueryException):
        raise getattr(exceptions, 'RouteDomainQueryException')()


def test_RouteDomainUpdateException():
    with pytest.raises(exceptions.RouteDomainUpdateException):
        raise getattr(exceptions, 'RouteDomainUpdateException')()


def test_RouteDomainDeleteException():
    with pytest.raises(exceptions.RouteDomainDeleteException):
        raise getattr(exceptions, 'RouteDomainDeleteException')()


def test_RuleCreationException():
    with pytest.raises(exceptions.RuleCreationException):
        raise getattr(exceptions, 'RuleCreationException')()


def test_RuleQueryException():
    with pytest.raises(exceptions.RuleQueryException):
        raise getattr(exceptions, 'RuleQueryException')()


def test_RuleUpdateException():
    with pytest.raises(exceptions.RuleUpdateException):
        raise getattr(exceptions, 'RuleUpdateException')()


def test_RuleDeleteException():
    with pytest.raises(exceptions.RuleDeleteException):
        raise getattr(exceptions, 'RuleDeleteException')()


def test_SelfIPCreationException():
    with pytest.raises(exceptions.SelfIPCreationException):
        raise getattr(exceptions, 'SelfIPCreationException')()


def test_SelfIPQueryException():
    with pytest.raises(exceptions.SelfIPQueryException):
        raise getattr(exceptions, 'SelfIPQueryException')()


def test_SelfIPUpdateException():
    with pytest.raises(exceptions.SelfIPUpdateException):
        raise getattr(exceptions, 'SelfIPUpdateException')()


def test_SelfIPDeleteException():
    with pytest.raises(exceptions.SelfIPDeleteException):
        raise getattr(exceptions, 'SelfIPDeleteException')()


def test_SNATCreationException():
    with pytest.raises(exceptions.SNATCreationException):
        raise getattr(exceptions, 'SNATCreationException')()


def test_SNATQueryException():
    with pytest.raises(exceptions.SNATQueryException):
        raise getattr(exceptions, 'SNATQueryException')()


def test_SNATUpdateException():
    with pytest.raises(exceptions.SNATUpdateException):
        raise getattr(exceptions, 'SNATUpdateException')()


def test_SNATDeleteException():
    with pytest.raises(exceptions.SNATDeleteException):
        raise getattr(exceptions, 'SNATDeleteException')()


def test_SystemCreationException():
    with pytest.raises(exceptions.SystemCreationException):
        raise getattr(exceptions, 'SystemCreationException')()


def test_SystemQueryException():
    with pytest.raises(exceptions.SystemQueryException):
        raise getattr(exceptions, 'SystemQueryException')()


def test_SystemUpdateException():
    with pytest.raises(exceptions.SystemUpdateException):
        raise getattr(exceptions, 'SystemUpdateException')()


def test_SystemDeleteException():
    with pytest.raises(exceptions.SystemDeleteException):
        raise getattr(exceptions, 'SystemDeleteException')()


def test_VirtualServerCreationException():
    with pytest.raises(exceptions.VirtualServerCreationException):
        raise getattr(exceptions, 'VirtualServerCreationException')()


def test_VirtualServerQueryException():
    with pytest.raises(exceptions.VirtualServerQueryException):
        raise getattr(exceptions, 'VirtualServerQueryException')()


def test_VirtualServerUpdateException():
    with pytest.raises(exceptions.VirtualServerUpdateException):
        raise getattr(exceptions, 'VirtualServerUpdateException')()


def test_VirtualServerDeleteException():
    with pytest.raises(exceptions.VirtualServerDeleteException):
        raise getattr(exceptions, 'VirtualServerDeleteException')()


def test_VLANCreationException():
    with pytest.raises(exceptions.VLANCreationException):
        raise getattr(exceptions, 'VLANCreationException')()


def test_VLANQueryException():
    with pytest.raises(exceptions.VLANQueryException):
        raise getattr(exceptions, 'VLANQueryException')()


def test_VLANUpdateException():
    with pytest.raises(exceptions.VLANUpdateException):
        raise getattr(exceptions, 'VLANUpdateException')()


def test_VLANDeleteException():
    with pytest.raises(exceptions.VLANDeleteException):
        raise getattr(exceptions, 'VLANDeleteException')()


def test_VXLANCreationException():
    with pytest.raises(exceptions.VXLANCreationException):
        raise getattr(exceptions, 'VXLANCreationException')()


def test_VXLANQueryException():
    with pytest.raises(exceptions.VXLANQueryException):
        raise getattr(exceptions, 'VXLANQueryException')()


def test_VXLANUpdateException():
    with pytest.raises(exceptions.VXLANUpdateException):
        raise getattr(exceptions, 'VXLANUpdateException')()


def test_VXLANDeleteException():
    with pytest.raises(exceptions.VXLANDeleteException):
        raise getattr(exceptions, 'VXLANDeleteException')()


def test_BigIPNotLicensedForVcmp():
        with pytest.raises(exceptions.BigIPNotLicensedForVcmp):
            raise getattr(exceptions, 'BigIPNotLicensedForVcmp')()


if __name__ == '__main__':
    pdb.run('pytest %s' % (sys.argv[0]))
