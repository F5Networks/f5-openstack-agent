import base_action

from sync_all import SyncAll
from f5_openstack_agent.lbaasv2.drivers.bigip import system_helper, resource_helper
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

class Druckhammer(base_action.BaseAction):

    def __init__(self, namespace):
        self.exempt_folders = ['/', 'Common', 'Drafts']
        self.sure = namespace.sure
        self.sync = namespace.sync
        self.project_id = None
        self.sh = system_helper.SystemHelper()
        self.rd_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.route_domain)
        self.si_manager = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.selfip)
        self.vlan_manger = resource_helper.BigIPResourceHelper(
            resource_helper.ResourceType.vlan)
        super(Druckhammer, self).__init__(namespace)

    def execute(self):
        if not self.sure:
            print("Please be sure by appending --i-am-sure-what-i-am-doing")
            exit(1)

        for bigip in self.driver.get_all_bigips():
            for folder in self.sh.get_folders(bigip):
                if folder in self.exempt_folders:
                    continue

                try:
                    print("Purging Folder \"%s\"" % folder)
                    self.sh.purge_folder_contents(bigip, folder)
                    self.sh.purge_folder(bigip, folder)
                except Exception as err:
                    print("Failed purging folder %s: %s" % (folder, err.message))

            for route in self.get_routes(bigip):
                try:
                    print("Purging route \"%s\"" % route.name)
                    route.delete()
                except Exception as err:
                    print("Failed purging route %s: %s" % (route.name, err.message))


            for selfip in self.get_selfips(bigip):
                try:
                    print("Purging selfip \"%s\"" % selfip.name)
                    selfip.delete()
                except Exception as err:
                    print("Failed purging selfip %s: %s" % (selfip.name, err.message))

            for route_domain in self.get_routedomains(bigip):
                try:
                    print("Purging route_domain \"%s\"" % route_domain.name)
                    route_domain.delete()
                except Exception as err:
                    print("Failed purging route_domain %s: %s" % (route_domain.name, err.message))


            for vlan in self.get_vlans(bigip):
                try:
                    print("Purging vlan \"%s\"" % vlan.name)
                    vlan.delete()
                except Exception as err:
                    print("Failed purging vlan %s: %s" % (vlan.name, err.message))

        if self.sync:
            # Crude hack, but it works :D
            # I wanted to reuse the code of SyncAll but don't want to initalize a new SyncAll class instance,
            # which would connect to F5 and reinitalize objects etc...
            # Instead, I just cast this druckhammer instance to the SyncAll Class and re-execute meself :)
            Syncer = self
            self.__class__ = SyncAll
            Syncer.execute()

    def get_selfips(self, bigip):
        selfips = []
        for selfip in self.si_manager.get_resources(bigip, "Common"):
            if selfip.name.startswith("local-" + bigip.device_name):
                selfips.append(selfip)

        return selfips

    def get_routedomains(self, bigip):
        routedomains = []
        for routedomain in self.rd_manager.get_resources(bigip, "Common"):
            if routedomain.name.startswith("rd-"):
                routedomains.append(routedomain)

        return routedomains

    def get_routes(self, bigip):
        routes = []
        for route in bigip.tm.net.routes.get_collection():
            if route.name.startswith("rt-"):
                routes.append(route)

        return routes

    def get_vlans(self, bigip):
        vlans = []
        for vlan in self.vlan_manger.get_resources(bigip, "Common"):
            if vlan.name.startswith("vlan-"):
                vlans.append(vlan)

        return vlans
