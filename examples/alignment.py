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

# Tracking class
class Tracking(object):

    N_SCAN_POINTS = 9
    N_MES = 10
    N_STOP = 3 # Number of consecitive times maximum is found at the center

    def __init__(self):
        """Initialise all variables"""
        self.step = 100 # Step size
        self.scan_points_x = [0, -self.step, -self.step, -self.step, 0, self.step, self.step, self.step, 0] # Steps circle scan
        self.scan_points_y = [0, -self.step, 0, self.step, self.step, self.step, 0, -self.step, -self.step]
        self.next_step_x = 0 # Steps direction line scan
        self.next_step_y = 0
        self.initial_position_x = 0 # Innitial position
        self.initial_position_y = 0
        self.local_rx_power_dBm = [0]*Tracking.N_SCAN_POINTS # Local power log
        self.remote_rx_power_dBm = [0]*Tracking.N_SCAN_POINTS # Remote power log
        self.count = 0 # Points count
        self.meas_count = 0 # Measurement count
        self.stop_count = 0 # Number of consecitive times maximum is found at the center
        self.state = 0 # States

    def run(self, x, y, rx_local, rx_remote):

        # STATE 0: monitoring
        if self.state == 0:
            self.state = 1
            print("ALIGNMENT: Alignment started!\n")
            time.sleep(2)
            return x, y

        # STATE 1: initialise
        elif self.state == 1:
            # save initial position
            self.initial_position_x = x
            self.initial_position_y = y
            # Determine step size
            if rx_remote < -25:
                self.step = 300
            else:
                self.step = 100

            # Re-set step size
            self.scan_points_x = [0, -self.step, -self.step, -self.step, 0, self.step, self.step, self.step, 0] # Steps circle scan
            self.scan_points_y = [0, -self.step, 0, self.step, self.step, self.step, 0, -self.step, -self.step]
            # Record initial readings in state 3
            self.state = 3
            # print("ALIGNMENT: Initialise.")
            time.sleep(2)
            return x, y

        # STATE 2: scanning
        elif self.state == 2:

            # Increase count
            self.count += 1
            # Go to measurement state
            self.state = 3

            # Check if all points have been scanned - find max value position
            if self.count == Tracking.N_SCAN_POINTS:
                self.state = 4 # Go to re-set state
                self.count = self.find_max_value()
                print("\n ALIGNMENT: Optimal position found at %d! \n" % self.count)

            # Define new position
            x_new = self.initial_position_x + self.scan_points_x[self.count]
            y_new = self.initial_position_y + self.scan_points_y[self.count]
            print("ALIGNMENT: Go to (x, y):", x_new, y_new)
            time.sleep(2)

            return x_new, y_new

        # STATE 3: wait for 10 measurements, calculate average
        elif self.state == 3:
            # Add new measurements
            self.local_rx_power_dBm[self.count] += rx_local
            self.remote_rx_power_dBm[self.count] += rx_remote
            # print("ALIGNMENT: Reading %d position %d, local: %f remote: %f " % (self.meas_count, self.count, rx_local, rx_remote))
            time.sleep(0.1)
            self.meas_count += 1 # Increment

            # Check if 10 measurements are obtained
            if self.meas_count == Tracking.N_MES:
                self.meas_count = 0 # Reset
                self.state = 2 # Go to moving state
                # Calculate average
                self.local_rx_power_dBm[self.count] = self.local_rx_power_dBm[self.count]/Tracking.N_MES
                self.remote_rx_power_dBm[self.count] = self.remote_rx_power_dBm[self.count]/Tracking.N_MES
                print("%f %f %f %f " % (x, y, self.local_rx_power_dBm[self.count], self.remote_rx_power_dBm[self.count]))
                time.sleep(2)

            return x,y

        # STATE 4: check stopping conditions
        if self.state == 4:
            # go to idle or continue alignment
            print("Check stopping conditions!")

            # Check stopping condition
            if self.count == 0:
                self.stop_count += 1 # Max found at the starting point
            else:
                self.stop_count = 0 # Re-set stop condition

            # Check if stopping condition was reached
            if self.stop_count == Tracking.N_STOP:
                self.state = 5 # Go to idle
                self.stop_count = 0
            else:
                self.state = 6 # Re-set and continue

            return x,y

        # STATE 5: Idle
        if self.state == 5:
            print("Idle state.")

            # Check re-starting conditions
            # self.state = 6 #Re-start algorithm
            time.sleep(10)
            return x,y

        # STATE 6: re-set
        else:
            # print("Re-set.")
            self.state = 0
            self.reset_measurements()

            return x,y

    def reset_measurements(self):
        """Reset rx power and point count"""
        for i in range(Tracking.N_SCAN_POINTS):
            self.local_rx_power_dBm[i] = 0
            self.remote_rx_power_dBm[i] = 0
        self.count = 0 # Reset points count
        self.meas_count = 0 # Reset measurements count

    def find_max_value(self):
        """Find max scanned signal"""
        max_rx = -40
        pos = 0
        for i in range(Tracking.N_SCAN_POINTS):
            new_rx = self.get_combined_power(self.local_rx_power_dBm[i], self.remote_rx_power_dBm[i])
            if new_rx > max_rx:
                max_rx = new_rx
                pos = i
        return pos


    def get_combined_power(self, rx_local, rx_remote):
        """Combine signal from local and remote unit based on the distance"""
        max_rx = rx_remote
        return max_rx

def mw_to_dbm(value):
    """Convert mW value to dBm."""

    if value > 0:
        value_dbm = 10 * math.log10(value)
    else:
        value_dbm = -40
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
alignment = Tracking()


# Processing loop.
print("INFO: Starting processing loop.")
time.sleep(2)
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

    # print("INFO: Distance:", distance)
    # print("INFO: Remote SFP RX power (dBm):", remote_rx_power_dbm)
    # print("INFO: Local SFP RX power (dBm):", local_rx_power_dbm)
    # print("INFO: Local motor position (x, y):", local_x, local_y)

    target_x, target_y = alignment.run(local_x, local_y, local_rx_power_dbm, remote_rx_power_dbm)
    # print("ALIGNMENT: Return value (x, y):", target_x, target_y)

    # Decide where to move based on current coordinates.
    # target_x = min(15000, local_x + 100)
    # target_y = min(15000, local_y + 100)
    target = (target_x, target_y)
    # print("TARGET: Return value (x, y):", target_x, target_y)

    # Check if we need to move.
    current = (local_x, local_y)
    if current == target:
        # print("\n")
        continue

    # Move local motors.
    # print("INFO: Moving motors to ({}, {}).\n".format(*target))
    time.sleep(2)

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
                # print("INFO: Target coordinates reached.")
                break

            if last_coordinates != current:
                last_coordinates_same = None
            elif last_coordinates_same is None:
                last_coordinates_same = time.time()

            last_coordinates = current

            # Check for stuck motors (coordinates didn't change in the last 5s).
            if last_coordinates_same is not None and time.time() - last_coordinates_same > 30:
                print("WARNING: Motors stuck when trying to reach target coordinates.")
                break
        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while confirming local move.".format(error))