#!/bin/bash

set -e

BUILD_DIR=build
INSTALL_ROOT=${BUILD_DIR}/install-root

rpxc_install()
{
  ./bin/rpxc install-raspbian --update $*
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
  rpxc "sudo ln -s /rpxc/sysroot/opt/vc /opt/vc && cd ${BUILD_DIR}/${directory}/build && cmake -DCMAKE_TOOLCHAIN_FILE=../../../toolchain/toolchain-rpi.cmake -DCMAKE_INSTALL_PREFIX=/build/${BUILD_DIR}/install-root/usr ${config} .. && make && make install"
}

install_file()
{
  local file="$1"
  local target="$2"
  mkdir -p ${INSTALL_ROOT}/$(dirname ${target})
  cp toolchain/${file} ${INSTALL_ROOT}/${target}
}

install_script()
{
  local file="$1"
  local target="$2"
  install_file "$1" "$2"
  chmod +x ${INSTALL_ROOT}/${target}
}

fetch_git()
{
  local repository="$1"
  local target="$2"
  local commit="$3"

  git clone "${repository}" "${BUILD_DIR}/${target}"
  if [ -n "${commit}" ]; then
    cd "${BUILD_DIR}/${target}"
    git checkout ${commit}
    cd -
  fi
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
fetch_git https://git.lede-project.org/project/uci.git uci 49ec6efbdac4819033d34f08927d795f83a3932d
fetch_git https://git.lede-project.org/project/rpcd.git rpcd
fetch_git https://git.lede-project.org/project/uhttpd.git uhttpd e6cfc911811b904494776938a480e0b77a14124a
fetch_git https://github.com/IRNAS/koruza-driver.git koruza-driver 0c52277e07fc6ba9cc825f6e912e98a98e1cd51b
fetch_git https://github.com/IRNAS/sfp-driver.git sfp-driver 4ed293576a672fefb8425c1f971f0f71523e6c1d
fetch_git https://github.com/IRNAS/koruza-ui.git koruza-ui 968013b96458d87c9fc88e646646895faf4053d7
fetch_git https://github.com/IRNAS/mjpg-streamer.git mjpg-streamer de5e2577c181dce21942eec4af020fce554b1647
fetch_git https://github.com/wlanslovenija/nodewatcher-agent.git nodewatcher-agent
fetch_git https://github.com/IRNAS/koruza-nodewatcher-agent.git koruza-nodewatcher-agent
fetch_git https://github.com/IRNAS/sfp-nodewatcher-agent.git sfp-nodewatcher-agent 898e8c7ec6b9ecd1f9f8449a0b354ccc5d51282b

# Build packages.
echo "Building packages."
cmake_build libubox "-DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF"
cmake_build ubus "-DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF"
cmake_build uci "-DBUILD_LUA=OFF"
cmake_build rpcd "-DFILE_SUPPORT=OFF -DIWINFO_SUPPORT=OFF -DRPCSYS_SUPPORT=OFF '-DCMAKE_C_FLAGS=-idirafter /rpxc/sysroot/usr/include -L/build/build/install-root/usr/lib'"
cmake_build uhttpd "-DLUA_SUPPORT=OFF -DTLS_SUPPORT=OFF '-DCMAKE_C_FLAGS=-idirafter /rpxc/sysroot/usr/include -L/build/build/install-root/usr/lib'"
cmake_build koruza-driver
cmake_build sfp-driver
cmake_build mjpg-streamer/mjpg-streamer-experimental "'-DCMAKE_C_FLAGS=-idirafter /rpxc/sysroot/usr/include -idirafter /rpxc/sysroot/usr/include/arm-linux-gnueabihf -L/build/build/install-root/usr/lib'"
cmake_build nodewatcher-agent "-DWIRELESS_MODULE=OFF -DINTERFACES_MODULE=OFF -DPACKAGES_MODULE=OFF -DCLIENTS_MODULE=OFF -DROUTING_BABEL_MODULE=OFF -DROUTING_OLSR_MODULE=OFF -DKEYS_SSH_MODULE=OFF"
cmake_build koruza-nodewatcher-agent
cmake_build sfp-nodewatcher-agent

# Install UI.
echo "Installing UI."
mkdir -p ${INSTALL_ROOT}/srv/www
cp -a ${BUILD_DIR}/koruza-ui/dist/* ${INSTALL_ROOT}/srv/www/
cp ${BUILD_DIR}/koruza-ui/src/favicon.ico ${INSTALL_ROOT}/srv/www/

# Install debug scripts.
mkdir ${INSTALL_ROOT}/srv/www/info
install_script debug/ip srv/www/info/ip
install_script debug/homing srv/www/info/homing
install_script debug/encoders srv/www/info/encoders

# Install MCU firmware and package upgrade scripts.
echo "Installing MCU upgrade scripts."
install_script mcu-reset usr/bin/mcu-reset
install_script mcu-upgrade-firmware usr/bin/mcu-upgrade-firmware
install_script koruza-upgrade usr/bin/koruza-upgrade

# Install test scripts.
echo "Installing test scripts."
install_script test-homing usr/bin/test-homing

# Install helper scripts.
echo "Installing helper scripts."
install_script koruza-identify usr/bin/koruza-identify
install_script webcam-position usr/bin/webcam-position

# Copy configuration files.
echo "Copying configuration files."
install_file ubus.service lib/systemd/system/ubus.service
install_file rpcd.service lib/systemd/system/rpcd.service
install_file uhttpd.service lib/systemd/system/uhttpd.service
install_file sfp-driver.service lib/systemd/system/sfp-driver.service
install_file koruza-driver.service lib/systemd/system/koruza-driver.service
install_file mjpg-streamer.service lib/systemd/system/mjpg-streamer.service
install_file nodewatcher-agent.service lib/systemd/system/nodewatcher-agent.service
install_file motor-test.service lib/systemd/system/motor-test.service
install_file unauthenticated-acl.json usr/share/rpcd/acl.d/unauthenticated.json
install_file koruza-driver-acl.json usr/share/rpcd/acl.d/koruza-driver.json
install_file sfp-driver-acl.json usr/share/rpcd/acl.d/sfp-driver.json
install_file system.config etc/config/system
install_file nodewatcher.config etc/config/nodewatcher
install_file koruza.config etc/config/koruza
install_file rpcd.config etc/config/rpcd

# Inject dpkg metadata.
echo "Building package."
mkdir ${INSTALL_ROOT}/DEBIAN
cp toolchain/control ${INSTALL_ROOT}/DEBIAN/control
cp toolchain/conffiles ${INSTALL_ROOT}/DEBIAN/conffiles
cp toolchain/post-install.sh ${INSTALL_ROOT}/DEBIAN/postinst
cp toolchain/pre-remove.sh ${INSTALL_ROOT}/DEBIAN/prerm
cp toolchain/post-remove.sh ${INSTALL_ROOT}/DEBIAN/postrm

VERSION=$(grep Version toolchain/control | awk '{print $2}')
dpkg-deb --build ${INSTALL_ROOT} koruza_${VERSION}.deb
