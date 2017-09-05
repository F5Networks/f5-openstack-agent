import argparse
import urllib3
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings
warnings.filterwarnings("ignore")

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from oslo_utils import importutils


ACTION_MODULE = 'f5_openstack_agent.lbaasv2.drivers.bigip.cli.actions.'

class Execute(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(Execute, self).__init__(option_strings, dest, **kwargs)
        self.actions = {"sync":"sync.Sync","sync-all":"sync_all.SyncAll","delete":"delete.Delete"}

    def __call__(self, parser, namespace, values, option_string=None):
        action = self.actions.get(values)
        if action:

            instance = importutils.import_object(ACTION_MODULE+action,namespace)


            instance.execute()


def main():
    parser = argparse.ArgumentParser(prog='f5_utils', description='Operations utilities for F5 LBAAS driver.')

    parser.add_argument('command',
                       help='command to execute',action=Execute,choices=["sync", "sync-all", "delete"])

    parser.add_argument('--lb-id',dest='lb_id',
                       help='router id',action='store')

    parser.add_argument('--project-id',dest='project_id',
                       help='project id',action='store')

    parser.add_argument('--config-file', dest='config', action='append',
                       default=["/etc/neutron/f5-oslbaasv2-agent.ini", "/etc/neutron/neutron.conf"],
                       help='Configuration files')
    parser.add_argument('--log',dest='log', action='store_true',
                       help='Enable openstack log output')

    parser.parse_args()
