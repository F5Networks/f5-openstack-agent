#!/bin/bash -ex

SRC_DIR=$1
pushd $SRC_DIR
PKG_VERSION=$(python -c "import f5_openstack_agent; print(f5_openstack_agent.__version__)")

PKG_NAME="f5-openstack-agent"

TMP_DIST="/var/deb_dist"
OS_VERSION="1404"
DIST_DIR="f5-openstack-agent-dist/deb_dist"

echo "Building ${PKG_NAME} debian packages..."

cp -R "${SRC_DIR}/${DIST_DIR}/stdeb.cfg" .
cp -R "${SRC_DIR}/${DIST_DIR}" ${TMP_DIST}

python setup.py --command-packages=stdeb.command sdist_dsc  --dist-dir=${TMP_DIST}
pushd "${TMP_DIST}/${PKG_NAME}-${PKG_VERSION}"
dpkg-buildpackage -rfakeroot -uc -us
popd; popd

pkg="python-${PKG_NAME}_${PKG_VERSION}-1_all.deb"
cp "${TMP_DIST}/${pkg}" "${SRC_DIR}/${DIST_DIR}/${pkg%%_all.deb}_${OS_VERSION}_all.deb"
