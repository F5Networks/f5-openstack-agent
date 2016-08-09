#!/usr/bin/python

import os
import re
import subprocess
import sys

f5_sdk_pattern = re.compile("^f5-sdk\s*=\s*(\d+\.\d+\.\d+)$")
f5_icontrol_rest_pattern = re.compile(
    "^f5-icontrol-rest\s*=\s*(\d+\.\d+\.\d+)$")


def usage():
    print "fetch_dependencies.py working_dir"

def runCommand(cmd):
    output = ""
    print " -- %s" % (cmd)
    try:
        p = subprocess.Popen(cmd.split(),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (output) = p.communicate()[0]
    except OSError, e:
        print >>sys.stderr, "Execution failed: ",e

    return (output, p.returncode)

def fetch_agent_dependencies(dist_dir, version, release):
    agent_pkg = "f5-openstack-agent-%s-%s.el7.noarch.rpm" % (version, release)

    # Copy agent package to /tmp
    cpCmd = "cp %s/rpms/build/%s /tmp" % (dist_dir, agent_pkg)
    print "Copying agent package to /tmp install directory"
    (output, status) = runCommand(cpCmd)
    if status != 0:
        print "Failed to copy f5-openstack-agent package"
    else:
        print "Success"

    # Get the sdk requirement.
    requiresCmd = "rpm -qRp %s/rpms/build/%s" % (dist_dir, agent_pkg)
    print "Getting dependencies for %s." % (agent_pkg)
    (output, status) = runCommand(requiresCmd)

    if status != 0:
        print "Can't get package dependencies for %s" % (agent_pkg)
        return 1
    else:
        print "Success"
    
    for line in output.split('\n'):
        m = f5_sdk_pattern.match(line)
        if m:
            f5_sdk_version = m.group(1)
            break

    if not f5_sdk_version:
        print "Can't find f5-sdk dependency for %s" % (agent_pkg)
        return 1

    # Fetch the sdk package
    github_sdk_url = (
        "https://github.com/F5Networks/f5-common-python/releases/download/v%s" % (
            f5_sdk_version)
    )
    f5_sdk_pkg = "f5-sdk-%s-1.el7.noarch.rpm" % (f5_sdk_version)
    curlCmd = (
        "curl -L -o /tmp/%s %s/f5-sdk-%s-1.el7.noarch.rpm" % (
            f5_sdk_pkg, github_sdk_url, f5_sdk_version) )

    print "Fetching f5-sdk package from github"
    (output, status) = runCommand(curlCmd)

    # Get the icontrol rest dependency
    requiresCmd = "rpm -qRp /tmp/%s" % (f5_sdk_pkg)
    print "Getting dependencies for %s." % (f5_sdk_pkg)
    (output, status) = runCommand(requiresCmd)
    if status != 0:
        print "Failed to to get requirements for %s." % (f5_sdk_pkg)
        return 1
    else:
        print "Success"

    for line in output.split('\n'):
        m = f5_icontrol_rest_pattern.match(line)
        if m:
            f5_icr_version = m.group(1)
            break
    if not f5_sdk_version:
        print "Can't find f5-sdk dependency for %s" % (f5_sdk_pkg)
        return 1

    # Fectch the icontrol rest package
    github_icr_url = (
        "https://github.com/F5Networks/f5-icontrol-rest/releases/download/v%s" % (
            f5_icr_version)
    )
    f5_icr_pkg = "f5-icontrol-rest-%s-1.el7.noarch.rpm" % (f5_icr_version)
    curlCmd = (
        "curl -L -o /tmp/%s %s/%s" % (
            f5_icr_pkg, github_icr_url, f5_icr_pkg) )

    print "Fetching f5-icontrol-reset package from github"
    (output, status) = runCommand(curlCmd)

    if status != 0:
        print "Failed to to fetch f5-icontrol-rest package."
        return 1
    else:
        print "Success"

def install_agent_pkgs(repo):
    installCmd = "rpm -ivh /tmp/*.rpm"
    (output, status) = runCommand(installCmd)
    if status != 0:
        print "Agent install failed"
        sys.exit(1)
    

def main(args):
    if len(args) != 2:
        usage()
        sys.exit(1)

    working_dir = os.path.normpath(args[1])
    try:
        os.chdir("/var/wdir")
    except OSError, e:
        print >>sys.stderr, "Can't change to directory %s (%s)" %  (working_dir, e)

    dist_dir = os.path.join(working_dir, "f5-openstack-agent-dist")
    version_tool = os.path.join(dist_dir, "scripts/get-version-release.py")

    cmd = "%s --version --release" % (version_tool)
    (output, status) = runCommand(cmd)
    if status == 0:
        (version, release) = output.rstrip().split()

    # Get all files for the f5-openstack agent.
    fetch_agent_dependencies(dist_dir, version, release)

    # Instal from the tmp directory.
    install_agent_pkgs("/tmp")


if __name__ == '__main__':
    main(sys.argv)
