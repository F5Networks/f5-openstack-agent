# Copyright 2014 F5 Networks Inc.
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


class F5AgentException(Exception):
    pass


class MinorVersionValidateFailed(F5AgentException):
    pass


class MajorVersionValidateFailed(F5AgentException):
    pass


class ProvisioningExtraMBValidateFailed(F5AgentException):
    pass


class BigIPDeviceLockAcquireFailed(F5AgentException):
    pass


class BigIPClusterInvalidHA(F5AgentException):
    pass


class BigIPClusterSyncFailure(F5AgentException):
    pass


class BigIPClusterPeerAddFailure(F5AgentException):
    pass


class BigIPClusterConfigSaveFailure(F5AgentException):
    pass


class UnknownMonitorType(F5AgentException):
    pass


class MissingVTEPAddress(F5AgentException):
    pass


class MissingNetwork(F5AgentException):
    pass


class InvalidNetworkType(F5AgentException):
    pass


class StaticARPCreationException(F5AgentException):
    pass


class StaticARPQueryException(F5AgentException):
    pass


class StaticARPDeleteException(F5AgentException):
    pass


class ClusterCreationException(F5AgentException):
    pass


class ClusterUpdateException(F5AgentException):
    pass


class ClusterQueryException(F5AgentException):
    pass


class ClusterDeleteException(F5AgentException):
    pass


class DeviceCreationException(F5AgentException):
    pass


class DeviceUpdateException(F5AgentException):
    pass


class DeviceQueryException(F5AgentException):
    pass


class DeviceDeleteException(F5AgentException):
    pass


class InterfaceQueryException(F5AgentException):
    pass


class IAppCreationException(F5AgentException):
    pass


class IAppQueryException(F5AgentException):
    pass


class IAppUpdateException(F5AgentException):
    pass


class IAppDeleteException(F5AgentException):
    pass


class L2GRETunnelCreationException(F5AgentException):
    pass


class L2GRETunnelQueryException(F5AgentException):
    pass


class L2GRETunnelUpdateException(F5AgentException):
    pass


class L2GRETunnelDeleteException(F5AgentException):
    pass


class MemberCreationException(F5AgentException):
    pass


class MemberQueryException(F5AgentException):
    pass


class MemberUpdateException(F5AgentException):
    pass


class MemberDeleteException(F5AgentException):
    pass


class MonitorCreationException(F5AgentException):
    pass


class MonitorQueryException(F5AgentException):
    pass


class MonitorUpdateException(F5AgentException):
    pass


class MonitorDeleteException(F5AgentException):
    pass


class NATCreationException(F5AgentException):
    pass


class NATQueryException(F5AgentException):
    pass


class NATUpdateException(F5AgentException):
    pass


class NATDeleteException(F5AgentException):
    pass


class PoolCreationException(F5AgentException):
    pass


class PoolQueryException(F5AgentException):
    pass


class PoolUpdateException(F5AgentException):
    pass


class PoolDeleteException(F5AgentException):
    pass


class RouteCreationException(F5AgentException):
    pass


class RouteQueryException(F5AgentException):
    pass


class RouteUpdateException(F5AgentException):
    pass


class RouteDeleteException(F5AgentException):
    pass


class RouteDomainCreationException(F5AgentException):
    pass


class RouteDomainQueryException(F5AgentException):
    pass


class RouteDomainUpdateException(F5AgentException):
    pass


class RouteDomainDeleteException(F5AgentException):
    pass


class RuleCreationException(F5AgentException):
    pass


class RuleQueryException(F5AgentException):
    pass


class RuleUpdateException(F5AgentException):
    pass


class RuleDeleteException(F5AgentException):
    pass


class SelfIPCreationException(F5AgentException):
    pass


class SelfIPQueryException(F5AgentException):
    pass


class SelfIPUpdateException(F5AgentException):
    pass


class SelfIPDeleteException(F5AgentException):
    pass


class SNATCreationException(F5AgentException):
    pass


class SNATQueryException(F5AgentException):
    pass


class SNATUpdateException(F5AgentException):
    pass


class SNATDeleteException(F5AgentException):
    pass


class SystemCreationException(F5AgentException):
    pass


class SystemQueryException(F5AgentException):
    pass


class SystemUpdateException(F5AgentException):
    pass


class SystemDeleteException(F5AgentException):
    pass


class VirtualServerCreationException(F5AgentException):
    pass


class VirtualServerQueryException(F5AgentException):
    pass


class VirtualServerUpdateException(F5AgentException):
    pass


class VirtualServerDeleteException(F5AgentException):
    pass


class VLANCreationException(F5AgentException):
    pass


class VLANQueryException(F5AgentException):
    pass


class VLANUpdateException(F5AgentException):
    pass


class VLANDeleteException(F5AgentException):
    pass


class VXLANCreationException(F5AgentException):
    pass


class VXLANQueryException(F5AgentException):
    pass


class VXLANUpdateException(F5AgentException):
    pass


class VXLANDeleteException(F5AgentException):
    pass


class BigIPNotLicensedForVcmp(F5AgentException):
    pass
