from osc_lib.clientmanager import ClientCache, ClientManager
from osc_lib import utils
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


API_NAME = 'f5agent'
API_VERSIONS = {
    '3': 'keystoneclient.v3.client.Client',
}


def make_client(instance):
    """Returns an identity service client."""
    f5agent_client = utils.get_client_class(
        api_name=API_NAME,
        version=instance._api_version[API_NAME],
        version_map=API_VERSIONS
    )
    LOG.debug('Instantiating f5agent client: %s', f5agent_client)

    kwargs = utils.build_kwargs_dict('interface', instance.interface)

    client = f5agent_client(
        session=instance.session,
        region_name=instance.region_name,
        **kwargs
    )
    return client


setattr(ClientManager, API_NAME, ClientCache(make_client))
