# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
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


import copy
import eventlet
from functools import wraps

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class On(object):
    def __init__(self, bigips):
        self.bigips = bigips
        self.failures = []
        self.exec_pool = eventlet.GreenPool()

    def __call__(self, func):
        '''The wrapped function prototype should be:

        :param func: def func(*args, service=<service>) -> None
        '''

        self.func_name = func.__name__

        @wraps(func)
        # @timer.timeit # testing bigip concurrent operation effect.
        def wrapped_function(*args, **kwargs):
            if 'service' not in kwargs:
                raise Exception("missing 'service' for %s" % func.__name__)

            def _func(*a, **kw):
                try:
                    func(*a, **kw)
                except Exception as ex:
                    self.failures.append(ex)

            for bigip in self.bigips:
                cargs = copy.deepcopy(args)
                ckwargs = copy.deepcopy(kwargs)
                ckwargs['service']['bigips'] = [bigip]
                self.exec_pool.spawn(_func, *cargs, **ckwargs)

            self.exec_pool.waitall()
            self.notify()
        return wrapped_function

    def notify(self):
        if len(self.failures):
            for failure in self.failures:
                LOG.exception("Fail to %s Exception: %s",
                              (self.func_name, failure.message))
                print("Fail to %s Exception: %s" %
                      (self.func_name, failure.message))
            raise self.failures[0]
