# coding=utf-8
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

from barbicanclient import client

from keystoneauth1 import identity
from keystoneauth1 import session
from oslo_log import log as logging

from f5_openstack_agent.lbaasv2.drivers.bigip import cert_manager

LOG = logging.getLogger(__name__)


class InvalidBarbicanConfig(Exception):
    pass


class BarbicanCertManager(cert_manager.CertManagerBase):

    def __init__(self, conf):
        super(BarbicanCertManager, self).__init__()

        if not conf:
            raise InvalidBarbicanConfig

        auth = ""
        if hasattr(conf, "auth_version"):
            if conf.auth_version == "keystone_v2":
                auth = identity.v2.Password(
                    username=conf.keystone_username,
                    password=conf.keystone_password,
                    tenant_name=conf.keystone_tenant_name,
                    auth_url=conf.keystone_auth_url)
            elif conf.barbican_auth_version == "keystone_v3":
                auth = identity.v3.Password(
                    username=conf.keystone_username,
                    user_domain_name=conf.keystone_user_domain_name,
                    password=conf.keystone_password,
                    project_name=conf.keystone_project_name,
                    auth_url=conf.keystone_auth_url)

        if auth:
            sess = session.Session(auth=auth)
            self.barbican = client.Client(session=sess)
            LOG.debug("BarbicanCertManager: using %s authentication" %
                      conf.auth_version)
        else:
            if hasattr(conf, "barbican_endpoint"):
                endpoint = conf.barbican_endpoint
            else:
                msg = "A Barbican endpoint must be " \
                      "defined to use Barbican in no-auth mode."
                LOG.error(msg)
                raise InvalidBarbicanConfig(msg)

            if hasattr(conf, "barbican_project_id"):
                project_id = conf.barbican_project_id
            else:
                msg = "A Barbican project_id must be " \
                      "defined to use Barbican in no-auth mode."
                LOG.error(msg)
                raise InvalidBarbicanConfig(msg)

            self.barbican = client.Client(endpoint=endpoint,
                                          project_id=project_id)
            LOG.debug("BarbicanCertManager: using no-auth mode with endpooint "
                      "%s and project-id %s." % (endpoint, project_id))

    def get_certificate(self, container_ref):
        container = self.barbican.containers.get(container_ref)
        return container.certificate.payload

    def get_private_key(self, container_ref):
        container = self.barbican.containers.get(container_ref)
        return container.private_key.payload

    def get_name(self, container_ref):
        container = self.barbican.containers.get(container_ref)
        return container.name
