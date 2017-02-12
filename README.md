KORUZA Software Package
=======================

To build the software package for the ARM-based KORUZA compute module, you
need a working Docker installation. Then run the following:
```
./build.sh
```

After the build process completes, you get everything packaged in a Debian
package called `koruza_1.0-1.deb`. To install or upgrade the package, run
the following on the KORUZA compute module:
```
sudo dpkg -i koruza_1.0-1.deb
```

