# coding=utf-8
import json
import os
import uuid

from openstackclient.i18n import _
from osc_lib.command import command
from osc_lib import exceptions
from oslo_log import log as logging

from f5_openstack_agent.client.clientmanager import IControlClient
from f5_openstack_agent.client.encrypt import decrypt_data

LOG = logging.getLogger(__name__)

INDENT = 4
INVENTORY_PATH = '/etc/neutron/services/f5/inventory.json'


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
            f.write(json.dumps(data, indent=INDENT))

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

    def refresh_all(self):
        inventory = self._load_inventory()
        for group_id in inventory:
            self.refresh_group(group_id)

    def refresh_group(self, group_id):
        blob = self.get_blob(group_id)
        bigip = blob['bigip']
        for hostname, info in bigip.items():
            self.refresh_bigip(group_id, hostname)

    def refresh_bigip(self, group_id, hostname):
        blob = self.get_blob(group_id)

        bigip = blob.get("bigip", None)
        if hostname not in bigip:
            msg = _("bigip: %s not in group: %s" % (hostname, group_id))
            raise exceptions.CommandError(msg)

        bigip_info = bigip[hostname]
        username = decrypt_data(bigip_info['serial_number'],
                                bigip_info['username'])
        password = decrypt_data(bigip_info['serial_number'],
                                bigip_info['password'])
        ic = IControlClient(hostname, username, password, bigip_info['port'])
        blob["bigip"][hostname] = ic.get_refresh_info(bigip_info)
        self.update_bigip(group_id, blob)

    def check_hostname_exists(self, hostname):
        inventory = self._load_inventory()
        for group_id, group in inventory.items():
            bigip = group['bigip']
            if hostname in bigip:
                msg = _("bigip: %s already exists in group: %s" %
                        (hostname, group_id))
                raise exceptions.CommandError(msg)

    def get_active_bigips(self, availability_zone):
        zones = []
        if availability_zone:
            zones = availability_zone.split(",")
        inventory = self._load_inventory()
        bigips = []
        for group_id, group in inventory.items():
            if group['availability_zone'] in zones:
                bigip = group['bigip']
                for host, info in bigip.items():
                    if info['failover_state'] == 'active':
                        username = decrypt_data(info['serial_number'],
                                                info['username'])
                        password = decrypt_data(info['serial_number'],
                                                info['password'])
                        bigips.append({
                            'group_id': group_id,
                            'hostname': host,
                            'username': username,
                            'password': password,
                            'port': info['port'],
                        })
        return bigips

    def update_external_mapping(self, parsed_args, blob):
        if parsed_args.external_physical_mappings is not None:
            if not parsed_args.host:
                msg = _(
                    "Update %s external-physical-mappings %s, "
                    "--host is not given" % (
                        parsed_args.id,
                        parsed_args.external_physical_mappings
                    )
                )
                raise exceptions.CommandError(msg)

            if parsed_args.host not in blob["bigip"]:
                msg = _(
                    "Update %s host %s "
                    "external-physical-mappings %s. "
                    "The host %s cannot be found in inventory."
                    % (
                        parsed_args.id,
                        parsed_args.host,
                        parsed_args.external_physical_mappings,
                        parsed_args.host,
                    )
                )
                raise exceptions.CommandError(msg)

            blob["bigip"][parsed_args.host][
                "external_physical_mappings"
            ] = parsed_args.external_physical_mappings


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
        parser.add_argument(
            '--vtep_ip',
            default=None,
            metavar='<vtep_id>',
            help=_('vtep ip for agent'),
        )
        parser.add_argument(
            '--external-physical-mappings',
            default="default:1.1",
            metavar='<external-physical-mappings>',
            help=_(
                'maps of neutorn physical network to bigip interface/trunk, '
                'such as '
                '<neturon physical network>:<bigip interface_name>,... '
                'for example '
                '"default:1.3, phynet1:1.2, exnet:trunk_1". '
                'The "default" is for all others nuknown '
                'physical networks.'
            ),
        )

        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        hostname, username, password, port = (parsed_args.icontrol_hostname,
                                              parsed_args.icontrol_username,
                                              parsed_args.icontrol_password,
                                              parsed_args.icontrol_port)
        ic = IControlClient(hostname, username, password, port)
        if not ic.bigip:
            msg = "fail to connect BIG-IP: {}".format(hostname)
            raise exceptions.CommandError(msg)

        commander.check_hostname_exists(hostname)
        if parsed_args.id:
            blob = commander.get_blob(parsed_args.id)
            bigip_num = len(blob["bigip"])
            if bigip_num == 2:
                msg = _("device group already have two bigips")
                raise exceptions.CommandError(msg)
            if bigip_num == 1:
                if ic.get_failover_state() != "standby":
                    msg = _("The failover_state of second BIG-IP you "
                            "create should be standby")
                    raise exceptions.CommandError(msg)
                ic.update_traffic_group1_mac(blob["masquerade_mac"])

            if bigip_num == 0:
                blob["masquerade_mac"] = ic.update_traffic_group1_mac()

            blob["bigip"][hostname] = ic.get_bigip_info()
            commander.update_bigip(parsed_args.id, blob)
            return commander.show_inventory(parsed_args.id)
        else:
            if ic.get_failover_state() != "active":
                msg = _("The failover_state of first BIG-IP "
                        "you create should be active")
                raise exceptions.CommandError(msg)
            blob = {
                "admin_state_up": True,
                "availability_zone": parsed_args.availability_zone,
                "masquerade_mac": ic.update_traffic_group1_mac(),
                "bigip": {
                    hostname: ic.get_bigip_info()
                },
            }
            if parsed_args.vtep_ip:
                blob['local_link_information'] = \
                    [{"node_vtep_ip": parsed_args.vtep_ip}]

            blob["bigip"][hostname][
                "external_physical_mappings"
            ] = parsed_args.external_physical_mappings

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
            bigip = blob.get("bigip", None)
            if icontrol_hostname not in bigip:
                msg = _("bigip: %s not in group" % icontrol_hostname)
                raise exceptions.CommandError(msg)
            del bigip[icontrol_hostname]
            blob['bigip'] = bigip
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
        parser.add_argument(
            '--vtep_ip',
            default=None,
            metavar='<vtep_id>',
            help=_('vtep ip for agent'),
        )
        parser.add_argument(
            '--host',
            default=None,
            metavar='<host>',
            help=_(
                'host should be given, when update bigip device info'
            ),
        )
        parser.add_argument(
            '--external-physical-mappings',
            default=None,
            metavar='<external-physical-mappings>',
            help=_(
                'maps of neutorn physical network to bigip interface/trunk, '
                'such as '
                '<neturon physical network>:<bigip interface_name>,... '
                'for example '
                '"default:1.3, phynet1:1.2, exnet:trunk_1". '
                'The "default" is for all others nuknown '
                'physical networks.'
            ),
        )

        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        blob = commander.get_blob(parsed_args.id)
        blob["admin_state_up"] = parsed_args.admin_state \
            if parsed_args is not None else True
        if parsed_args.availability_zone:
            blob["availability_zone"] = parsed_args.availability_zone
        if parsed_args.vtep_ip:
            blob['local_link_information'] = \
                [{"node_vtep_ip": parsed_args.vtep_ip}]
        commander.update_external_mapping(parsed_args, blob)
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
            '--icontrol_hostname',
            metavar='<icontrol_hostname>',
            help=_('icontrol_hostname of BIG-IP'),
        )
        return parser

    def take_action(self, parsed_args):
        commander = BipipCommand()
        icontrol_hostname = parsed_args.icontrol_hostname
        group_id = parsed_args.id
        if group_id == "all":
            commander.refresh_all()
            return {}, {}
        else:
            if icontrol_hostname:
                commander.refresh_bigip(group_id, icontrol_hostname)
            else:
                commander.refresh_group(group_id)
            return commander.show_inventory(group_id)


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
