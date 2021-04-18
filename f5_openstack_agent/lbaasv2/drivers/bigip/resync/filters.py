# -*- coding: utf-8 -*-


class BigIPFilter(object):

    def __init__(self, prefix):
        self.prefix = prefix + "_"

    def get_id(self, resource):
        uuid = resource.name.split(self.prefix)[-1]
        return uuid

    def get_ids(self, resources):
        ids = []
        for res in resources:
            if self.prefix in res.name:
                uuid = self.get_id(res)
                ids.append(uuid)
        return set(ids)

    @staticmethod
    def format_member(member):
        address = None
        port = None
        mb = member.get('name')

        if "%" in mb:
            mb = mb.split("%")
            address = mb[0]
            if "." in mb[1]:
                port = mb[1].split('.')[1]
            else:
                port = mb[1].split(":")[1]
        else:
            if mb.count(":") > mb.count("."):
                mb = mb.split('.')
            else:
                mb = mb.split(':')
            address = mb[0]
            port = mb[1]
        address_port = address + "_" + str(port)
        return address_port
        # return {"address": address, "port": port}

    def filter_pool_members(self, partition_pools):
        pools = {}
        for pl in partition_pools:
            members = []
            pl_id = None
            member_items = pl.membersReference.get('items')
            if member_items:
                for mb in member_items:
                    member = self.format_member(mb)
                    members.append(member)
            pl_id = self.get_id(pl)
            pools[pl_id] = members
        return pools


class LbaasFilter(object):

    def get_ids(self, resources):
        ids = []
        for res in resources:
            ids.append(res.id)
        return set(ids)

    @staticmethod
    def format_member(member):
        mb = {}
        mb['address_port'] = member.address + "_" + str(member.protocol_port)
        # mb['port'] = member.protocol_port
        mb['id'] = member.id
        return mb

    def filter_pool_members(self, project_pools):
        pools = {}
        for pl in project_pools:
            members = []
            for mb in pl.members:
                member = self.format_member(mb)
                members.append(member)
            pools[pl.id] = members
        return pools
