# KORUZA examples

Install required dependencies:
```
sudo apt-get install python-requests
```

To run the API example, just specify the remote unit's hostname as an argument:
```
sudo python api_example.py <remote_host>
```

## Development
To test run the scripts do the following one-time when developing on a new KORUZA unit:
```
sudo apt-get install python-requests
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

To run the latest script run the following:
```
git pull origin && sudo nohup python examples/alignment.py <remote_host> &
tail -f alignment.log
```
