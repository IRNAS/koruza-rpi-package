#!/bin/sh
set -e

deb-systemd-invoke stop koruza-driver.service >/dev/null || true
deb-systemd-invoke stop sfp-driver.service >/dev/null || true
deb-systemd-invoke stop ubus.service >/dev/null || true
