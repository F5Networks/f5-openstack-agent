from oslo_log import log as logging
from openstackclient.i18n import _
from osc_lib.command import command
from osc_lib import utils
import six

LOG = logging.getLogger(__name__)


class CreateBigip(command.ShowOne):

    def get_parser(self, prog_name):
        parser = super(CreateBigip, self).get_parser(prog_name)
        parser.add_argument(
            '--user',
            metavar='<user>',
            default='neutron',
            choices=['neutron'],
            help=_('user that owns the credential (name or ID)'),
        )
        parser.add_argument(
            '--type',
            default='bigip',
            metavar='<type>',
            choices=['bigip'],
            help=_('New credential type:bigip'),
        )

        parser.add_argument(
            'project',
            metavar='<project>',
            help=_('Project which limits the scope of '
                   'the credential (name or ID)'),
        )
        parser.add_argument(
            'hostname',
            metavar='<hostname>',
            help=_('bigip hostname'),
        )
        return parser

    def take_action(self, parsed_args):
        """
        usage: f5agent bigip-create
        """
        LOG.info("parsed_args: {}".format(parsed_args))
        self.app.stdout.write('create a bigip \n')
        f5agent_client = self.app.client_manager.f5agent
        user_id = utils.find_resource(f5agent_client.users, parsed_args.user).id

        if parsed_args.project:
            project = utils.find_resource(f5agent_client.projects, parsed_args.project).id
        else:
            project = None

        data = {
            "data": parsed_args.hostname
        }
        credential = f5agent_client.credentials.create(
            user=user_id,
            type=parsed_args.type,
            blob=data,
            project=project)

        credential._info.pop('links')
        return zip(*sorted(six.iteritems(credential._info)))

