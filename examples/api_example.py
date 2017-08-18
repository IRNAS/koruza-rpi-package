from __future__ import print_function

import os
import json
import math
import subprocess
import sys
import time

import requests


class KoruzaAPIError(Exception):
    """KORUZA API error."""
    pass


class KoruzaAPI(object):
    """KORUZA API."""
    STATUS_OK = 0
    STATUS_INVALID_COMMAND = 1
    STATUS_INVALID_ARGUMENT = 2
    STATUS_METHOD_NOT_FOUND = 3
    STATUS_NOT_FOUND = 4
    STATUS_NO_DATA = 5
    STATUS_PERMISSION_DENIED = 6
    STATUS_TIMEOUT = 7
    STATUS_NOT_SUPPORTED = 8
    STATUS_UNKNOWN_ERROR = 9
    STATUS_CONNECTION_FAILED = 10

    SESSION_NULL = '00000000000000000000000000000000'

    LOCAL_HOST = 'localhost'

    def __init__(self, host, port=80, path='/ubus'):
        """Construct API instance."""
        self.host = host
        self.port = port
        self.path = path
        self._session = KoruzaAPI.SESSION_NULL

    def _call(self, object_name, method, parameters=None):
        """Raw call to API method."""
        if parameters is None:
            parameters = {}

        if self.host == KoruzaAPI.LOCAL_HOST:
            # Special handling for local commands.
            try:
                response = subprocess.check_output([
                    'ubus',
                    'call',
                    object_name,
                    method,
                    json.dumps(parameters)
                ]).strip()

                if response:
                    return json.loads(response)

                return {}
            except subprocess.CalledProcessError, error:
                raise KoruzaAPIError(error.returncode)
            except ValueError:
                raise KoruzaAPIError("Parse error")
        else:
            payload = {
                'jsonrpc': '2.0',
                'method': 'call',
                'id': 1,
                'params': [self._session, object_name, method, parameters],
            }
            response = requests.post(
                'http://{}:{}{}'.format(self.host, self.port, self.path),
                data=json.dumps(payload),
                headers={'content-type': 'application/json'},
                timeout=5,
            ).json()

            if 'result' in response:
                code = response['result'][0]
                if code == KoruzaAPI.STATUS_OK:
                    return response['result'][1]
                else:
                    raise KoruzaAPIError(code)
            elif 'error' in response:
                raise KoruzaAPIError(response['error']['code'])

    def login(self, username, password):
        """Authenticate to the remote host.

        Authentication is only required for specific requests. Some requests
        may be performed without authentication. Local commands do not require
        authentication.
        """
        if self.host == KoruzaAPI.LOCAL_HOST:
            return

        response = self._call('session', 'login', {
            'username': username,
            'password': password,
            'timeout': 3600,
        })
        self._session = response['ubus_rpc_session']

    def logout(self):
        """Close session."""
        if self.host == KoruzaAPI.LOCAL_HOST:
            return

        self._call('session', 'destroy', {'session': self._session})
        self._session = KoruzaAPI.SESSION_NULL

    def get_status(self):
        """Get general KORUZA unit status.

        Authentication is not required.
        """
        return self._call('koruza', 'get_status')

    def get_sfp_modules(self):
        """Get SFP module information.

        Authentication is not required.
        """
        return self._call('sfp', 'get_modules')

    def get_sfp_diagnostics(self):
        """Get SFP diagnostics information (including RX/TX power).

        Authentication is not required.
        """
        return self._call('sfp', 'get_diagnostics')

    def move_motor(self, x, y):
        """Move motors.

        Authentication is required.
        """
        return self._call('koruza', 'move_motor', {'x': x, 'y': y, 'z': 0})


def mw_to_dbm(value):
    """Convert mW value to dBm."""

    value_dbm = 10 * math.log10(value)
    if value_dbm < -40:
        value_dbm = -40

    return value_dbm

if len(sys.argv) < 2:
    print("ERROR: Please specify KORUZA unit host.")
    sys.exit(1)

if os.getuid() != 0:
    print("ERROR: Must be run as root.")
    sys.exit(1)

local = KoruzaAPI(KoruzaAPI.LOCAL_HOST)
remote = KoruzaAPI(sys.argv[1])

# Processing loop.
print("INFO: Starting processing loop.")
while True:
    # Get remote unit's status.
    try:
        remote_status = remote.get_status()
    except requests.exceptions.Timeout:
        print("WARNING: Timeout while waiting for remote unit.")
        continue
    except KoruzaAPIError, error:
        print("WARNING: API error ({}) while requesting remote status.".format(error))
        continue

    # Get local unit's status.
    try:
        local_status = local.get_status()
    except KoruzaAPIError, error:
        print("WARNING: API error ({}) while requesting local status.".format(error))
        continue

    remote_rx_power_mw = remote_status['sfp']['rx_power'] / 10000.
    remote_rx_power_dbm = mw_to_dbm(remote_rx_power_mw)
    local_rx_power_mw = local_status['sfp']['rx_power'] / 10000.
    local_rx_power_dbm = mw_to_dbm(local_rx_power_mw)
    local_motors = local_status['motors']
    local_x, local_y = local_motors['x'], local_motors['y']
    distance = local_status['camera_calibration']['distance']

    print("INFO: Distance:", distance)
    print("INFO: Remote SFP RX power (dBm):", remote_rx_power_dbm)
    print("INFO: Local SFP RX power (dBm):", local_rx_power_dbm)
    print("INFO: Local motor position (x, y):", local_x, local_y)

    # Decide where to move based on current coordinates.
    target_x = min(15000, local_x + 100)
    target_y = min(15000, local_y + 100)
    target = (target_x, target_y)

    # Check if we need to move.
    current = (local_x, local_y)
    if current == target:
        continue

    # Move local motors.
    print("INFO: Moving motors to ({}, {}).".format(*target))

    while True:
        try:
            local.move_motor(*target)
            break
        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while requesting local move.".format(error))

    last_coordinates = (local_x, local_y)
    last_coordinates_same = None
    while True:
        try:
            # Check if target reached.
            current_motors = local.get_status()['motors']
            current = (current_motors['x'], current_motors['y'])

            if current == target:
                print("INFO: Target coordinates reached.")
                break

            if last_coordinates != current:
                last_coordinates_same = None
            elif last_coordinates_same is None:
                last_coordinates_same = time.time()

            last_coordinates = current

            # Check for stuck motors (coordinates didn't change in the last 5s).
            if last_coordinates_same is not None and time.time() - last_coordinates_same > 5000:
                print("WARNING: Motors stuck when trying to reach target coordinates.")
                break
        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while confirming local move.".format(error))
