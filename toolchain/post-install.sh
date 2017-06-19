#!/bin/sh
set -e

deb-systemd-helper enable ubus.service >/dev/null || true
deb-systemd-helper enable rpcd.service >/dev/null || true
deb-systemd-helper enable uhttpd.service >/dev/null || true
deb-systemd-helper enable sfp-driver.service >/dev/null || true
deb-systemd-helper enable koruza-driver.service >/dev/null || true
deb-systemd-helper enable mjpg-streamer.service >/dev/null || true
deb-systemd-helper enable nodewatcher-agent.service >/dev/null || true
deb-systemd-helper enable motor-test.service >/dev/null || true
systemctl --system daemon-reload >/dev/null || true
deb-systemd-invoke start ubus.service >/dev/null || true
deb-systemd-invoke start rpcd.service >/dev/null || true
deb-systemd-invoke start uhttpd.service >/dev/null || true
deb-systemd-invoke start sfp-driver.service >/dev/null || true
deb-systemd-invoke start koruza-driver.service >/dev/null || true
deb-systemd-invoke start mjpg-streamer.service >/dev/null || true
deb-systemd-invoke start nodewatcher-agent.service >/dev/null || true
deb-systemd-invoke start motor-test.service >/dev/null || true

# Enable hostapd and udhcpd.
update-rc.d hostapd enable || true
update-rc.d udhcpd enable || true

# Reset rc.local in case it contains test-homing directives.
grep -q test-homing /etc/rc.local && {
  echo '#!/bin/sh -e' > /etc/rc.local
}
