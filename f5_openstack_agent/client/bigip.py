# coding=utf-8
import os

import six

import json
from oslo_log import log as logging
from openstackclient.i18n import _
from osc_lib.command import command
from osc_lib import utils

from clientmanager import make_client, IControlClient

LOG = logging.getLogger(__name__)

CREDENTIAL_USERNAME = 'neutron'
CREDENTIAL_TYPE = 'bigip'


class CreateBigip(command.ShowOne):
    _description = _("Create new bigip credential")

    def get_parser(self, prog_name):
        parser = super(CreateBigip, self).get_parser(prog_name)

        parser.add_argument(
            'icontrol_hostname',
            metavar='<icontrol_hostname>',
            help=_('icontrol_hostname of BIG-IP device'),
        )
        parser.add_argument(
            'icontrol_username',
            metavar='<icontrol_username>',
            help=_('icontrol_username of BIG-IP device'),
        )
        parser.add_argument(
            'icontrol_password',
            metavar='<icontrol_password>',
            help=_('password of icontrol_hostname'),
        )
        parser.add_argument(
            '--credential',
            metavar='<credential-id>',
            help=_('ID of credential(s) to delete'),
        )
        parser.add_argument(
            '--icontrol_port',
            default="443",
            metavar='<icontrol_port to communicate with bigip>',
            help=_('port of '),
        )

        return parser

    def take_action(self, parsed_args):
        """
        usage: f5agent bigip-create project icontrol_hostname
        """
        LOG.debug("parsed_args: {}".format(parsed_args))

        # TODO(seven): MAKE session from os_client_config
        f5agent_client = make_client()
        user_id = utils.find_resource(f5agent_client.users, CREDENTIAL_USERNAME).id
        # TODO(seven): get project name from config
        project = utils.find_resource(f5agent_client.projects, os.environ['OS_PROJECT_NAME']).id

        icontrol_hostname, icontrol_username, icontrol_password, icontrol_port = parsed_args.icontrol_hostname, \
                                                                                 parsed_args.icontrol_username, \
                                                                                 parsed_args.icontrol_password, \
                                                                                 parsed_args.icontrol_port
        ic = IControlClient(icontrol_hostname, icontrol_username, icontrol_password, icontrol_port)

        if parsed_args.credential:
            # 在已有credential中添加设备信息
            #
            pass
        else:
            # create new credential
            blob = {
                "bigips": {
                    icontrol_hostname: ic.get_bigip_info()
                },
            }

            credential = f5agent_client.credentials.create(
                user=user_id,
                type=CREDENTIAL_TYPE,
                blob=json.dumps(blob),
                project=project)

            LOG.debug("credential info: %s" % credential)
            credential._info.pop('links')
            return zip(*sorted(six.iteritems(credential._info)))
