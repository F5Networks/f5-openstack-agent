#!/usr/bin/python

from __future__ import print_function

import glob
import os
import re
import subprocess
import sys

from collections import deque, namedtuple

dep_match_re = \
    re.compile('^((python|f5-sdk|f5-icontrol-rest)[\w\-]*)' +
               '\s([<>=]{1,2})\s(\S+)')


def usage():
    print("fetch_dependencies.py working_dir")


def runCommand(cmd):
    output = ""
    print(" -- %s" % (cmd))
    try:
        p = subprocess.Popen(cmd.split(),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (output) = p.communicate()[0]
    except OSError as e:
        print("Execution failed: ", e, file=sys.stderr)
    return (output, p.returncode)


def fetch_agent_dependencies(dist_dir, version, release, agent_pkg):
    # agent_pkg = "f5-openstack-agent-%s-%s.el7.noarch.rpm" % (version, release)
    ReqDetails = namedtuple('ReqDetails', 'name, oper, version')
    requires = deque()
    # Copy agent package to /tmp
    cpCmd = "cp %s /tmp" % agent_pkg
    print("Copying agent package to /tmp install directory")
    (output, status) = runCommand(cpCmd)
    if status != 0:
        print("Failed to copy f5-openstack-agent package")
    else:
        print("Success")

    # Get the sdk requirement.
    requiresCmd = "rpm -qRp %s" % agent_pkg
    agent_pkg_base = os.path.basename(agent_pkg)
    print("Getting dependencies for %s." % agent_pkg_base)
    (output, status) = runCommand(requiresCmd)

    if status != 0:
        print("Can't get package dependencies for %s" % agent_pkg_base)
        return 1
    else:
        print("Success")

    for line in output.split('\n'):
        print(line, dep_match_re.pattern)
        match = dep_match_re.match(line)
        if match:
            groups = list(match.groups())
            my_dep = ReqDetails(groups[0], groups[2], groups[3])
            if 'f5-sdk' in my_dep.name:
                f5_sdk_version = my_dep.version
            else:
                requires.append(my_dep)

    # we know we will always need this...
    if not f5_sdk_version:
        print("Can't find f5-sdk dependency for %s" % (agent_pkg))
        return 1

    # Check if the required packages are present, then install the ones we are
    # aware of...
    # grab the sdk's:
    sdk_github_addr = \
        "https://github.com/F5Networks/f5-common-python/releases/download/v%s"
    github_sdk_url = (sdk_github_addr % f5_sdk_version)
    f5_sdk_pkg = "f5-sdk-%s-1.el7.noarch.rpm" % (f5_sdk_version)
    curlCmd = ("curl -L -o /tmp/%s %s/f5-sdk-%s-1.el7.noarch.rpm" %
               (f5_sdk_pkg, github_sdk_url, f5_sdk_version))

    print("Fetching f5-sdk package from github")
    (output, status) = runCommand(curlCmd)

    # Get the icontrol rest dependency
    requiresCmd = "rpm -qRp /tmp/%s" % (f5_sdk_pkg)
    print("Getting dependencies for %s." % (f5_sdk_pkg))
    (output, status) = runCommand(requiresCmd)
    if status != 0:
        print("Failed to to get requirements for %s." % (f5_sdk_pkg))
        return 1
    else:
        print("Success")

    sdk_reqs = deque()  # can use later in a loop-through to validate compliance
    for line in output.split('\n'):
        m = dep_match_re.search(line)
        if m:
            groups = m.groups()
            my_dep = ReqDetails(groups[0], groups[2], groups[3])
            if 'f5-icontrol-rest' in my_dep.name:
                if re.search('^>?=', my_dep.oper):
                    f5_icr_version = my_dep.version
            else:
                sdk_reqs.append(my_dep)
    if not f5_icr_version:
        print("Can't find f5-sdk dependency for %s" % (f5_sdk_pkg))
        return 1

    # Fectch the icontrol rest package
    github_icr_url = \
        ("https://github.com/F5Networks/f5-icontrol-rest/releases/download/v%s"
         % f5_icr_version)
    f5_icr_pkg = "f5-icontrol-rest-%s-1.el7.noarch.rpm" % (f5_icr_version)
    curlCmd = ("curl -L -o /tmp/%s %s/%s" %
               (f5_icr_pkg, github_icr_url, f5_icr_pkg))

    print("Fetching f5-icontrol-reset package from github")
    (output, status) = runCommand(curlCmd)

    if status != 0:
        print("Failed to to fetch f5-icontrol-rest package.")
        return 1
    else:
        print("Success on F5 Libraries")
    return check_other_dependencies(requires, dist_dir, agent_pkg)


def check_other_dependencies(requires, dist_dir, agent_pkg):
    # triage the packages already installed
    rpm_list_cmd = "rpm -qa"
    print("Collecting a list of already-install pkgs")
    (output, status) = runCommand(rpm_list_cmd)
    to_get = deque()
    ignore = []
    while requires:
        my_dep = requires.popleft()
        if my_dep.name not in output and my_dep.name not in ignore:
            to_get.append(my_dep)
    # install the repo-stored rpm's
    print("Grabbing the ones we have copies of")
    to_install = glob.glob(dist_dir + "/Docker/redhat/7/*.rpm")
    for rpm_file in to_install:
        for rpm_dep in to_get:
            if rpm_dep.name in rpm_file:
                to_get.remove(rpm_dep)
        rpm_install_cmd = "rpm -i %s" % rpm_file
        runCommand(rpm_install_cmd)
    if to_get:
        print("WARNING: there are missing dependencies!")
        while to_get:
            dep = to_get.popleft()
            print("%s %s %s" % (dep.name, dep.oper, dep.version))
    else:
        print("""Succsess!
All dependencies search satisfied!  However, by-version check may still fail...
""")
    # change to be dynamic if we decide to be more rigorous at this stage...
    return 0


def install_agent_pkgs(repo):
    installCmd = "rpm -ivh /tmp/*.rpm"
    (output, status) = runCommand(installCmd)
    if status != 0:
        print("Agent install failed")
        sys.exit(1)


def main(args):
    if len(args) != 3:
        usage()
        sys.exit(1)

    working_dir = os.path.normpath(args[1])
    pkg_fullname = args[2]
    try:
        os.chdir("/var/wdir")
    except OSError as e:
        print("Can't change to directory %s (%s)" % (working_dir, e),
              file=sys.stderr)

    dist_dir = os.path.join(working_dir, "f5-openstack-agent-dist")
    version_tool = os.path.join(dist_dir, "scripts/get-version-release.py")

    cmd = "%s --version --release" % (version_tool)
    (output, status) = runCommand(cmd)
    if status == 0:
        (version, release) = output.rstrip().split()

    # Get all files for the f5-openstack agent.
    fetch_agent_dependencies(dist_dir, version, release, pkg_fullname)

    # Instal from the tmp directory.
    install_agent_pkgs("/tmp")


if __name__ == '__main__':
    main(sys.argv)
