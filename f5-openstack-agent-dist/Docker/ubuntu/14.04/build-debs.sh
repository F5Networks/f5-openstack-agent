#!/bin/bash -ex

SRC_DIR=$1

PKG_NAME="f5-openstack-agent"
OS_VERSION="1404"
DIST_DIR="f5-openstack-agent-dist/deb_dist"

# Change directory to the source to get package information.
pushd ${SRC_DIR}

# The version is embedded in the package.
PKG_VERSION=$(python -c "import f5_openstack_agent; print(f5_openstack_agent.__version__)")
PKG_RELEASE=$(python ./f5-openstack-agent-dist/scripts/get-version-release.py --release)

# Exit source directory
popd

# Create a temporary work directory and copy the source to it.
BUILDROOT=$(mktemp -d /tmp/${PKG_NAME}.XXXXX)
cp -R ${SRC_DIR}/* ${BUILDROOT}
pushd ${BUILDROOT}

echo "Building ${PKG_NAME} debian packages..."

# Copy the stdeb.cfg file to the current directory and add the pkg release to it.
cp -R "${SRC_DIR}/${DIST_DIR}/stdeb.cfg" .
echo "Debian-Version: ${PKG_RELEASE}" >> stdeb.cfg

# Build debian package.
python setup.py --command-packages=stdeb.command sdist_dsc
pushd "deb_dist/${PKG_NAME}-${PKG_VERSION}"
dpkg-buildpackage -rfakeroot -uc -us
popd

pkg="python-${PKG_NAME}_${PKG_VERSION}-${PKG_RELEASE}_all.deb"
cp "deb_dist/${pkg}" "${SRC_DIR}/${DIST_DIR}/${pkg%%_all.deb}_${OS_VERSION}_all.deb"
