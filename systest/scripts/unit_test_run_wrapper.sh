#! /usr/bin/env bash
export TAGINFO=`git describe --long --tags --first-parent`
export TIMESTAMP=`date +"%Y%m%d-%H%M%S"`
export SESSIONLOGDIR=${TAGINFO}_$TIMESTAMP
export STAGENAME=f5-openstack-agent_mitaka-unit
export COVRESULTS=\
/testlab/openstack/testresults/coverage/$STAGENAME/$SESSIONLOGDIR
sudo -E docker run -v `pwd`:/home/jenkins/f5-openstack-agent \
docker-registry.pdbld.f5net.com/openstack-test-agentunitrunner-prod/mitaka \
$STAGENAME $SESSIONLOGDIR
mkdir -p $COVRESULTS
cp f5_openstack_agent/.coverage $COVRESULTS
