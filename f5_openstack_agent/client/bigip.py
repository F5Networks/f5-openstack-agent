from oslo_log import log as logging
from openstackclient.i18n import _
from osc_lib.command import command

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
            'data',
            metavar='<data>',
            help=_('New bigip data'),
        )
        return parser

    def take_action(self, parsed_args):
        """
        usage: f5agent bigip-create
        """
        LOG.info("parsed_args: {}".format(parsed_args))
        self.app.stdout.write('create a bigip \n')
        columns = ('user',
                   'type',
                   'project',
                   'data',
                   )
        data = (parsed_args.user,
                parsed_args.type,
                parsed_args.project,
                parsed_args.data,
                )
        return columns, data
