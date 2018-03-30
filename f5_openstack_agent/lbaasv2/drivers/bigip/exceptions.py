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

import errno
import inspect
import logging
import os
import oslo_i18n
from oslo_utils import excutils
import re
import six
import sys
import syslog
import traceback


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


class NetworkNotReady(F5AgentException):
    pass


class InvalidNetworkType(F5AgentException):
    pass


class InvalidNetworkDefinition(F5AgentException):
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


class NodeDeleteException(F5AgentException):
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


class NoActionFoundForPolicy(F5AgentException):
    pass


class PolicyHasNoRules(F5AgentException):
    pass


class L7PolicyCreationException(F5AgentException):
    pass


class L7PolicyQueryException(F5AgentException):
    pass


class L7PolicyUpdateException(F5AgentException):
    pass


class L7PolicyDeleteException(F5AgentException):
    pass


class esdJSONFileEmptyException(F5AgentException):
    pass


class esdJSONFileInvalidException(F5AgentException):
    pass


class F5MissingDependencies(F5AgentException):
    default_msg = "%s cannot start due to missing dependency" % \
        str(sys.argv[0])
    message_format = "(%d) %s: %s [%s; line:%s]"
    default_errno = errno.ENOSYS
    default_project = 'neutron'
    default_name = 'f5-oslbaasv2-agent'

    def __init__(self, *args, **kargs):
        self.__set_message(args, kargs)
        super(F5MissingDependencies, self).__init__(self.message)
        self.__logger()
        self.__log_error()
        self.__check_debug()

    def __check_debug(self):
        print("__check_debug")
        debug = False
        for item in sys.argv:
            if 'f5-openstack-agent.ini' in item:
                with open(item, 'r') as fh:
                    line = fh.readline()
                    print('line', line)
                    debug_re = \
                        re.compile('debug\s*=\s*([Tt]rue|[Ff]alse|[01])')
                    while line:
                        match = debug_re.search(line)
                        if match:  # there should only be one!
                            if re.search('[tT]|1', match.group(1)):
                                debug = True
                            break
                        line = fh.readline()
        if debug:
            # our sys.exc_info queue should still be pointing at our ImportE
            traceback.print_exc()

    def __get_mod(self):
        frame = self.frame
        mod = "f5_openstack_agent.lbaasv2.drivers.bigip."
        mod = mod + os.path.basename(frame.filename)
        mod = mod.replace('.py', '')
        return mod

    def __logger(self):
        try:
            self._logger = \
                logging.getLogger('%s' % (self.__get_mod()))
            fh = \
                logging.FileHandler("/var/log/%s/%s.log" %
                                    (self.default_project, self.default_name))
            fh.setLevel(logging.DEBUG)
            self._logger.addHandler(fh)
        except IOError:
            self._logger = None

    def __log_error(self):
        if self._logger:
            self._logger.fatal(self.message)
        else:
            syslog.syslog(syslog.LOG_CRIT, self.message)

    def __set_message(self, args, kargs):
        details = ', '.join(map(str, args))
        errno = kargs['errno'] if 'errno' in kargs and kargs['errno'] else \
            self.default_errno
        self.errno = errno
        message = kargs['message'] if 'message' in kargs and kargs['message'] \
            else self.default_msg
        exception = ''
        if 'frame' in kargs and kargs['frame']:
            frame = kargs['frame']
        else:
            my_frames = inspect.getouterframes(inspect.currentframe())[2]
            frame = inspect.getframeinfo(my_frames[0])
        if 'exception' in kargs and kargs['exception']:
            message = kargs['exception']
        elif details:
            exception = details
        self.frame = frame
        self.message = self.message_format % (errno, message, exception,
                                              frame.filename, frame.lineno)


class RouteDomainCacheMiss(F5AgentException):
    pass


class F5NeutronException(F5AgentException):
    translators = oslo_i18n.TranslatorFactory(domain="exceptions")
    message = translators.primary("An unknown exception occurred.")

    def __init__(self, **kwargs):
        try:
            super(F5NeutronException, self).__init__(self.message % kwargs)
            self.msg = self.message % kwargs
        except F5AgentException:
            with excutils.save_and_reraise_exception() as ctxt:
                if not self.use_fatal_exceptions():
                    ctxt.reraise = False
                    # at least get the core message out if something happened
                    super(F5NeutronException, self).__init__(self.message)

    if six.PY2:
        def __unicode__(self):
            return unicode(self.msg)

    def __str__(self):
        return self.msg

    def use_fatal_exceptions(self):
        return False


class F5InvalidConfigurationOption(F5AgentException):
    translators = oslo_i18n.TranslatorFactory(domain="exceptions")
    message = translators.primary(
        "An invalid value was provided for %(opt_name)s: "
        "%(opt_value)s.")
