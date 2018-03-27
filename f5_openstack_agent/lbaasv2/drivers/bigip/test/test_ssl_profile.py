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

from f5_openstack_agent.lbaasv2.drivers.bigip.ssl_profile import \
    SSLProfileError
from f5_openstack_agent.lbaasv2.drivers.bigip.ssl_profile import \
    SSLProfileHelper


import mock
import pytest


class TestSSLProfileHelper(object):
    def test_get_ssl_profile_count(self):
        bigip = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.get_collection =\
            mock.MagicMock(return_value=[1, 2, 3, 4])
        assert(SSLProfileHelper.get_client_ssl_profile_count(bigip) == 4)

    def test_create_client_ssl_profile_exists(self):
        bigip = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl =\
            mock.MagicMock(return_value=True)
        rv = SSLProfileHelper.create_client_ssl_profile(
            bigip, 'testprofile', 'testcert', 'testkey')
        assert(rv is None)

    def test_create_client_ssl_profile_parent_none(self):
        bigip = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl.exists.return_value = False
        SSLProfileHelper.create_client_ssl_profile(
            bigip, 'testprofile', 'testcert', 'testkey', parent_profile=None)
        bigip.tm.ltm.profile.client_ssls.client_ssl.create.assert_called_with(
            name='testprofile',
            partition='Common',
            certKeyChain=[
                {'name': 'testprofile',
                 'cert': '/Common/testprofile.crt',
                 'key': '/Common/testprofile.key'}
            ],
            sniDefault=False,
            defaultsFrom=None,
        )

    def exists_parent(self, *args, **kwargs):
        name = kwargs.get('name', '')
        if name.startswith('parent'):
            return True
        else:
            return False

    def test_create_client_ssl_profile_parent_not_exist(self):
        bigip = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl.exists.return_value = False
        SSLProfileHelper.create_client_ssl_profile(
            bigip, 'testprofile', 'testcert', 'testkey',
            parent_profile="testparentprofile"
        )
        bigip.tm.ltm.profile.client_ssls.client_ssl.create.assert_called_with(
            name='testprofile',
            partition='Common',
            certKeyChain=[
                {'name': 'testprofile',
                 'cert': '/Common/testprofile.crt',
                 'key': '/Common/testprofile.key'}
            ],
            sniDefault=False,
            defaultsFrom=None,
        )

    def test_create_client_ssl_profile_parent(self):
        bigip = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl.exists.side_effect =\
            self.exists_parent
        SSLProfileHelper.create_client_ssl_profile(
            bigip, 'testprofile', 'testcert', 'testkey',
            parent_profile="parentprofile"
        )
        bigip.tm.ltm.profile.client_ssls.client_ssl.create.assert_called_with(
            name='testprofile',
            partition='Common',
            certKeyChain=[
                {'name': 'testprofile',
                 'cert': '/Common/testprofile.crt',
                 'key': '/Common/testprofile.key'}
            ],
            sniDefault=False,
            defaultsFrom='parentprofile',
        )

    def test_create_client_ssl_profile_raises(self):
        err = Exception()
        bigip = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl = mock.MagicMock()
        bigip.tm.ltm.profile.client_ssls.client_ssl.exists.return_value = False
        bigip.tm.ltm.profile.client_ssls.client_ssl.create =\
            mock.MagicMock(side_effect=err)
        with pytest.raises(SSLProfileError):
            SSLProfileHelper.create_client_ssl_profile(
                bigip, 'testprofile', 'testcert', 'testkey',
                parent_profile="parentprofile"
            )
