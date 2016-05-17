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

from f5.bigip import ManagementRoot
from f5_openstack_agent.lbaasv2.drivers.bigip import ssl_profile
from f5_openstack_agent.lbaasv2.drivers.bigip import barbican_cert

# from keystoneauth1 import identity
# from keystoneauth1 import session

class Config(object):
    def __init__(self):
        self.barbican_endpoint = "http://10.190.4.169:9311"
        self.barbican_project_id = 'FAKE_PROJECT'


def test_cert_manager():
    conf = Config()
    cert_payload = read_file('server.crt')
    key_payload = read_file('server.key')

    container_ref = create_container('server', cert_payload, key_payload, conf)

    cert_manager = barbican_cert.BarbicanCertManager(Config())
    cert = cert_manager.get_certificate(container_ref)


    print cert_payload
    assert cert == cert_payload

    key = cert_manager.get_private_key(container_ref)
    print key_payload
    assert key == key_payload

    bigip = ManagementRoot('10.190.7.108', 'admin', 'admin')
    ssl_profile.SSLProfileHelper.create_client_ssl_profile(
        bigip, 'server', cert, key)

def create_container(name, cert_payload, key_payload, conf):
    """
    auth = identity.v2.Password(auth_url='http://10.190.4.201:5000/v2.0',
                                username='barbican',
                                password='orange',
                                tenant_name='service')


    sess = session.Session(auth=auth)
    barbican = client.Client(session=sess)
    """
    barbican = client.Client(endpoint=conf.barbican_endpoint,
                             project_id=conf.barbican_project_id)
    secret_cert = barbican.secrets.create(name + '.crt', payload=cert_payload)
    secret_key = barbican.secrets.create(name + '.key', payload=key_payload)
    container = barbican.containers.create_certificate(name="server",
                                                       certificate=secret_cert,
                                                       private_key=secret_key)

    ref = container.store()
    assert ref.startswith("http")

    return ref


def read_file(file_name):
    file = open(file_name, 'rb')
    return file.read()



