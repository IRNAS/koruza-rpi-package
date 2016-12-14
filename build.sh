#!/bin/bash

BUILD_DIR=build

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
  mkdir -p ${BUILD_DIR}/install-root/$(dirname ${target})
  cp toolchain/${file} ${BUILD_DIR}/install-root/${target}
}

fetch_git()
{
  local repository="$1"
  local target="$2"
  git clone "${repository}" "${BUILD_DIR}/${target}"
}

# Clean build directory.
echo "Cleaning build directory."
rm -rf ${BUILD_DIR}
mkdir ${BUILD_DIR}

# Fetch packages.
echo "Fetching sources."
fetch_git https://git.lede-project.org/project/libubox.git libubox
fetch_git https://git.lede-project.org/project/ubus.git ubus
fetch_git https://git.lede-project.org/project/uci.git uci
fetch_git https://github.com/IRNAS/koruza-driver.git koruza-driver
fetch_git https://github.com/IRNAS/sfp-driver.git sfp-driver

# Build packages.
echo "Building packages."
cmake_build libubox "-DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF"
cmake_build ubus "-DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF"
cmake_build uci "-DBUILD_LUA=OFF"
cmake_build koruza-driver
cmake_build sfp-driver

# Copy configuration files.
echo "Copying configuration files."
install_file ubus.service lib/systemd/system/ubus.service
install_file sfp-driver.service lib/systemd/system/sfp-driver.service

# Inject dpkg metadata.
echo "Building package."
mkdir ${BUILD_DIR}/install-root/DEBIAN
cp toolchain/control ${BUILD_DIR}/install-root/DEBIAN/control
dpkg-deb --build ${BUILD_DIR}/install-root koruza_1.0-1.deb

