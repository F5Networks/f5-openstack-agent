import os

from oslo_log import log as logging
from openstackclient.i18n import _
from osc_lib.command import command
from osc_lib import utils
import six

from clientmanager import make_client

LOG = logging.getLogger(__name__)


class CreateBigip(command.ShowOne):

    def get_parser(self, prog_name):
        parser = super(CreateBigip, self).get_parser(prog_name)

        parser.add_argument(
            'project',
            metavar='<project>',
            help=_('Project which bigip device belong to'),
        )
        parser.add_argument(
            'icontrol_hostname',
            metavar='<icontrol_hostname>',
            help=_('bigip device icontrol_hostname'),
        )
        return parser

    def take_action(self, parsed_args):
        """
        usage: f5agent bigip-create
        """
        LOG.debug("parsed_args: {}".format(parsed_args))
        f5agent_client = make_client()

        username = 'neutron'
        user_id = utils.find_resource(f5agent_client.users, username).id
        project = utils.find_resource(f5agent_client.projects, parsed_args.project).id

        credential_type = "bigip"
        data = {
            "data": parsed_args.icontrol_hostname
        }
        credential = f5agent_client.credentials.create(
            user=user_id,
            type=credential_type,
            blob=data,
            project=project)

        LOG.debug("credential info: %s" % credential)
        credential._info.pop('links')
        return zip(*sorted(six.iteritems(credential._info)))
