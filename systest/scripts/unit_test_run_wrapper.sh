#! /usr/bin/env bash
export TAGINFO=`git describe --long --tags --first-parent`
export TIMESTAMP=`date +"%Y%m%d-%H%M%S"`
# This is approximately the same as GUMBALLS_SESSION
export SESSIONLOGDIR=${TAGINFO}_$TIMESTAMP

export STAGENAME=f5-openstack-agent_mitaka-unit
pwd
ls -l
sudo -E docker pull  docker-registry.pdbld.f5net.com/openstack-test-agentunitrunner-prod/mitaka
sudo -E docker run -u jenkins -v `pwd`:/home/jenkins/f5-openstack-agent \
docker-registry.pdbld.f5net.com/openstack-test-agentunitrunner-prod/mitaka:latest \
$STAGENAME $SESSIONLOGDIR
mkdir -p ${COVERAGERESULTS}
mv .coverage ${COVERAGERESULTS}/.coverage_unit
