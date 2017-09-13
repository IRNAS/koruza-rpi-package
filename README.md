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

If you get some missing dependencies, be sure to also run:
```bash
sudo apt-get -f install
```

## Motor homing tests

In order to run continuous motor homing test every time the compute module
is rebooted, run the following and reboot the device:
```bash
sudo uci set koruza.@motors[0].test=1
sudo uci commit koruza
```

To disable the tests later:
```bash
sudo uci set koruza.@motors[0].test=0
sudo uci commit koruza
```

## Configuring a serial number

In order to configure a serial number for the unit (e.g., `0001`) run:
```bash
sudo uci set koruza.@unit[0].serial_number=0001
```

If this command gives you an invalid argument error, run the following:
```bash
sudo uci add koruza unit
sudo uci set koruza.@unit[0].serial_number=0001
```

Commit the changes by running:
```
sudo uci commit koruza
```


## Configuring monitoring push location

In order to configure the URL where the unit should push data (e.g., for `push.kw.koruza.net`), run:
```bash
sudo uci set nodewatcher.@agent[0].push_url_template=https://push.kw.koruza.net/push/http/{uuid}
sudo uci commit nodewatcher
```

---

#### License

Firmware and software originating from KORUZA Pro project, including KORUZA Software Package (koruza-rpi-package), is licensed under [GNU GENERAL PUBLIC LICENSE v3](https://www.gnu.org/licenses/gpl-3.0.en.html).

What this means is that you can use this firmware and software without paying a royalty and knowing that you'll be able to use your version forever. You are also free to make changes but if you share these changes then you have to do so on the same conditions that you enjoy.

KORUZA, KORUZA Pro and IRNAS are all names and marks of Institute IRNAS Rače. You may use these names and terms only to attribute the appropriate entity as required by the Open Licence referred to above. You may not use them in any other way and in particular you may not use them to imply endorsement or authorization of any hardware that you design, make or sell.
