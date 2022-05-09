import requests

from oslo_log import log

LOG = log.getLogger(__name__)

requests.packages.urllib3.disable_warnings()


class F5OSClient(object):

    host = ""
    port = 443
    user = "admin"
    password = "admin"

    proto = "https"

    h_accept = "application/yang-data+json"
    h_content = "application/yang-data+json"

    headers = {
        "Accept": h_accept,
        "Content-Type": h_content
    }

    verify = False
    timeout = 15

    def __init__(self, **kwargs):
        self.host = kwargs.get("host", self.host)
        self.port = kwargs.get("port", self.port)
        self.user = kwargs.get("user", self.user)
        self.password = kwargs.get("password", self.password)

        self.url = self.proto + "://" + self.host + ":" + \
            str(self.port) + "/api/data/"
        self.auth = (self.user, self.password)

    def get(self, **kwargs):
        path = kwargs.get("path", "")
        url = self.url + path

        resp = requests.get(url, headers=self.headers, auth=self.auth,
                            timeout=self.timeout, verify=self.verify)

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return
        else:
            resp.raise_for_status()

    def post(self, **kwargs):
        path = kwargs.get("path", "")
        body = kwargs.get("body", {})
        url = self.url + path

        resp = requests.post(
            url, json=body, headers=self.headers, auth=self.auth,
            timeout=self.timeout, verify=self.verify
        )

        if resp.status_code == 201:
            return
        else:
            resp.raise_for_status()

    def delete(self, **kwargs):
        path = kwargs.get("path", "")
        url = self.url + path

        resp = requests.delete(
            url, headers=self.headers, auth=self.auth,
            timeout=self.timeout, verify=self.verify
        )

        if resp.status_code == 204:
            return
        elif resp.status_code == 404:
            return
        else:
            resp.raise_for_status()

    def patch(self, **kwargs):
        path = kwargs.get("path", "")
        body = kwargs.get("body", {})
        url = self.url + path

        resp = requests.patch(
            url, json=body, headers=self.headers, auth=self.auth,
            timeout=self.timeout, verify=self.verify
        )

        if resp.status_code == 204:
            return
        else:
            resp.raise_for_status()

    def put(self, **kwargs):
        path = kwargs.get("path", "")
        body = kwargs.get("body", {})
        url = self.url + path

        resp = requests.put(
            url, json=body, headers=self.headers, auth=self.auth,
            timeout=self.timeout, verify=self.verify
        )

        if resp.status_code == 204:
            return
        else:
            resp.raise_for_status()


class F5OSResource(object):

    def __init__(self, client, name=None):
        if not client:
            raise ValueError("Invalid client: " + client)
        self.client = client

    def instance_path(self):
        raise NotImplementedError()

    def load(self, path=None):
        if not path:
            path = self.instance_path()

        resp = self.client.get(path=path)
        if resp:
            key = self.path[:-1]
            return resp[key][0]
        else:
            return

    def loadCollection(self):
        resp = self.client.get(path=self.path)
        return resp[self.path][self.type]

    def create(self, body):
        if not body:
            raise ValueError("Invalid body: " + body)
        return self.client.post(path=self.path, body=body)

    def delete(self, path=None):
        if not path:
            path = self.instance_path()
        self.client.delete(path=path)

    def update(self, **kwargs):
        raise NotImplementedError()


class Tenant(F5OSResource):

    type = "tenant"
    path = "f5-tenants:tenants"

    def __init__(self, client, name=None):
        super(Tenant, self).__init__(client)

        if name is not None:
            self.validate_name(name)
            self.name = name

    def validate_name(self, name):
        if not name or name.isspace():
            raise ValueError("Invalid tenant name: " + name)

    def instance_path(self, name=None):
        if name is None:
            name = self.name
        self.validate_name(name)
        return self.path + "/tenant=" + name

    def load(self, name=None):
        resp = super(Tenant, self).load(path=self.instance_path(name))
        if resp:
            self.name = resp["config"]["name"]
        return resp

    def create(self, **kwargs):
        raise NotImplementedError()

    def delete(self, name=None):
        raise NotImplementedError()

    def update(self, **kwargs):
        raise NotImplementedError()

    def associateVlan(self, vlan_id, tenant_name=None):
        path = self.instance_path(tenant_name) + "/config/vlans"
        body = {
            "f5-tenants:vlans": [
                int(vlan_id)
            ]
        }
        self.client.patch(path=path, body=body)

    def dissociateVlan(self, vlan_id, tenant_name=None):
        path = self.instance_path(tenant_name) + "/config/vlans"
        body = self.client.get(path=path)

        if not body:
            return

        try:
            body["f5-tenants:vlans"].remove(vlan_id)
            self.client.put(path=path, body=body)
        except ValueError:
            pass


