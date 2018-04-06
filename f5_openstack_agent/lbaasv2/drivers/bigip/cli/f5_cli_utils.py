import argparse

import sys
import urllib3
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings
warnings.filterwarnings("ignore")

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from oslo_utils import importutils

ACTION_MODULE = 'f5_openstack_agent.lbaasv2.drivers.bigip.cli.actions.'

class Execute(argparse._SubParsersAction):
    def __init__(self, option_strings, **kwargs):
        super(Execute, self).__init__(option_strings, **kwargs)
        self.actions = {
            "sync":"sync.Sync",
            "sync-all":"sync_all.SyncAll",
            "delete":"delete.Delete",
            "holzhammer":"holzhammer.Holzhammer",
            "druckhammer":"druckhammer.Druckhammer"
        }

    def __call__(self, parser, namespace, values, option_string=None):
        super(Execute, self).__call__(parser, namespace, values, option_string)
        action = self.actions.get(values[0])
        if action:

            instance = importutils.import_object(ACTION_MODULE+action,namespace)
            instance.execute()

def main():

    parser = argparse.ArgumentParser(prog='f5_utils', description='Operations utilities for F5 LBAAS driver.')

    parser.add_argument('--config-file', dest='config', action='append',
                       default=["/etc/neutron/f5-oslbaasv2-agent.ini", "/etc/neutron/neutron.conf"],
                       help='Configuration files')

    parser.add_argument('--log',dest='log', action='store_true',
                       help='Enable openstack log output')

    subparsers = parser.add_subparsers(title='command', description='valid subcommands',
                       help='command to execute', action=Execute, dest='subcommand')

    parser_sync = subparsers.add_parser('sync', help='sync a specific load balancer')
    parser_sync.add_argument('--lb-id',dest='lb_id',
                       help='router id',action='store')

    parser_sync_all = subparsers.add_parser('sync-all', help='sync all load balancer')
    parser_sync_all.add_argument('--project-id',dest='project_id',
                       help='project id',action='store')


    parser_delete = subparsers.add_parser('delete', help='delete a specific load balancer')
    parser_delete.add_argument('--lb-id',dest='lb_id',
                       help='router id',action='store')

    parser_holzhammer = subparsers.add_parser('holzhammer', help='purge and resync project')
    parser_holzhammer.add_argument('--i-am-sure-what-i-am-doing', action='store_true', dest='sure',
                                   help='declaration of liability')
    parser_holzhammer.add_argument('--no-sync', action='store_false', dest='sync',
                                   help='disable resync of project')
    parser_holzhammer.add_argument('--project-id',dest='project_id',
                                   help='project id',action='store')

    parser_druckhammer = subparsers.add_parser('druckhammer', help='purge all bigip '
                                                                   'partitions/vlans/selfip/routes/routedomains')
    parser_druckhammer.add_argument('--i-am-sure-what-i-am-doing', action='store_true', dest='sure',
                                   help='declaration of liability')
    parser_druckhammer.add_argument('--sync', action='store_true', dest='sync',
                                   help='resync all LB from agent/neutron')

    parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
