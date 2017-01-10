#!/bin/bash

set -e

BUILD_DIR=build
INSTALL_ROOT=${BUILD_DIR}/install-root

rpxc_install()
{
  ./bin/rpxc install-raspbian $*
}

rpxc()
{
  local cmd="$1"
  ./bin/rpxc sh -c "${cmd}"
}

cmake_build()
{
  local directory="$1"
  local config="$2"

  echo "Building '${directory}'."
  rm -rf ${BUILD_DIR}/${directory}/build
  mkdir -p ${BUILD_DIR}/${directory}/build
  rpxc "cd ${BUILD_DIR}/${directory}/build && cmake -DCMAKE_TOOLCHAIN_FILE=../../../toolchain/toolchain-rpi.cmake -DCMAKE_INSTALL_PREFIX=/build/${BUILD_DIR}/install-root/usr ${config} .. && make && make install"
}

install_file()
{
  local file="$1"
  local target="$2"
  mkdir -p ${INSTALL_ROOT}/$(dirname ${target})
  cp toolchain/${file} ${INSTALL_ROOT}/${target}
}

fetch_git()
{
  local repository="$1"
  local target="$2"
  git clone "${repository}" "${BUILD_DIR}/${target}"
}

echo "Preparing builder image."
rpxc_install $(cat toolchain/packages-buildtime.txt) $(cat toolchain/packages-runtime.txt)

# Clean build directory.
echo "Cleaning build directory."
rm -rf ${BUILD_DIR}
mkdir ${BUILD_DIR}

# Fetch packages.
echo "Fetching sources."
fetch_git https://git.lede-project.org/project/libubox.git libubox
fetch_git https://git.lede-project.org/project/ubus.git ubus
fetch_git https://git.lede-project.org/project/uci.git uci
fetch_git https://git.lede-project.org/project/rpcd.git rpcd
fetch_git https://git.lede-project.org/project/uhttpd.git uhttpd
fetch_git https://github.com/IRNAS/koruza-driver.git koruza-driver
fetch_git https://github.com/IRNAS/sfp-driver.git sfp-driver
fetch_git https://github.com/IRNAS/koruza-ui.git koruza-ui

# Build packages.
echo "Building packages."
cmake_build libubox "-DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF"
cmake_build ubus "-DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF"
cmake_build uci "-DBUILD_LUA=OFF"
cmake_build rpcd "-DFILE_SUPPORT=OFF -DIWINFO_SUPPORT=OFF -DRPCSYS_SUPPORT=OFF '-DCMAKE_C_FLAGS=-idirafter /rpxc/sysroot/usr/include -L/build/build/install-root/usr/lib'"
cmake_build uhttpd "-DLUA_SUPPORT=OFF -DTLS_SUPPORT=OFF '-DCMAKE_C_FLAGS=-idirafter /rpxc/sysroot/usr/include -L/build/build/install-root/usr/lib'"
cmake_build koruza-driver
cmake_build sfp-driver

# Install UI.
echo "Installing UI."
mkdir -p ${INSTALL_ROOT}/srv/www
cp -a ${BUILD_DIR}/koruza-ui/dist/* ${INSTALL_ROOT}/srv/www/
cp ${BUILD_DIR}/koruza-ui/src/favicon.ico ${INSTALL_ROOT}/srv/www/

# Copy configuration files.
echo "Copying configuration files."
install_file ubus.service lib/systemd/system/ubus.service
install_file rpcd.service lib/systemd/system/rpcd.service
install_file uhttpd.service lib/systemd/system/uhttpd.service
install_file sfp-driver.service lib/systemd/system/sfp-driver.service
install_file koruza-driver.service lib/systemd/system/koruza-driver.service
install_file unauthenticated-acl.json usr/share/rpcd/acl.d/unauthenticated.json
install_file koruza-driver-acl.json usr/share/rpcd/acl.d/koruza-driver.json
install_file sfp-driver-acl.json usr/share/rpcd/acl.d/sfp-driver.json
install_file koruza.config etc/config/koruza
install_file rpcd.config etc/config/rpcd

# Inject dpkg metadata.
echo "Building package."
mkdir ${INSTALL_ROOT}/DEBIAN
cp toolchain/control ${INSTALL_ROOT}/DEBIAN/control
cp toolchain/post-install.sh ${INSTALL_ROOT}/DEBIAN/postinst
cp toolchain/pre-remove.sh ${INSTALL_ROOT}/DEBIAN/prerm
cp toolchain/post-remove.sh ${INSTALL_ROOT}/DEBIAN/postrm
dpkg-deb --build ${INSTALL_ROOT} koruza_1.0-1.deb
