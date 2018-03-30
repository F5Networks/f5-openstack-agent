"""A library for hosting a base cache class

This library hosts a cache base class for tunnels.  This cache base allows for
additional, shared functionalities between classes.
"""
# Copyright (c) 2018, F5 Networks, Inc.
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

import gc

import f5_openstack_agent.lbaasv2.drivers.bigip.exceptions as f5_ex


class CacheError(f5_ex.F5AgentException):
    """An Exception that highlights the fact that a Cache has failed"""
    def __init__(self, message, *args, **kwargs):
        message = "{} (gc.garbage: {})".format(message, gc.garbage)


class CacheBase(object):
    """A base class for all, standalone, cache objects

    Args:
        None
    Returns:
        None
    """
    pass
