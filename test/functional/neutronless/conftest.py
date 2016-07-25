# Copyright 2016 F5 Networks Inc.
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

import logging
import pytest

from f5.utils.testutils.registrytools import register_device
from f5_os_test.order_utils import AGENT_LB_DEL_ORDER
from f5_os_test.order_utils import order_by_weights
from icontrol.exceptions import iControlUnexpectedHTTPError


@pytest.fixture
def setup_neutronless_test(request, bigip):
    pretest_snapshot = frozenset(register_device(bigip))

    def remove_test_created_elements():
        for t in bigip.tm.net.fdb.tunnels.get_collection():
            if t.name != 'http-tunnel' and t.name != 'socks-tunnel':
                t.update(records=[])
        posttest_registry = register_device(bigip)
        created = frozenset(posttest_registry) - pretest_snapshot
        ordered = order_by_weights(created, AGENT_LB_DEL_ORDER)
        for selfLink in ordered:
            try:
                logging.info(selfLink)
                posttest_registry[selfLink].delete()
            except iControlUnexpectedHTTPError as exc:
                if exc.response.status_code == 404:
                    logging.debug(exc.response.status_code)
                else:
                    raise

    request.addfinalizer(remove_test_created_elements)
