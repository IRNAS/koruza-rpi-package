#!/bin/sh
set -e

deb-systemd-helper enable ubus.service >/dev/null || true
deb-systemd-helper enable sfp-driver.service >/dev/null || true
deb-systemd-helper enable koruza-driver.service >/dev/null || true
systemctl --system daemon-reload >/dev/null || true
deb-systemd-invoke start ubus.service >/dev/null || true
deb-systemd-invoke start sfp-driver.service >/dev/null || true
deb-systemd-invoke start koruza-driver.service >/dev/null || true
