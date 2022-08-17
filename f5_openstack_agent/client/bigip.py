# coding=utf-8
import os

import six

import json
from oslo_log import log as logging
from openstackclient.i18n import _
from osc_lib.command import command
from osc_lib import utils, exceptions

from clientmanager import make_client, IControlClient

LOG = logging.getLogger(__name__)

CREDENTIAL_USERNAME = 'neutron'
CREDENTIAL_TYPE = 'bigip'
INDENT = 4


class BipipCommand(command.ShowOne):
    def __init__(self, app, app_args):
        super(BipipCommand, self).__init__(app, app_args)
        self.f5agent_client = make_client()
        self.user_id = utils.find_resource(self.f5agent_client.users, CREDENTIAL_USERNAME).id
        self.project = utils.find_resource(self.f5agent_client.projects, os.environ['OS_PROJECT_NAME']).id

    def show_credential(self, credential):
        new_credential = utils.find_resource(self.f5agent_client.credentials, credential)
        LOG.debug("credential info: %s" % new_credential)
        new_credential._info.pop('links')
        return zip(*sorted(six.iteritems(new_credential._info)))

    def create_credential(self, blob):
        new_credential = self.f5agent_client.credentials.create(
            user=self.user_id,
            type=CREDENTIAL_TYPE,
            blob=json.dumps(blob, indent=INDENT),
            project=self.project)
        return new_credential

    def update_credential(self, credential, blob):
        self.f5agent_client.credentials.update(credential,
                                               user=self.user_id,
                                               type=CREDENTIAL_TYPE,
                                               blob=json.dumps(blob, indent=INDENT),
                                               project=self.project)


class CreateBigip(BipipCommand):
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
            '--id',
            metavar='<credential-id>',
            help=_('ID of credential(s) to delete'),
        )
        parser.add_argument(
            '--availability_zone',
            metavar='<availability_zone>',
            default=None,
            help=_('availability_zone which the agent is belong'),
        )
        parser.add_argument(
            '--icontrol_port',
            default="443",
            metavar='<icontrol_port>',
            help=_('port of to communicate with bigip'),
        )

        return parser

    def take_action(self, parsed_args):
        """
        usage: f5agent bigip-create project icontrol_hostname
        """
        icontrol_hostname, icontrol_username, icontrol_password, icontrol_port = parsed_args.icontrol_hostname, \
                                                                                 parsed_args.icontrol_username, \
                                                                                 parsed_args.icontrol_password, \
                                                                                 parsed_args.icontrol_port
        ic = IControlClient(icontrol_hostname, icontrol_username, icontrol_password, icontrol_port)

        if parsed_args.id:
            credential = utils.find_resource(self.f5agent_client.credentials, parsed_args.id)
            blob = json.loads(credential._info['blob'])
            blob["bigips"][icontrol_hostname] = ic.get_bigip_info()
            self.update_credential(parsed_args.id, blob)
            new_credential = utils.find_resource(self.f5agent_client.credentials, parsed_args.id)
        else:
            blob = {
                "admin_state_up": True,
                "availability_zone": parsed_args.availability_zone,
                "bigips": {
                    icontrol_hostname: ic.get_bigip_info()
                },
            }
            new_credential = self.create_credential(blob)

        LOG.debug("credential info: %s" % new_credential)
        new_credential._info.pop('links')
        return zip(*sorted(six.iteritems(new_credential._info)))


class DeleteBigip(BipipCommand):
    _description = _("Remove a existing bigip from an existing device group")

    def get_parser(self, prog_name):
        parser = super(DeleteBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<credential-id>',
            help=_('ID of credential(s) to delete'),
        )

        parser.add_argument(
            'icontrol_hostname',
            metavar='<icontrol_hostname>',
            help=_('icontrol_hostname of BIG-IP device'),
        )
        return parser

    def take_action(self, parsed_args):
        credential = utils.find_resource(self.f5agent_client.credentials, parsed_args.id)
        blob = json.loads(credential._info['blob'])
        bigips = blob.get("bigips", None)

        icontrol_hostname = parsed_args.icontrol_hostname
        if icontrol_hostname not in bigips:
            msg = (_("bigip: %(hostname)s not in credential") % {'hostname': icontrol_hostname})
            raise exceptions.CommandError(msg)
        del bigips[icontrol_hostname]
        blob['bigips'] = bigips

        self.update_credential(parsed_args.id, blob)
        return self.show_credential(parsed_args.id)


class UpdateBigip(BipipCommand):
    _description = _("Modify the admin properties of an existing device group")

    def get_parser(self, prog_name):
        parser = super(UpdateBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<credential-id>',
            help=_('ID of credential(s) to delete'),
        )
        parser.add_argument(
            '--admin-state-down',
            dest='admin_state',
            action='store_false',
            help=_('Set admin state up of the bigip group to false.'))

        parser.add_argument(
            '--availability_zone',
            metavar='<availability_zone>',
            default=None,
            help=_('availability_zone which the agent is belong'),
        )

        return parser

    def take_action(self, parsed_args):
        credential = utils.find_resource(self.f5agent_client.credentials, parsed_args.id)
        blob = json.loads(credential._info['blob'])
        blob["admin_state_up"] = parsed_args.admin_state if parsed_args is not None else True
        if parsed_args.availability_zone:
            blob["availability_zone"] = parsed_args.availability_zone

        self.update_credential(parsed_args.id, blob)
        return self.show_credential(parsed_args.id)


class RefreshBigip(BipipCommand):
    _description = _("Refresh the device properties of an existing bigip in an existing device group")

    def get_parser(self, prog_name):
        parser = super(RefreshBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<credential-id>',
            help=_('ID of credential(s) to delete'),
        )
        parser.add_argument(
            'icontrol_hostname',
            metavar='<icontrol_hostname>',
            help=_('icontrol_hostname of BIG-IP device'),
        )
        return parser

    def take_action(self, parsed_args):
        credential = utils.find_resource(self.f5agent_client.credentials, parsed_args.id)
        blob = json.loads(credential._info['blob'])
        bigips = blob.get("bigips", None)
        icontrol_hostname = parsed_args.icontrol_hostname
        if icontrol_hostname not in bigips:
            msg = (_("bigip: %(hostname)s not in credential") % {'hostname': icontrol_hostname})
            raise exceptions.CommandError(msg)

        bigip_info = bigips[icontrol_hostname]
        ic = IControlClient(icontrol_hostname, bigip_info['username'], bigip_info['password'], bigip_info['port'])
        blob["bigips"][icontrol_hostname] = ic.get_bigip_info()
        self.update_credential(parsed_args.id, blob)

        return self.show_credential(parsed_args.id)