class Interface(F5OSResource):

    type = "interface"
    path = "openconfig-interfaces:interfaces"

    def __init__(self, client, name=None):
        super(Interface, self).__init__(client)

        if name is not None:
            self.validate_name(name)
            self.name = name

    def validate_name(self, name):
        if not name or name.isspace():
            raise ValueError("Invalid interface name: " + name)

    def instance_path(self, name=None):
        if name is None:
            name = self.name
        self.validate_name(name)
        return self.path + "/interface=" + name

    def load(self, name=None):
        resp = super(Interface, self).load(path=self.instance_path(name))
        if resp and resp["config"]["type"] == self.subtype:
            self.name = resp["config"]["name"]
            return resp
        else:
            return None

    def create(self, **kwargs):
        raise NotImplementedError()

    def delete(self, name=None):
        raise NotImplementedError()

    def update(self, **kwargs):
        raise NotImplementedError()


class MgmtInterface(Interface):

    subtype = "iana-if-type:ethernetCsmacd"

    def __init__(self, client):
        super(MgmtInterface, self).__init__(client, "mgmt")

    def validate_name(self, name):
        if name != "mgmt":
            raise ValueError("Invalid management interface name: " + name)

    def loadCollection(self):
        resp = super(MgmtInterface, self).loadCollection()
        interfaces = []
        for e in resp:
            if e["config"]["type"] == self.subtype and \
               e["config"]["name"] == "mgmt":
                interfaces.append(e)
        return interfaces


class DataInterface(Interface):

    subtype = "iana-if-type:ethernetCsmacd"

    def validate_name(self, name):
        if name == "mgmt":
            raise ValueError("Invalid data interface name: " + name)

        super(DataInterface, self).validate_name(name)

    def loadCollection(self):
        resp = super(DataInterface, self).loadCollection()
        interfaces = []
        for e in resp:
            if e["config"]["type"] == self.subtype and \
               e["config"]["name"] != "mgmt":
                interfaces.append(e)
        return interfaces

    def associateVlan(self, vlan_id, interface_name=None):
        path = self.instance_path(interface_name) + \
            "/openconfig-if-aggregate:aggregation/openconfig-vlan:switched-vlan/config/trunk-vlans"    # noqa
        body = {
            "openconfig-vlan:trunk-vlans": [
                int(vlan_id)
            ]
        }
        self.client.patch(path=path, body=body)

    def dissociateVlan(self, vlan_id, interface_name=None):
        path = self.instance_path(interface_name) + \
            "/openconfig-if-aggregate:aggregation/openconfig-vlan:switched-vlan/config/trunk-vlans"    # noqa
        body = self.client.get(path=path)

        if not body:
            return

        try:
            body["openconfig-vlan:trunk-vlans"].remove(vlan_id)
            self.client.put(path=path, body=body)
        except ValueError:
            pass


class LAG(DataInterface):

    subtype = "iana-if-type:ieee8023adLag"


class Vlan(F5OSResource):

    type = "vlan"
    path = "openconfig-vlan:vlans"

    def __init__(self, client, id=None, name=None):
        super(Vlan, self).__init__(client)

        if id is not None:
            self.validate_id(id)
            self.id = id

        if name is not None:
            self.validate_name(name)
            self.name = name

    def validate_id(self, id):
        if id is None or int(id) < 0 or int(id) > 4095:
            raise ValueError("Invalid vlan id: " + str(id))

    def validate_name(self, name):
        if not name or name.isspace():
            raise ValueError("Invalid vlan name: " + name)

    def instance_path(self, id=None):
        if id is None:
            id = self.id
        self.validate_id(id)
        return self.path + "/vlan=" + str(id)

    def load(self, id=None):
        resp = super(Vlan, self).load(path=self.instance_path(id))
        if resp:
            self.id = resp["config"]["vlan-id"]
            self.name = resp["config"]["name"]
        return resp

    def create(self, id=None, name=None):
        if id is None:
            id = self.id
        self.validate_id(id)

        if name is None:
            name = self.name
        self.validate_name(name)

        body = {
            "openconfig-vlan:vlan": [{
                "vlan-id": str(id),
                "config": {
                    "vlan-id": int(id),
                    "name": name
                }
            }]
        }
        super(Vlan, self).create(body=body)
        self.id = id
        self.name = name

    def delete(self, id=None):
        super(Vlan, self).delete(path=self.instance_path(id))

    def update(self, **kwargs):
        raise NotImplementedError()
