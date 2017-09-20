from __future__ import print_function

import os
import json
import math
import subprocess
import sys
import time
import requests
import logging


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
                logging.warning("Sending local command: {} {} {}".format(object_name, method, parameters))
                response = subprocess.check_output([
                    'ubus',
                    'call',
                    object_name,
                    method,
                    json.dumps(parameters)
                ]).strip()
                logging.warning("Command sent: {}...".format(response[:30]))

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
class Spiral_scan(object):
    N_CIRCLE = 20
    BACKLASH = 130  # Backlash
    STEP = 10

    def __init__(self):
        """Initialise all variables"""

        self.backlash = [0, 0]  # Movement direction
        self.initial_position = [0, 0]  # Innitial position - middle of the square
        self.step = [0, 0] # Steps
        self.new_position = [0, 0]  # New position
        self.dir = 1  # Direction of motion

        self.point_count = 0  # Points count
        self.n_points = 0  # Number of points on the line
        self.coordinate_count = 0  # Coordinates
        self.circle_count = 0  # Count half circles
        self.state = 0  # States
        self.Run = True

    def run(self, x, y, rx_local, rx_remote):

        # Check if requested position was reached
        if self.state > 0 and self.check_move(x, y):
            logging.info("%d %d %f %f\n" % (self.step[0], self.step[1], rx_local, rx_remote))
            file.write("%d %d %f %f\n" % (self.step[0], self.step[1], rx_local, rx_remote))

        elif self.state > 0 and not self.check_move(x, y):
            logging.info("POSITION NOT REACHED, RE-SEND!\n")

            return self.new_position[0], self.new_position[1], self.Run

        # STATE 0: Initialise
        if self.state == 0:

            self.initial_position = [x, y]
            self.new_position = [x, y]
            # Initialise movement direction
            self.backlash_x = 0
            self.backlash_y = 0
            self.state = 1
            self.point_count = 0
            self.n_points = 1

            return x, y, self.Run

        # STATE 1: initialise
        elif self.state == 1:

            # Update steps - line scanned
            if self.point_count == self.n_points:

                # Re-set points count
                self.point_count = 0

                # Check if both lines are scanned
                if self.coordinate_count == 1:
                    self.circle_count += 1  # Update half-circle count

                    # Check if scanning is complete - EXIT
                    if self.circle_count == 2 * Spiral_scan.N_CIRCLE:

                        # Move to initial position
                        self.Run = False
                        return self.initial_position[0], self.initial_position[1], self.Run

                    # Update points
                    else:
                        self.dir *= -1  # Change direction
                        self.n_points += 1 # Increase points count

                # Update coordinate count
                self.coordinate_count = (self.coordinate_count + 1) % 2

                # Update backlash
                if self.dir < 0:
                    self.backlash[self.coordinate_count] = 1

            # Move
            self.point_count += 1  # Increase points count
            self.step[self.coordinate_count] += self.dir * Spiral_scan.STEP  # Update steps
            # New position
            self.new_position[self.coordinate_count] = self.initial_position[self.coordinate_count] + self.step[
                self.coordinate_count] - self.backlash[self.coordinate_count] * Spiral_scan.BACKLASH

            return self.new_position[0], self.new_position[1], self.Run


    def check_move(self, x, y):
        if self.new_position[0] == x and self.new_position[1] == y:
            return True
        else:
            return False


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
scan = Spiral_scan()
Run = True

# Open log file
logging.basicConfig(filename='scan.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)
# Open output file
file = open('scan_output.txt','w')

# Processing loop.
print("INFO: Starting processing loop.")
time.sleep(2)


while Run:
    # Get remote unit's status.
    try:
        remote_status = remote.get_status()
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        print("WARNING: Network error while waiting for remote unit.")
        logging.warning("WARNING: Network error while waiting for remote unit.")
        continue
    except KoruzaAPIError, error:
        print("WARNING: API error ({}) while requesting remote status.".format(error))
        logging.warning("WARNING: API error ({}) while requesting remote status.".format(error))
        continue

    # Get local unit's status.
    try:
        local_status = local.get_status()
    except KoruzaAPIError, error:
        print("WARNING: API error ({}) while requesting local status.".format(error))
        logging.warning("WARNING: API error ({}) while requesting local status.".format(error))
        continue

    remote_rx_power_mw = remote_status['sfp']['rx_power'] / 10000.
    remote_rx_power_dbm = mw_to_dbm(remote_rx_power_mw)
    local_rx_power_mw = local_status['sfp']['rx_power'] / 10000.
    local_rx_power_dbm = mw_to_dbm(local_rx_power_mw)
    local_motors = local_status['motors']
    local_x, local_y = local_motors['x'], local_motors['y']
    remote_motors = remote_status['motors']
    remote_x, remote_y = remote_motors['x'], remote_motors['y']
    distance = local_status['camera_calibration']['distance']

    target_x, target_y, Run = scan.run(local_x, local_y, local_rx_power_dbm, remote_rx_power_dbm)

    target = (target_x, target_y)

    # Check if we need to move.
    current = (local_x, local_y)
    if current == target:
        # logging.info("INFO: Already at target coordinates.")
        continue

    # Move local motors.
    while True:
        try:
            local.move_motor(*target)
            break
        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while requesting local move.".format(error))
            logging.warning("WARNING: API error ({}) while requesting local move.".format(error))

    last_coordinates = (local_x, local_y)
    last_coordinates_same = None
    stuck_times = 0
    while True:
        try:
            # Check if target reached.
            current_motors = local.get_status()['motors']
            current = (current_motors['x'], current_motors['y'])

            if current == target:
                logging.info("INFO: Target coordinates reached.\n")
                time.sleep(0.5)
                break

            if last_coordinates != current:
                last_coordinates_same = None
            elif last_coordinates_same is None:
                last_coordinates_same = time.time()

            last_coordinates = current

            # Check for stuck motors (coordinates didn't change in the last 5s).
            if last_coordinates_same is not None and time.time() - last_coordinates_same > 30:
                last_coordinates_same = None
                print("WARNING: Motors stuck when trying to reach target coordinates.")
                logging.warning("WARNING: Motors stuck when trying to reach target coordinates.")

                stuck_times += 1
                if stuck_times > 10:
                    logging.warning("Stuck more than 10 times. Aborting current move.")
                    break

                logging.warning("Resending move command.")

                while True:
                    try:
                        local.move_motor(*target)
                        break
                    except KoruzaAPIError, error:
                        print("WARNING: API error ({}) while requesting local move.".format(error))
                        logging.warning("WARNING: API error ({}) while requesting local move.".format(error))

                continue
        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while confirming local move.".format(error))
            logging.warning("WARNING: API error ({}) while confirming local move.".format(error))
