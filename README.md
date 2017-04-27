# KORUZA Software Package

To build the software package for the ARM-based KORUZA compute module, you
need a working Docker installation. Then run the following:
```bash
./build.sh
```

After the build process completes, you get everything packaged in a Debian
package called `koruza_1.0-1.deb`. To install or upgrade the package, run
the following on the KORUZA compute module:
```bash
sudo dpkg -i koruza_1.0-1.deb
```

## Motor homing tests

In order to run continuous motor homing test every time the compute module
is rebooted, add the following to `/etc/rc.local`, just above `exit 0`:
```bash
# Run homing tests.
{
  sleep 30
  while true; do
    test-homing quiet >> /var/log/koruza-test-homing.log
    sleep 1
  done
} &
```
