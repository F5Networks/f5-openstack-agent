# -*- coding: utf-8 -*-


class LbaasToBigIP(object):

    def __init__(self, benchmark, benchmark_filter):

        self.benchmark_name = None
        self.benchmark = None
        self.benchmark_filter = None
        self.benchmark_projects = None

        self.subject_name = None
        self.subject = None
        self.subject_filter = None
        self.subject_projects = None

        self.validate_subject(benchmark)
        self.init_benchmark(benchmark, benchmark_filter)

    def compare_to(self, subject, subject_filter):
        self.validate_subject(subject)
        self.init_subject(subject, subject_filter)

    def validate_subject(self, subject):
        if not isinstance(subject, dict):
            raise Exception("Comparator must be a dcit type")
        if len(subject) != 1:
            raise Exception("Only one Comparator should be "
                            "provided at a time")

    def init_subject(self, subject, subject_filter):
        self.subject_name = subject.keys()[0]
        self.subject = subject.values()[0]

        self.subject_filter = subject_filter
        projects = self.subject.get_projects_on_device()
        self.subject_projects = self.subject_filter.get_ids(
            projects
        )

    def init_benchmark(self, benchmark, benchmark_filter):
        self.benchmark_name = benchmark.keys()[0]
        self.benchmark = benchmark.values()[0]
        self.benchmark_filter = benchmark_filter

        projects = \
            self.benchmark.get_projects_on_device()
        self.benchmark_projects = set(projects)

    def get_common_resources_diff(self, bm_method, sub_method):
        bm_resources = []
        sub_resources = []

        for project in self.benchmark_projects:
            bm_resources += bm_method(
                project
            )

        bm_lbs_ids = self.benchmark_filter.get_ids(
            bm_resources)

        for project in self.subject_projects:
            sub_resources += sub_method(
                project
            )

        sub_lbs_ids = self.subject_filter.get_ids(
            sub_resources)

        diff = bm_lbs_ids - sub_lbs_ids
        return list(diff)

    def get_missing_projects(self):
        diff = self.benchmark_projects - self.subject_projects
        return list(diff)

    def get_missing_loadbalancers(self):
        bm_method = self.benchmark.get_project_loadbalancers
        sub_method = self.subject.get_project_loadbalancers
        diff = self.get_common_resources_diff(
            bm_method, sub_method
        )

        return diff

    def get_missing_listeners(self):
        bm_method = self.benchmark.get_project_listeners
        sub_method = self.subject.get_project_listeners
        diff = self.get_common_resources_diff(
            bm_method, sub_method
        )
        return diff

    def get_missing_pools(self):
        bm_method = self.benchmark.get_project_pools
        sub_method = self.subject.get_project_pools
        diff = self.get_common_resources_diff(
            bm_method, sub_method
        )
        return diff

    def get_missing_members(self):
        bm_pools = []
        sub_pools = []
        missing_mb = []

        for project in self.benchmark_projects:
            bm_pools += self.benchmark.get_project_pools(
                project
            )

        bm_mbs = self.benchmark_filter.filter_pool_members(bm_pools)

        for project in self.subject_projects:
            sub_pools += self.subject.get_project_pools(
                project
            )

        sub_mbs = self.subject_filter.filter_pool_members(sub_pools)

        for k, v in bm_mbs.items():
            if k not in sub_mbs:
                if v:
                    missing_mb.append({k: v})
                continue

            mbs = []
            for mb in v:
                if not mb["address_port"] in sub_mbs[k]:
                    mbs.append(mb)
                if mbs:
                    missing_mb.append({k: mbs})

        return missing_mb
