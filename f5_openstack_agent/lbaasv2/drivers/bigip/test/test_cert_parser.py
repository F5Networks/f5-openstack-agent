# coding=utf-8
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

from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from f5_openstack_agent.lbaasv2.drivers.bigip.test.certs_sample import \
    samples
from f5_openstack_agent.utils.cert_parser import get_intermediates_pems

import pytest


class TestTLSCertParser(object):

    def test_get_intermediates_pem_chain(self):
        intermediates = [c for c in
                         get_intermediates_pems(samples.X509_IMDS)]
        assert set(intermediates) == set(samples.X509_IMDS_LIST)

    def test_get_intermediates_pkcs7_pem(self):
        intermediates = [c for c in
                         get_intermediates_pems(samples.PKCS7_PEM)]
        assert set(intermediates) == set(samples.X509_IMDS_LIST)

    def test_get_intermediates_pkcs7_pem_bad(self):
        intermeidates = get_intermediates_pems(samples.BAD_PKCS7_PEM)

        with pytest.raises(f5_ex.UnreadableCert):
            list(intermeidates)

    def test_get_intermediates_pkcs7_der(self):
        intermediates = [c for c in
                         get_intermediates_pems(samples.PKCS7_DER)]
        assert set(intermediates) == set(samples.X509_IMDS_LIST)

    def test_get_intermediates_pkcs7_der_bad(self):
        intermeidates = get_intermediates_pems(samples.BAD_PKCS7_DER)

        with pytest.raises(f5_ex.UnreadableCert):
            list(intermeidates)
