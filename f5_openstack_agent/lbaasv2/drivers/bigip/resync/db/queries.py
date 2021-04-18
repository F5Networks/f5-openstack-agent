# -*- coding: utf-8 -*-

from f5_openstack_agent.lbaasv2.drivers.bigip.resync.db.connection \
    import Session
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.db import models


class Queries(object):

    def __init__(self):

        self.connection = models.con
        self.lb = models.Loadbalancer
        self.ls = models.Listener
        self.pl = models.Pool
        self.mn = models.Monitor
        self.mb = models.Member
        self.bindings = models.Loadbalanceragentbindings

    def get_loadbalancers_by_agent_id(self, agent_id):
        with Session(self.connection) as se:
            ret = se.query(self.lb).join(self.bindings).filter(
                  self.lb.id == self.bindings.loadbalancer_id).all()
        return ret

    def get_loadbalancer(self, lb_id):
        with Session(self.connection) as se:
            ret = se.query(self.lb).get(lb_id)
        return ret

    def get_loadbalancers_by_project_id(self, pj_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.lb).filter(
                self.lb.project_id == pj_id
            ).all()
        return ret

    def get_listener(self, ls_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.ls).get(ls_id)
        return ret

    def get_listeners_by_lb_id(self, lb_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.ls).filter(
                self.ls.loadbalancer_id == lb_id
            ).all()
        return ret

    def get_pool(self, pl_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.pl).get(pl_id)
        return ret

    def get_pools_by_lb_id(self, lb_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.pl).filter(
                models.Pool.loadbalancer_id == lb_id
            ).all()
        return ret

    def get_mn(self, mn_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.mn).get(mn_id)
        return ret

    def get_member(self, mb_id):
        # with self.session as se:
        with Session(self.connection) as se:
            ret = se.query(self.mb).get(mb_id)
        return ret
