# KORUZA Software Package

To set-up a system running the KORUZA software package one may choose vuilding from the latest source or using a pre-compiled binary.

## Install with pre-compiled binary
To install a pre-compiled binary a Raspberry Pi device is required, by default Raspberry Pi Compute Module (V1 or V3), but versions should work if correct GPIO pins are configured for different features. Install Raspbian Lite operating system, configure it correctly and then install the pre-compiled package:

```
wget https://github.com/IRNAS/koruza-rpi-package/releases/download/stable/koruza.deb
sudo dpkg -i koruza.deb
```

Once package is installed, it can be simply upgraded running:
```
sudo koruza-upgrade
```
which will fetch the latest stable release and install it.

## Build from source

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

## Configuring webcam zoom and flip

To enable image flipping, run:
```bash
sudo uci set koruza.@webcam[0].flip=1  # 0 to disable.
```

The webcam image is automatically centered on the calibrated position (requires restart). To change
the zoom in X and/or Y direction, run:
```bash
sudo uci set koruza.@webcam[0].zoom_w=0.4  # X direction.
sudo uci set koruza.@webcam[0].zoom_h=0.4  # Y direction.
```

Commit the changes by running:
```
sudo uci commit koruza
```

After making the modifications either reboot the device or restart the `mjpg-streamer` service:
```
sudo systemctl restart mjpg-streamer
```

## Manually capturing video or images from the webcam
You can capture video and images manuall from koruza unit using the following method, see [this link](https://www.raspberrypi.org/documentation/usage/camera/raspicam/raspivid.md) for more information on using the raspivid command.

```
sudo systemctl stop mjpg-streamer
sudo raspivid -o vid.h264
sudo systemctl start mjpg-streamer
```
## Setting a static IP address:
The static IP address can be configured by establishing an ssh connection to the unit `pi@<ip address>` with default password `raspberry`.

Then use the following command to edit config:

```sudo nano /etc/dhcpcd.conf```
 and copy paste this, editting the settings:
 
 ```
 interface eth0

static ip_address=192.168.0.10/24
static routers=192.168.0.1
static domain_name_servers=192.168.0.1
```
then reboot by issuing `sudo reboot`

---

#### License

Firmware and software originating from KORUZA Pro project, including KORUZA Software Package (koruza-rpi-package), is licensed under [GNU GENERAL PUBLIC LICENSE v3](https://www.gnu.org/licenses/gpl-3.0.en.html).

What this means is that you can use this firmware and software without paying a royalty and knowing that you'll be able to use your version forever. You are also free to make changes but if you share these changes then you have to do so on the same conditions that you enjoy.

KORUZA, KORUZA Pro and IRNAS are all names and marks of Institute IRNAS Rače. You may use these names and terms only to attribute the appropriate entity as required by the Open Licence referred to above. You may not use them in any other way and in particular you may not use them to imply endorsement or authorization of any hardware that you design, make or sell.
