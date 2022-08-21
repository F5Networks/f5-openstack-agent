# coding=utf-8
import os
import json
import uuid

from oslo_log import log as logging
from openstackclient.i18n import _
from osc_lib.command import command
from osc_lib import exceptions

from clientmanager import IControlClient

LOG = logging.getLogger(__name__)

INDENT = 4
INVENTORY_PATH = '/etc/neutron/bigip_inventory.json'


class BipipCommand(command.ShowOne):
    def __init__(self, app, app_args):
        super(BipipCommand, self).__init__(app, app_args)
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
        blob = self.get_blob(group_id)
        return (('ID', 'GROUP'),
                (group_id, json.dumps(blob, indent=INDENT)))

    def delete_group(self, group_id):
        inventory = self._load_inventory()
        if group_id not in inventory:
            msg = _("id: %s not in inventory" % group_id)
            raise exceptions.CommandError(msg)
        del inventory[group_id]
        self._write_inventory(inventory)


class CreateBigip(BipipCommand):
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
        """
        usage: f5agent bigip-create project icontrol_hostname
        """
        icontrol_hostname, icontrol_username, icontrol_password, icontrol_port = parsed_args.icontrol_hostname, \
                                                                                 parsed_args.icontrol_username, \
                                                                                 parsed_args.icontrol_password, \
                                                                                 parsed_args.icontrol_port
        ic = IControlClient(icontrol_hostname, icontrol_username, icontrol_password, icontrol_port)

        if parsed_args.id:
            blob = self.get_blob(parsed_args.id)
            blob["bigips"][icontrol_hostname] = ic.get_bigip_info()
            self.update_bigip(parsed_args.id, blob)
            return self.show_inventory(parsed_args.id)
        else:
            blob = {
                "admin_state_up": True,
                "availability_zone": parsed_args.availability_zone,
                "bigips": {
                    icontrol_hostname: ic.get_bigip_info()
                },
            }
            group_id = self.create_bigip(blob)
            return self.show_inventory(group_id)


class DeleteBigip(BipipCommand):
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
        if parsed_args.icontrol_hostname:
            blob = self.get_blob(parsed_args.id)
            bigips = blob.get("bigips", None)
            icontrol_hostname = parsed_args.icontrol_hostname
            if icontrol_hostname not in bigips:
                msg = _("bigip: %s not in group" % icontrol_hostname)
                raise exceptions.CommandError(msg)
            del bigips[icontrol_hostname]
            blob['bigips'] = bigips
            self.update_bigip(parsed_args.id, blob)

            return self.show_inventory(parsed_args.id)
        else:
            #  TODO: delete group, how to show
            self.delete_group(parsed_args.id)
            msg = 'delete group: %s successful' % parsed_args.id
            return (('MESSAGE'), (msg))


class UpdateBigip(BipipCommand):
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
        blob = self.get_blob(parsed_args.id)
        blob["admin_state_up"] = parsed_args.admin_state if parsed_args is not None else True
        if parsed_args.availability_zone:
            blob["availability_zone"] = parsed_args.availability_zone
        self.update_bigip(parsed_args.id, blob)

        return self.show_inventory(parsed_args.id)


class RefreshBigip(BipipCommand):
    _description = _("Refresh the device properties of an existing bigip in an existing device group")

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
        blob = self.get_blob(parsed_args.id)
        bigips = blob.get("bigips", None)
        icontrol_hostname = parsed_args.icontrol_hostname
        if icontrol_hostname not in bigips:
            msg = _("bigip: %s not in group" % icontrol_hostname)
            raise exceptions.CommandError(msg)

        bigip_info = bigips[icontrol_hostname]
        ic = IControlClient(icontrol_hostname, bigip_info['username'], bigip_info['password'], bigip_info['port'])
        blob["bigips"][icontrol_hostname] = ic.get_refresh_info()
        self.update_bigip(parsed_args.id, blob)

        return self.show_inventory(parsed_args.id)


class ListBigip(command.Lister):
    _description = _("List all BIG-IP in the inventory")

    def take_action(self, parsed_args):
        with open(INVENTORY_PATH, 'r') as f:
            inventory = json.load(f)
        return (('ID', 'GROUP'),
                ((k, json.dumps(v, indent=INDENT)) for k, v in inventory.items())
                )


class ShowBigip(BipipCommand):
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
        return self.show_inventory(parsed_args.id)
