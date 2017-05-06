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


---

#### License

All our projects are as usefully open-source as possible.

Hardware including documentation is licensed under [CERN OHL v.1.2. license](http://www.ohwr.org/licenses/cern-ohl/v1.2)

Firmware and software originating from the project is licensed under [GNU GENERAL PUBLIC LICENSE v3](http://www.gnu.org/licenses/gpl-3.0.en.html).

Open data generated by our projects is licensed under [CC0](https://creativecommons.org/publicdomain/zero/1.0/legalcode).

All our websites and additional documentation are licensed under [Creative Commons Attribution-ShareAlike 4 .0 Unported License] (https://creativecommons.org/licenses/by-sa/4.0/legalcode).

What this means is that you can use hardware, firmware, software and documentation without paying a royalty and knowing that you'll be able to use your version forever. You are also free to make changes but if you share these changes then you have to do so on the same conditions that you enjoy.

Koruza, GoodEnoughCNC and IRNAS are all names and marks of Institut IRNAS Rače.
You may use these names and terms only to attribute the appropriate entity as required by the Open Licences referred to above. You may not use them in any other way and in particular you may not use them to imply endorsement or authorization of any hardware that you design, make or sell.
