
import base_action

from neutron.plugins.common import constants as plugin_const

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class SyncAll(base_action.BaseAction):

    def __init__(self, namespace):
        self.project_id = namespace.project_id
        super(SyncAll, self).__init__(namespace)

    def execute(self):

        services = self.manager.plugin_rpc.get_all_loadbalancers(host=self.manager.agent_host)

        if self.project_id is not None:
            print("Syncing all LBs in project {}".format(self.project_id))
        else:
            print("Syncing all LBs hosted on agent {}".format(self.host))

        for service in services:

            if self.project_id is None or service['tenant_id'] == self.project_id :

                detailed_service = self.manager.plugin_rpc.get_service_by_loadbalancer_id(service['lb_id'])

                print("Starting sync attempt for load balancer {}".format(service['lb_id']))


                detailed_service = self.replace_dict_value(detailed_service, 'provisioning_status', plugin_const.PENDING_CREATE)
                self.driver._common_service_handler(detailed_service)

                print("The device state of loadbalancer {} has been synced with Neutron".format(service['lb_id']))


