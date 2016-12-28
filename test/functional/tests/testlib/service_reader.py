

class LoadbalancerReader(object):
    def __init__(self, service):
        self.service = service
        self.loadbalancer = service.get('loadbalancer', None)
        self.network_id = self.loadbalancer.get('network_id', "")
        self.network = service['networks'][self.network_id]

    def id(self):
        return self.loadbalancer['id']

    def tenant_id(self):
        return self.loadbalancer['tenant_id']

    def vip_address(self):
        return self.loadbalancer['vip_address']

    def network_id(self):
        return self.loadbalancer['network_id']

    def network_type(self):
        return self.network['provider:network_type']

    def network_seg_id(self):
        return self.network['provider:segmentation_id']

    def subnet_id(self):
        return self.loadbalancer['vip_subnet_id']

class ServiceReader(object):

    def __init_(self, service):
        self.service = service

    def get_loadbalancer(self):
        loadbalancers = self.service.get("loadbalancer", None)

