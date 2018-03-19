"""A decorator library for tunnels/

This is a decorator library, and as such, all method within this library are
decorator methods that either add wrappers or handle specific cases for method
manipulations.
"""
# Copyright 2018 F5 Networks Inc.
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
import socket
import sys
import weakref

from requests import HTTPError

import oslo_log.log as logging

LOG = logging.getLogger(__name__)


def weakref_handle(method):
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except weakref.ReferenceError:
            LOG.debug("Could not perform {!s} on ({}, {}) due to the tunnel "
                      "being deleted from the cache.  The agent will now "
                      "attempt to continue with the remaining tunnels to "
                      "be updated".format(method, args, kwargs))
            gc.collect()
            remaining = gc.garbage()
            if remaining:
                LOG.debug("garbage({})".format(remaining))
            return None
    return wrapper


def http_error(*args, **exc_specs):
    """Http error handler function that adds a http_decorator to a method

    This decorator is a exception handler that can be partially customized for
    the caller to handle requests.HTTPError messages ONLY.

    Format for caller to follow:
        @http_error(<error level>={<status_code>: <message>})
    Where <error level> is a valid Logger log level.
    Example:
        @http_error(error={404: "Bad arguments", 409: "Not found!"})
    More than one error level can be given in an expression.

    Know that any 'non-given' status code errors will simply be raised.

    Args:
        error_level - This should be a valid log-producing attribute of
            logging.Logger and

    """
    def http_error_decorator(method, *dargs, **dkwargs):
        """A deorator function that adds the http_error_wrapper"""
        def http_error_wrapper(instance, *wargs, **wkwargs):
            """The wrapper that handles the http_error handler's claim"""
            try:
                return method(instance, *wargs, **wkwargs)
            except HTTPError as error:
                for level in exc_specs:
                    if level not in dir(LOG):
                        continue
                    messages = exc_specs.get(level, '')
                    if not messages:
                        continue
                    status_code = error.response.status_code
                    message = messages.get(
                        status_code, messages.get(
                            str(status_code), ''))
                    if not message:
                        raise  # we've gotten to our status error's specifics
                    msg_type = getattr(LOG, level)
                    if wargs:
                        message = "{} (args: {})".format(message, args)
                    if wkwargs:
                        message = "{} (kwargs: {})".format(message, wkwargs)
                    message = str(
                        "From [{m.co_filename}:{m.co_name}:"
                        "{m.co_firstlineno}] {}").format(
                            message, m=method.func_code)
                    msg_type(message)
                    sys.exc_clear()
                    break
                else:
                    raise
        return http_error_wrapper
    return http_error_decorator


def not_none(method):
    """A decorator function that adds the not_none wrapper"""
    def not_none_wrapper(inst, value):
        """A wrapper that checks the input value and raises TypeError if None

        This will check the instance of the provided argument to the method
        under wrap before the method is called and raise TypeError if the
        value given is NoneType.
        """
        if isinstance(value, type(None)):
            raise TypeError("None sent to {}".format(method))
        return method(inst, value)
    return not_none_wrapper


def ip_address(method):
    """A decorator function that adds the is_ip_address_wrapper"""
    def is_ip_address_wrapper(inst, value, force=False):
        """Checks the method under wrap's value to validate IP Address

        This wrapper will check validity of the IP Address in the value given
        to the method under wrap.  If it is not a valid IP Address, then a
        TypeError is raised.

        Optional:
            Caller may provide a force kwarg.  If true, then this decorator
            will ignore what tyep of object is passed.
        """
        if not force:
            try:
                socket.inet_aton(value)
            except socket.error:
                raise TypeError(
                    "method {} is expecting an IP address!".format(method))
        return method(inst, value)
    return is_ip_address_wrapper


def add_logger(method):
    """Decorator that adds an instance-specific logger for troubleshooting"""
    def add_logger_wrapper(inst, *args, **kwargs):
        """Wrapper that wraps method with a logger of its own

        This method is handy for troubleshooting memory issues when comparing
        log instances across multiple potential instances of an object within
        a cache.
        """
        my_id = hex(id(inst))
        name = "{}_{}".format(inst.__class__.__name__, my_id)
        inst.logger = logging.getLogger(name)
        inst.logger.debug("Creating object ({}, {})".format(args, kwargs))
        return method(inst, *args, **kwargs)
    return add_logger_wrapper


def only_one(method, *dargs, **dkwargs):
    """Decorator that only allows one set value for an attr"""
    def only_one_wrapper(inst, *args, **kwargs):
        """Wrapper that, for a carrier object, only allows one set time

        This wrapper will raise if the decorated set property method has
        already been set with a value.  This forces only one value ever for
        a particular attribute for an object.

        This allows for better readability and distinction for gets and sets
        while still having the ability to have an attribute immutable.
        """
        class_name = inst.__class__.__name__
        method_name = method.__class__.__name__
        attr_name = method_name.replace('_set_', '')
        if hasattr(inst, "_{}__{}".format(class_name, attr_name)):
            raise TypeError(
                "{} class can only set {} once".format(class_name, attr_name))
        method(inst, *args, **kwargs)
    return only_one_wrapper
