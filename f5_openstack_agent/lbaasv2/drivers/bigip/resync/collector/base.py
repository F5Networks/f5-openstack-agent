# -*- coding: utf-8 -*-


class Collector(object):

    def __init__(self, source):
        self.source = source

    def get_project_loadbalancers(project_id, *args, **kwargs):
        """Get loadbalancers by a project_id.

        """
        pass

    def get_project_listeners(project_id, *args, **kwargs):
        """Get listeners by a project_id.

        """
        pass

    def get_project_pools(project_id, *args, **kwargs):
        """Get pools by a project_id.

        """
        pass

    def get_project_members(project_id, *args, **kwargs):
        """Get members by a project_id.

        """
        pass

    def get_project_healthmonitor(project_id, *args, **kwargs):
        """Get healthmonitor by a project_id.

        """
        pass
