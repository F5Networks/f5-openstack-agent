#!/bin/bash -ex

SRC_DIR=$1

PKG_NAME="f5-openstack-agent"
DIST_DIR="${PKG_NAME}-dist"
RPMBUILD_DIR="rpmbuild"
OS_VERSION=7
DEST_DIR="${SRC_DIR}/${DIST_DIR}"
PRE_INSTALL_SCRIPT=${DIST_DIR}/rpms/scripts/f5-openstack-agent-preinstall.sh

# The version is embedded in the package.
pushd ${SRC_DIR}
PKG_VERSION=$(python -c "import f5_openstack_agent; print(f5_openstack_agent.__version__)")
PKG_RELEASE=$(python ./f5-openstack-agent-dist/scripts/get-version-release.py --release)
popd

echo "Building ${PKG_NAME} RPM packages..."

# Create a temporary work directory and copy the source to it.
buildroot=$(mktemp -d /tmp/${PKG_NAME}.XXXXX)
cp -R $SRC_DIR/* ${buildroot}
pushd ${buildroot}

# Add 'Release to the setup.cfg file'
echo "release = ${PKG_RELEASE}" >> ./setup.cfg

# Setup the RPM build area.
python setup.py build bdist_rpm --rpm-base rpmbuild

# Modify the config to point to the new build area.
echo "%_topdir ${buildroot}/rpmbuild" > ~/.rpmmacros

# Create a .spec file to use as the package template.
python setup.py bdist_rpm --spec-only --dist-dir rpmbuild/SPECS --pre-install ${PRE_INSTALL_SCRIPT}
echo "%config /etc/neutron/services/f5/f5-openstack-agent.ini" >> rpmbuild/SPECS/f5-openstack-agent.spec

rpmbuild -ba rpmbuild/SPECS/f5-openstack-agent.spec

mkdir -p ${DEST_DIR}/rpms/build

for pkg in $(ls rpmbuild/RPMS/noarch/*.rpm); do
  if [[ $pkg =~ ".noarch." ]]; then
    mv $pkg ${pkg%%.noarch.rpm}.el${OS_VERSION}.noarch.rpm
  fi
done
cp -R rpmbuild/RPMS/noarch/*.rpm ${DEST_DIR}/rpms/build

popd

#rm -rf ${buildroot}

