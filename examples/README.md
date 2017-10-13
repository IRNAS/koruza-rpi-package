# KORUZA tracking algorithm beta
This is experimental software for auto-tracking of KORUZA units. Be advised you are using this at your own risk and the use of this software may result in hardware malfunction or damage and void the warranty.


## Installing the tracking algorithm
SSH into your unit and run the appropriate commands.

First make sure you are running the latest KORUZA firmware:

```
sudo koruza-upgrade
```

Install required dependencies:
```
sudo apt-get install python-requests
```

First configure remote unit IP and reboot:
```
sudo uci set koruza.@network[0].peer=<remote units IP address>
sudo uci commit koruza
sudo reboot
```

go to home directory and clone repository:

```
git clone https://github.com/IRNAS/koruza-rpi-package
```
enter directory of the repo
```
cd koruza-rpi-package/
```
switch to development branch
```
git checkout tracking_dev
```
run to make sure you are on the latest version or to update at a later stage
```
git pull origin
```

To run the algorithm use the following command
```
sudo systemctl start koruza-alignment
```

To stop the algorithm use the following command
```
sudo systemctl stop koruza-alignment
```

To see the real-time log
```
tail -f examples/alignment.log
```
