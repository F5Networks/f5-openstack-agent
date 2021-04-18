# -*- coding: utf-8 -*-

from f5_openstack_agent.lbaasv2.drivers.bigip.resync.collector \
    import base
from f5_openstack_agent.lbaasv2.drivers.bigip.resync.util \
    import time_logger
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class LbassDBCollector(base.Collector):

    def __init__(self, source, agent_id):
        self.source = source
        self.agent_id = agent_id

        # NOTE(pzhang): should not construct cache here
        # cache content {'project_uuid':[resource_a, ...]}
        # eager load
        self.lb_cache = {}
        self.project_cache = []

        # these cache are lazy load
        self.ls_cache = {}
        self.pl_cache = {}

        self.init_lb_cache(self.agent_id)
        self.init_agent_projects()

    def _cache_agent_lb_by_project_id(self,
                                      lbs,
                                      lb_cache):
        for lb in lbs:
            if lb.project_id not in lb_cache:
                self.lb_cache[lb.project_id] = [lb]
            else:
                self.lb_cache[lb.project_id].append(lb)

    def _cache_resource_by_project_id(self,
                                      project_id,
                                      resources,
                                      resource_cache):
        # new search overwrite all old data
        resource_cache[project_id] = resources

    def init_lb_cache(self, agent_id):
        """Initiate root loadbalancer cache for agent

        this is should not be lazy load
        agent_id:str is passed by users
        """
        lbs = self.source.get_loadbalancers_by_agent_id(
            agent_id)
        self._cache_agent_lb_by_project_id(lbs,
                                           self.lb_cache)

    def init_agent_projects(self):
        self.project_cache = self.lb_cache.keys()

    @time_logger(LOG)
    def get_projects_on_device(self):
        LOG.info("Get projects of agent : %s in Neutron DB",
                 self.agent_id)
        return self.project_cache

    @time_logger(LOG)
    def get_project_loadbalancers(self, project_id):
        LOG.info("Get loadbalancers of project: %s", project_id)
        if project_id not in self.project_cache:
            # project is not exist in cache
            return []

        # assert or throw error
        loadbalancers = self.lb_cache[project_id]
        return loadbalancers

    @time_logger(LOG)
    def get_project_listeners(self, project_id):
        LOG.info("Get listeners of project: %s", project_id)
        total_listeners = []

        if project_id not in self.project_cache:
            # project is not exist in cache
            return []

        if project_id in self.ls_cache:
            # find ls of project in cache
            return self.ls_cache[project_id]

        total_listeners = self.source.get_listeners_by_project_id(
           project_id
        )

        self._cache_resource_by_project_id(project_id,
                                           total_listeners,
                                           self.ls_cache)

        return total_listeners

    @time_logger(LOG)
    def get_project_pools(self, project_id):
        LOG.info("Get pools of project: %s", project_id)
        total_pools = []

        if project_id not in self.project_cache:
            # project is not exist in cache
            return []

        if project_id in self.pl_cache:
            pools = self.pl_cache[project_id]
            return pools

        total_pools = self.source.get_pools_by_project_id(
            project_id
        )

        self._cache_resource_by_project_id(project_id,
                                           total_pools,
                                           self.pl_cache)

        # set pl_cache first, then set member
        # or it will be in recursive loop
        # if cache do not have any pools belongs to project_id
        # , it will cause sink into infinite recursive.
        self.set_project_pool_members(project_id)

        return total_pools

    @time_logger(LOG)
    def set_project_pool_members(self, project_id):
        """Set members in a pool of a project

           consider members are as configuration of pools
        """
        LOG.info("Set pool members of project: %s", project_id)
        if project_id not in self.project_cache:
            # project is not exist in cache
            return

        pools = self.get_project_pools(project_id)
        for pl in pools:
            pool_configured_members = []
            pool_configured_members = self.source.get_members_by_pool_id(pl.id)
            # maybe use it this way: pl["members"]
            pl.members = pool_configured_members
