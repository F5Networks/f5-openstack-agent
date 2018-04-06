import base_action

from sync_all import SyncAll
from f5_openstack_agent.lbaasv2.drivers.bigip import system_helper
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

class Holzhammer(base_action.BaseAction):

    def __init__(self, namespace):
        self.sync = namespace.sync
        self.project_id = namespace.project_id
        self.sh = system_helper.SystemHelper()
        super(Holzhammer, self).__init__(namespace)

    def execute(self):
        if self.project_id is None:
            print("Please specify an Project id with --project-id")
            exit(1)

        for bigip in self.driver.get_all_bigips():
            try:
                print("Cleaning Partition %s" % "Project_" + self.project_id)
                self.sh.purge_folder_contents(bigip, "Project_" + self.project_id)
            except Exception as err:
                print(err.message)

        if self.sync:
            # Crude hack, but it works :D
            # I wanted to reuse the code of SyncAll but don't want to initalize a new SyncAll class instance,
            # which would connect to F5 and reinitalize objects etc...
            # Instead, I just cast this Holzhammer instance to the SyncAll Class and re-execute meself :)
            Syncer = self
            self.__class__ = SyncAll
            Syncer.execute()
