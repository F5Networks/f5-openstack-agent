
import base_action

from neutron.plugins.common import constants as plugin_const

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class Sync(base_action.BaseAction):

    def __init__(self, namespace):
        super(Sync, self).__init__(namespace)

    def execute(self):

        service = self.manager.plugin_rpc.get_service_by_loadbalancer_id(
                self.lb_id
            )

        if not bool(service):
            print("Loadbalancer {} not found".format(self.lb_id))
            exit(1)

        service = self.replace_dict_value(service, 'provisioning_status', plugin_const.PENDING_CREATE)

        self.driver._common_service_handler(service)

        print("The device state of loadbalancer {} has been synced with Neutron".format(self.lb_id))


