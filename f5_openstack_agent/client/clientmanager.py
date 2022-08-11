import os

from oslo_log import log as logging
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client

LOG = logging.getLogger(__name__)


def build_session():
    auth_url = os.environ['OS_AUTH_URL']
    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    project_name = os.environ['OS_PROJECT_NAME']
    user_domain_name = os.environ.get('OS_USER_DOMAIN_NAME', None)
    project_domain_name = os.environ.get('OS_PROJECT_DOMAIN_NAME', None)
    LOG.debug("f5agent session,auth_url: %s, username: %s, password: %s, project_name: %s, user_domain_name: %s, "
              "project_domain_name: %s" % (auth_url, username, password, project_name, user_domain_name,
                                           project_domain_name))
    auth = v3.Password(auth_url=auth_url, username=username, password=password, project_name=project_name,
                       user_domain_name=user_domain_name, project_domain_name=project_domain_name)

    sess = session.Session(auth=auth)
    return sess


def make_client():
    return client.Client(session=build_session())
