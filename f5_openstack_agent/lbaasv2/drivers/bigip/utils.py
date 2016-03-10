"""Utility classes and functions."""
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
from time import time
import uuid

from eventlet import greenthread
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
OBJ_PREFIX = 'uuid_'


def strip_domain_address(ip_address):
    # Strip domain from ip address
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
            service_queue = args[0].service_queue
            my_request_id = uuid.uuid4()

            service = None
            if len(args) > 0:
                last_arg = args[-1]
                if isinstance(last_arg, dict) and ('loadbalancer' in last_arg):
                    service = last_arg
            if 'service' in kwargs:
                service = kwargs['service']

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
    """Get index of request in request queue."""
    for request in request_queue:
        if request[0] == request_id:
            return request_queue.index(request)
