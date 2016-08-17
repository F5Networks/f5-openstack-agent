#!/usr/bin/python

import os
import re
import subprocess
import sys

f5_sdk_version_pattern = re.compile("^\s*Depends:\s+(?:.*)python-f5-sdk\s+\(=\s*(.*)\)(?:.*)$")
f5_icr_version_pattern = re.compile("^\s*Depends:\s+(?:.*)python-f5-icontrol-rest\s+\(=\s*(.*)\)(?:.*)$")

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
    agent_pkg = "python-f5-openstack-agent_%s-%s_1404_all.deb" % (version, release)

    # Copy agent package to /tmp
    cpCmd = "cp %s/deb_dist/%s /tmp" % (dist_dir, agent_pkg)
    print "Copying agent package to /tmp install directory"
    (output, status) = runCommand(cpCmd)
    if status != 0:
        print "Failed to copy python-f5-openstack-agent package"
    else:
        print "Success"

    # Get the sdk requirement.
    requiresCmd = "dpkg -I %s/deb_dist/%s" % (dist_dir, agent_pkg)
    print "Getting dependencies for %s." % (agent_pkg)
    (output, status) = runCommand(requiresCmd)

    if status != 0:
        print "Can't get package dependencies for %s" % (agent_pkg)
        return 1
    else:
        print "Success"
    
    for line in output.split('\n'):
        m = f5_sdk_version_pattern.match(line)
        if m:
            f5_sdk_version = m.group(1).strip(' ')
            break

    if not f5_sdk_version:
        print "Can't find f5-sdk dependency for %s" % (agent_pkg)
        return 1

    (f5_sdk_version, f5_sdk_release) = f5_sdk_version.split('-')

    # Fetch the sdk package
    github_sdk_url = (
        "https://github.com/F5Networks/f5-common-python/releases/download/v%s" % (
            f5_sdk_version)
    )
    f5_sdk_pkg = "python-f5-sdk_%s-1_1404_all.deb" % (f5_sdk_version)
    curlCmd = (
        "curl -L -o /tmp/%s %s/%s" % (
            f5_sdk_pkg, github_sdk_url, f5_sdk_pkg) )

    print "Fetching f5-sdk package from github"
    (output, status) = runCommand(curlCmd)

    # Get the icontrol rest dependency
    requiresCmd = "dpkg -I /tmp/%s" % (f5_sdk_pkg)
    print "Getting dependencies for %s." % (f5_sdk_pkg)
    (output, status) = runCommand(requiresCmd)
    if status != 0:
        print "Failed to to get requirements for %s." % (f5_sdk_pkg)
        return 1
    else:
        print "Success"

    for line in output.split('\n'):
        m = f5_icr_version_pattern.match(line)
        if m:
            f5_icr_version = m.group(1)
            break
    if not f5_icr_version:
        print "Can't find f5-sdk dependency for %s" % (f5_sdk_pkg)
        return 1
    print f5_icr_version
    (f5_icr_version, f5_icr_release) = f5_icr_version.split('-')

    # Fectch the icontrol rest package
    github_icr_url = (
        "https://github.com/F5Networks/f5-icontrol-rest/releases/download/v%s" % (
            f5_icr_version)
    )
    f5_icr_pkg = "python-f5-icontrol-rest_%s-1_1404_all.deb" % (f5_icr_version)
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

    return [f5_icr_pkg, f5_sdk_pkg, agent_pkg]

def install_agent_pkgs(repo, pkg_list):
    for pkg in pkg_list:
        installCmd = "dpkg -i /tmp/%s" % (pkg)
        print "Installing: %s" % (pkg)
        (output, status) = runCommand(installCmd)
    if status != 0:
        print "Agent install failed"
        sys.exit(1)
    else:
        print "Success"

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
    packages = fetch_agent_dependencies(dist_dir, version, release)

    # Instal from the tmp directory.
    install_agent_pkgs("/tmp", packages)


if __name__ == '__main__':
    main(sys.argv)
