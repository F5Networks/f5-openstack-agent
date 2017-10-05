#!/usr/bin/env bash

set -ex
export PYTHONDONTWRITEBYTECODE=1

# - JOB_NAME is provided by Jenkins (eg. "openstack/agent/liberty/unit-tests")
export CI_PROGRAM=$(echo $JOB_NAME | cut -d "/" -f 1)
export CI_PROJECT=$(echo $JOB_NAME | cut -d "/" -f 2)
export CI_BRANCH=$(echo $JOB_NAME | cut -d "/" -f 3)
export PROJ_HASH=$(git rev-parse HEAD | xargs)

job_dirname="${CI_PROGRAM}.${CI_PROJECT}.${CI_BRANCH}.${JOB_BASE_NAME}"
export build_dirname="${JOB_BASE_NAME}-${BUILD_ID}"
export CI_RESULTS_DIR="/home/jenkins/results/${job_dirname}/${build_dirname}"
export CI_BUILD_SUMMARY="${CI_RESULTS_DIR}/ci-build.yaml"
export PYTHONDONTWRITEBYTECODE=1

# BEGIN COVERAGE REPORTING SECTION
# The following logic enables combined coverage reporting.
covbase="/testlab/openstack/testresults/coverage/${CI_PROJECT}/${CI_BRANCH}/${PROJ_HASH}"
mkdir -p ${covbase}
COVPREFIX="[run]\n"\
"omit = \n"\
"\t/*/f5_openstack_agent/lbaasv2/drivers/bigip/test/*\n"\
"\t/*/f5_openstack_agent/tests/*\n"\
"\n"\
"[paths]\n"\
"paths = \n"\
"\t${covbase}/source_code\n"\
"\t/*/f5-openstack-agent\n"\
"\t/*/dist-packages\n"\
"\t/*/site-packages"

if [ ! -f "${covbase}/.coveragerc"  ]; then
    echo ${COVPREFIX} > ${covbase}/.coveragerc
fi
if grep --quiet -e"${JOB_BASE_NAME}" ${covbase}/.coveragerc; then
    echo "Path already mapped."
else
    echo "\t/*/${JOB_BASE_NAME}" >> ${covbase}/.coveragerc
fi
if [ ! -d "${covbase}/source_code" ]; then
    TEMPTAG=temptag_${PROJ_HASH}
    git tag -f ${TEMPTAG}
    git clone -b ${TEMPTAG} --depth=1 --single-branch `pwd` ${covbase}/source_code
    pushd ${covbase}/source_code && git checkout -b ${CI_BRANCH} && popd
fi

export COVERAGERESULTS="${covbase}/${BUILD_ID}_${JOB_BASE_NAME}"
cp ${covbase}/.coveragerc ./.coveragerc

# END COVERAGE REPORTING SECTION

# - source this job's environment variables
export CI_ENV_FILE=systest/${JOB_BASE_NAME}.env
if [ -e $CI_ENV_FILE ]; then
    . $CI_ENV_FILE
fi
