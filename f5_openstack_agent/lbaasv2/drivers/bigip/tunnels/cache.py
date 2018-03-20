"""A library for hosting a base cache class

This library hosts a cache base class for tunnels.  This cache base allows for
additional, shared functionalities between classes.
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
import os
import threading
import time

import f5_openstack_agent.lbaasv2.drivers.bigip.exceptions as f5_ex


class CacheError(f5_ex.F5AgentException):
    """An Exception that highlights the fact that a Cache has failed"""
    def __init__(self, message, *args, **kwargs):
        message = "{} (gc.garbage: {})".format(message, gc.garbage)


def lock(method):
    def lock_wrapper(cache, *args, **kwargs):
        """Places a lock on the instance of the object"""
        cache.acquire_lock()
        try:
            attempted_lock_acquire_time = time.time()
            cache.logger.debug(
                "Locked {} for {}".format(
                    cache.__class__.__name__, method.__name__))
            method_start_time = time.time()
            ret_val = method(cache, *args, **kwargs)
        except RuntimeError:
            cache.logger.exception("A lock-mechanism error has occurred!")
        finally:
            method_end_time = time.time()
            cache.release_lock()
            lock_end_time = time.time()
            cache.logger.debug(
                "Unlocked {} by {} method tool {} seconds lock {} "
                "seconds".format(
                    cache.__class__.__name__, method.__name__,
                    method_start_time - method_end_time,
                    attempted_lock_acquire_time - lock_end_time))
        return ret_val
    return lock_wrapper


class CacheBase(object):
    """A base class for all, standalone, cache objects

    This object hosts commonly referenced caching needs including locking,
    primarily, object-locking capabilities.

    Such locking mechanisms assume that the lock needs to be a thread lock
    ONLY and does not guarentee safty across multiple PID's.

    This object DOES NOT offer any with block support for locking mechanisms!
    It is assumed that the cache's API will lock the object if/when necessary
    for certain operations.

    Args:
        None
    Returns:
        None
    """
    def __init__(self):
        self.__mechanism = threading.Lock()
        self.__workers_waiting = 0
        self.__lock_acquired = None
        self.__workers_locks = threading.Condition(self.__mechanism)
        self.__my_pid = os.getpid()

    def acquire_lock(self):
        """Handles cache locking mechanisms for this object

        This method will take the method call with all of its args, lock the
        object using the threading library, exceute the method, then unlock
        the object and return the method-call's results.

        The caller assumes all liability in orchestrating locks appropriately.
        Thus, this method is not responsible for the enter/exit strategy of
        this object's locking mechanism.

        Deadlock Prevention:
            There are several arguments on how to handle deadlock prevention.
            The biggest taboo; however, is a constraint where objects under
            lock are modified, a catch that includes what is thrown captures
            then the exception within to-be locked code.  As such, a Cache
            SHOULD NEVER catch a RuntimeError or lower!

            Let me repeat: this branch of exceptions should not be caught
            anywhere within a Cache object instance!

        Args:
            None
        Returns:
            None
        Wrapping:
            It is assumed that the caller will wrap things appropriately to
            unlock this lock when appropriate.
        """
        if self.__lock_acquired == threading.current_thread():
            # perform lock-out safety... This SHOULD NOT happen!
            msg = str("Attempting to acquire the same lock as I already have "
                      "(thread-wise)")
            # self.logger.warning(msg)
            self.release_lock()
            raise RuntimeError(msg)
            # return
        my_pid = os.getpid()
        if self.__my_pid != os.getpid():
            self.logger.warning("Cache object does not support "
                                "multiprocessing (mypid: {}; create_pid: {})".
                                format(my_pid, self.__my_pid))
        with self.__mechanism:
            while self.__lock_acquired:
                self.__workers_waiting += 1
                self.__workers_locks.wait()
                self.__workers_waiting -= 1
            self.__lock_acquired = threading.current_thread()

    def release_lock(self):
        """Releases an afore-created lock

        Expected bahavior of deadlock-prevention code:
            It is expected, if a deadlock occurs, is a 2 layer exception.  One
            for when the deadlock is detected, and the second when the locking
            mechanism that originally existed attempted to unlock the
            mechanism.

        To prevent this from causing a troubleshooting taboo, there is a
        mechanism that will produce a Loggr.exception() to capture this
        information.
        """
        with self.__mechanism:
            my_thread = threading.current_thread()
            # lock sanity checking...
            if self.__lock_acquired is None:
                raise RuntimeError("We can't release a non-acquired lock!")
            elif not self.__lock_acquired:
                self.logger.error("Shying away from unlocking an "
                                  "unlocked-lock!")
            elif self.__lock_acquired != my_thread and self.__lock_acquired:
                raise RuntimeError(
                    "We can't release another's lock "
                    "(lock({}), thread({}))".format(
                        self.__lock_acquired, my_thread))
            self.__lock_acquired = None
            if self.__workers_waiting > 0:
                self.__workers_locks.notify()
