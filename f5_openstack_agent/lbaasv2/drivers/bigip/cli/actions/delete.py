
import base_action


from oslo_log import log as logging
from neutron.plugins.common import constants as plugin_const

LOG = logging.getLogger(__name__)


class Delete(base_action.BaseAction):

    def __init__(self, namespace):
        super(Delete, self).__init__(namespace)

    def execute(self):
        service = self.manager.plugin_rpc.get_service_by_loadbalancer_id(
                self.lb_id
                )

        if not bool(service):
            print("Loadbalancer {} not found".format(self.lb_id))
            exit(1)

        service = self.replace_dict_value(service, 'provisioning_status', plugin_const.PENDING_DELETE)


        self.driver._common_service_handler(service,cli_sync=True)

        print("All device configuration forloadbalancer {} has been removed".format(self.lb_id))

