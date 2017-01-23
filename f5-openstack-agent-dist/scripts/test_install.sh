#!/bin/bash -ex

OS_TYPE=$1
OS_VERSION=$2
PKG_FULLNAME=$3
PKG_NAME="f5-openstack-agent"
DIST_DIR="${PKG_NAME}-dist"

BUILD_CONTAINER="${OS_TYPE}${OS_VERSION}-${PKG_NAME}-pkg-tester"
WORKING_DIR="/var/wdir"

if [[ ${OS_TYPE} == "redhat" ]]; then
	CONTAINER_TYPE="centos${OS_VERSION}"
elif [[ ${OS_TYPE} == "ubuntu" ]]; then
	if [[ ${OS_VERSION} == "14.04" ]]; then
		CONTAINER_TYPE="trusty"
	else
		echo "Only Trusty release currently supported"
		exit 1
	fi
else
	echo "Unsupported target OS (${OS_TYPE})"
	exit 1
fi

DOCKER_DIR="${DIST_DIR}/Docker/${OS_TYPE}/install_test"
DOCKER_FILE="${DOCKER_DIR}/Dockerfile.${CONTAINER_TYPE}"

docker build -t ${BUILD_CONTAINER} -f ${DOCKER_FILE} ${DOCKER_DIR}
docker run --privileged --rm -v $(pwd):${WORKING_DIR} ${BUILD_CONTAINER} /usr/bin/python \
	   /fetch_and_install_deps.py ${WORKING_DIR} ${PKG_FULLNAME}

exit 0
