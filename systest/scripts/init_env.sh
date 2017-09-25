#!/usr/bin/env bash

set -ex

# - JOB_NAME is provided by Jenkins (eg. "openstack/agent/liberty/unit-tests")
export CI_PROGRAM=$(echo $JOB_NAME | cut -d "/" -f 1)
export CI_PROJECT=$(echo $JOB_NAME | cut -d "/" -f 2)
export CI_BRANCH=$(echo $JOB_NAME | cut -d "/" -f 3)
export PROJ_HASH=$(git rev-parse HEAD | xargs)

job_dirname="${CI_PROGRAM}.${CI_PROJECT}.${CI_BRANCH}.${JOB_BASE_NAME}"
export build_dirname="${JOB_BASE_NAME}-${BUILD_ID}"
covsuffix="${CI_PROJECT}/${CI_BRANCH}/${PROJ_HASH}/${build_dirname}"
export COVERAGERESULTS=/testlab/openstack/testresults/coverage/${covsuffix}
export CI_RESULTS_DIR="/home/jenkins/results/${job_dirname}/${build_dirname}"
export CI_BUILD_SUMMARY="${CI_RESULTS_DIR}/ci-build.yaml"
export PYTHONDONTWRITEBYTECODE=1

# - source this job's environment variables
export CI_ENV_FILE=systest/${JOB_BASE_NAME}.env
if [ -e $CI_ENV_FILE ]; then
    . $CI_ENV_FILE
fi

# - print env vars
