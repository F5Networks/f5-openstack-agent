# coding=utf-8
import json
import os
import uuid

from openstackclient.i18n import _
from osc_lib import exceptions
from osc_lib.command import command
from oslo_log import log as logging

from f5_openstack_agent.client.clientmanager import IControlClient

LOG = logging.getLogger(__name__)

INDENT = 4
INVENTORY_PATH = '/etc/neutron/bigip_inventory.json'


class BipipCommand(object):
    def __init__(self):
        self.filepath = INVENTORY_PATH
        self._check_file()

    def _check_file(self):
        if not os.path.isfile(self.filepath):
            with open(self.filepath, 'w') as f:
                f.write(json.dumps({}))

    def _load_inventory(self):
        with open(self.filepath, 'r') as f:
            inventory = json.load(f)
        return inventory

    def _write_inventory(self, data):
        with open(self.filepath, 'w') as f:
            f.write(json.dumps(data))

    def create_bigip(self, blob):
        data = self._load_inventory()
        group_id = str(uuid.uuid4())
        data[group_id] = blob
        self._write_inventory(data)
        return group_id

    def update_bigip(self, group_id, blob):
        data = self._load_inventory()
        data[group_id] = blob
        self._write_inventory(data)

    def get_blob(self, group_id):
        data = self._load_inventory()
        if group_id not in data:
            msg = _("id: %s not in inventory" % group_id)
            raise exceptions.CommandError(msg)
        return data[group_id]

    def show_inventory(self, group_id=None):
        if group_id:
            blob = self.get_blob(group_id)
            return (('ID', 'GROUP'),
                    (group_id, json.dumps(blob, indent=INDENT)))
        else:
            inventory = self._load_inventory()
            return (('ID', 'GROUP'),
                    ((k, json.dumps(v, indent=INDENT))
                     for k, v in inventory.items())
                    )

    def delete_group(self, group_id):
        inventory = self._load_inventory()
        if group_id not in inventory:
            msg = _("id: %s not in inventory" % group_id)
            raise exceptions.CommandError(msg)
        del inventory[group_id]
        self._write_inventory(inventory)


class CreateBigip(command.ShowOne):
    _description = _("Create a new bigip to a device group")

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
            metavar='<id>',
            help=_('ID of BIG-IP group'),
        )
        parser.add_argument(
            '--availability_zone',
            metavar='<availability_zone>',
            default=None,
            help=_('availability_zone which the BIG-IP is belong'),
        )
        parser.add_argument(
            '--icontrol_port',
            default="443",
            metavar='<icontrol_port>',
            help=_('port to communicate with BIG-IP'),
        )

        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        hostname, username, password, port = (parsed_args.icontrol_hostname,
                                              parsed_args.icontrol_username,
                                              parsed_args.icontrol_password,
                                              parsed_args.icontrol_port)
        ic = IControlClient(hostname, username, password, port)

        if parsed_args.id:
            blob = commander.get_blob(parsed_args.id)
            blob["bigips"][hostname] = ic.get_bigip_info()
            commander.update_bigip(parsed_args.id, blob)
            return commander.show_inventory(parsed_args.id)
        else:
            blob = {
                "admin_state_up": True,
                "availability_zone": parsed_args.availability_zone,
                "bigips": {
                    hostname: ic.get_bigip_info()
                },
            }
            group_id = commander.create_bigip(blob)
            return commander.show_inventory(group_id)


class DeleteBigip(command.Command):
    _description = _("Remove an existing BIG-IP from an existing device group")

    def get_parser(self, prog_name):
        parser = super(DeleteBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<id>',
            help=_('ID of BIG-IP group'),
        )

        parser.add_argument(
            '--icontrol_hostname',
            metavar='<icontrol_hostname>',
            default=None,
            help=_('icontrol_hostname of BIG-IP device'),
        )
        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        icontrol_hostname = parsed_args.icontrol_hostname
        if icontrol_hostname:
            blob = commander.get_blob(parsed_args.id)
            bigips = blob.get("bigips", None)
            if icontrol_hostname not in bigips:
                msg = _("bigip: %s not in group" % icontrol_hostname)
                raise exceptions.CommandError(msg)
            del bigips[icontrol_hostname]
            blob['bigips'] = bigips
            commander.update_bigip(parsed_args.id, blob)
        else:
            commander.delete_group(parsed_args.id)


class UpdateBigip(command.ShowOne):
    _description = _("Modify the admin properties of an existing device group")

    def get_parser(self, prog_name):
        parser = super(UpdateBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<id>',
            help=_('ID of BIG-IP group'),
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
            help=_('availability zone which the BIG-IP is belong'),
        )

        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        blob = commander.get_blob(parsed_args.id)
        blob["admin_state_up"] = parsed_args.admin_state \
            if parsed_args is not None else True
        if parsed_args.availability_zone:
            blob["availability_zone"] = parsed_args.availability_zone
        commander.update_bigip(parsed_args.id, blob)

        return commander.show_inventory(parsed_args.id)


class RefreshBigip(command.ShowOne):
    _description = _("Refresh the device properties of an existing "
                     "bigip in an existing device group")

    def get_parser(self, prog_name):
        parser = super(RefreshBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<id>',
            help=_('ID of BIG-IP group'),
        )
        parser.add_argument(
            'icontrol_hostname',
            metavar='<icontrol_hostname>',
            help=_('icontrol_hostname of BIG-IP'),
        )
        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        blob = commander.get_blob(parsed_args.id)
        bigips = blob.get("bigips", None)
        icontrol_hostname = parsed_args.icontrol_hostname
        if icontrol_hostname not in bigips:
            msg = _("bigip: %s not in group" % icontrol_hostname)
            raise exceptions.CommandError(msg)

        bigip_info = bigips[icontrol_hostname]
        ic = IControlClient(icontrol_hostname, bigip_info['username'],
                            bigip_info['password'], bigip_info['port'])
        blob["bigips"][icontrol_hostname] = ic.get_refresh_info()
        commander.update_bigip(parsed_args.id, blob)

        return commander.show_inventory(parsed_args.id)


class ListBigip(command.Lister):
    _description = _("List all BIG-IP in the inventory")

    def take_action(self, parsed_args):
        commander = BipipCommand()
        return commander.show_inventory()


class ShowBigip(command.ShowOne):
    _description = _("Show the specific group of BIG-IP inventory")

    def get_parser(self, prog_name):
        parser = super(ShowBigip, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            metavar='<id>',
            help=_('ID of BIG-IP group'),
        )
        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        return commander.show_inventory(parsed_args.id)
