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
                # logging.warning("Sending local command: {} {} {}".format(object_name, method, parameters))
                response = subprocess.check_output([
                    'ubus',
                    'call',
                    object_name,
                    method,
                    json.dumps(parameters)
                ]).strip()
                # logging.warning("Command sent: {}".format(response))

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

    def set_alignment(self, state, variables):
        """Set alignment state.
        Authentication is required.
        """
        return self._call('koruza', 'set_alignment', {'state': state, 'variables': variables})


# Backlash class
class Backlash(object):
    BACKLASH = 130  # Backlash

    def __init__(self):
        """Initialise all variables"""

        self.backlash_x = 0  # Movement direction
        self.backlash_y = 0

        self.new_position_x = 0  # New position
        self.new_position_y = 0

        self.old_position_x = 0  # Prev position
        self.old_position_y = 0

    # Initialise backlash by moving forward for backlash value
    def init_backlash(self, x, y):

        self.new_position_x = x + Backlash.BACKLASH
        self.new_position_y = y + Backlash.BACKLASH
        self.old_position_x = self.new_position_x
        self.old_position_y = self.new_position_y
        self.backlash_x = 0
        self.backlash_y = 0

        return self.new_position_x, self.new_position_y

    # Get position without backlash, return position with backlash
    def backlash_forward(self, x, y):

        # Update new position
        self.new_position_x = x
        self.new_position_y = y

        # Calculate move
        dx = self.new_position_x - self.old_position_x
        dy = self.new_position_y - self.old_position_y

        # Determine backlash
        if dx < 0:
            self.backlash_x = 1
        elif dx > 0:
            self.backlash_x = 0

        if dy < 0:
            self.backlash_y = 1
        elif dy > 0:
            self.backlash_y = 0

        # Update old position
        self.old_position_x = self.new_position_x
        self.old_position_y = self.new_position_y

        return self.new_position_x - self.backlash_x * Backlash.BACKLASH, self.new_position_y - self.backlash_y * Backlash.BACKLASH

    # Get motor position with backlash, convert to position without based on the current state
    def backlash_inverse(self, x, y):

        return x + self.backlash_x * Backlash.BACKLASH, y + self.backlash_y * Backlash.BACKLASH

    def reset_position(self, x, y):

        self.new_position_x = x
        self.new_position_y = y
        self.old_position_x = x
        self.old_position_y = y


# Tracking class
class Tracking(object):
    N_SCAN_POINTS = 9
    N_SCAN_POINTS_IDLE = 5
    N_MES = 5
    N_STOP = 3  # Number of consecitive times maximum is found at the center
    N_IDLE = 25  # Number of averaged mesurments in idle state
    TIMEOUT = 1000  # Timeout for single alignment session
    MIN_STEP = 50
    MAX_STEP = 100
    IDLE_STEP = 25

    def __init__(self):
        """Initialise all variables"""

        self.backlash = Backlash()  # Backlash class

        self.step = Tracking.MIN_STEP  # Step size
        self.n_points = Tracking.N_SCAN_POINTS  # Number of points to scan
        self.scan_points_x = [0, -self.step, -self.step, -self.step, 0, self.step, self.step, self.step,
                              0]  # Steps circle scan
        self.scan_points_y = [0, -self.step, 0, self.step, self.step, self.step, 0, -self.step, -self.step]

        self.initial_position_x = 0  # Innitial position - middle of the square
        self.initial_position_y = 0

        self.new_position_x = 0  # New position
        self.new_position_y = 0

        self.local_rx_power_dBm = [0] * Tracking.N_SCAN_POINTS  # Local power log
        self.remote_rx_power_dBm = [0] * Tracking.N_SCAN_POINTS  # Remote power log
        self.local_rx_store = [-40] * 3
        self.remote_rx_store = [-40] * 3

        self.average = -40  # Power average for idle state
        self.new_average = 0  # new power average for idle state
        # Counters:
        self.count = 0  # Points count
        self.meas_count = 0  # Measurement count

        self.state = -2  # States
        self.remote_state = -2 # Remote state
        self.start_time = time.time()
        self.motors_stuck = 0

    def run(self, x, y, rx_local, rx_remote, state_remote):

        # Update remote state
        self.remote_state = state_remote

        # Check if requested position was reached
        if self.state > 0 and not self.check_move(x, y):
            self.new_position_x += 1  # Try changing position
            self.backlash.reset_position(self.new_position_x,
                                         self.new_position_y)  # Update position without changing backlash
            logging.info("POSITION NOT REACHED, RE-SEND AND INCREASE!\n")

            # Check stuck time
            if self.motors_stuck == 0:
                self.motors_stuck = time.time()
            elif time.time() - self.motors_stuck > 300:
                self.motors_stuck = 0
                self.state = -2

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # Check if no signal
        if rx_remote <= -40 and rx_local <= -40:
            logging.info("NO SIGNAL, TERMINATE ALIGNMENT!\n")
            self.state = 100

        # STATE: -2: Initialise backlash: only once when algorithm starts
        if self.state == -2:
            logging.info("INITIALISE BACKLASH!\n")

            # Define new position
            self.new_position_x, self.new_position_y = self.backlash.init_backlash(x, y)

            # Initialise other variables
            self.state = -1
            self.count = 0
            self.meas_count = 0

            # Reset measurements
            self.reset_measurements()

            logging.info("Go to: %f %f %f %f \n" % (
            self.new_position_x, self.new_position_y, self.local_rx_power_dBm[self.count],
            self.remote_rx_power_dBm[self.count]))

            return self.new_position_x, self.new_position_y

        # STATE -1: Check other unit status before attempting alignment - always check before atempting to move
        elif self.state == -1:

            # Check in which state is the other unit
            if self.remote_state < 0 or self.remote_state > 4:

                logging.info("Remote unit is not moving state: %d, start alignment!\n" % self.remote_state)
                self.state = 0  # Start alignment

            else:
                logging.info("Wait for the other unit, remote state: %d!\n" % self.remote_state)
                time.sleep(15)

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 0: Monitor alignment procedure - timeout -  second check moving
        elif self.state == 0:
            # Check for timeout
            if time.time() - self.start_time > Tracking.TIMEOUT:
                self.state = 5  # Go to idle state
                logging.info("TIMEOUT!\n")
            # Check if remote unit is moving
            elif self.remote_state < 0 or self.remote_state > 4:
                self.state = 1
                logging.info("ALIGNMENT: Alignment started!\n")
            else:
                self.state = -2
                logging.info("Remote unit started to move state %d, wait!\n" % self.remote_state)

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 1: initialise new backlash circle
        elif self.state == 1:
            # Save initial position
            self.initial_position_x = self.new_position_x
            self.initial_position_y = self.new_position_y

            # Determine step size
            if rx_remote < -20:
                self.step = Tracking.MAX_STEP
            else:
                self.step = Tracking.MIN_STEP

            # Re-set predicted steps for square scan
            self.scan_points_x = [0, -self.step, -self.step, -self.step, 0, self.step, self.step, self.step,
                                  0]  # Steps circle scan
            self.scan_points_y = [0, -self.step, 0, self.step, self.step, self.step, 0, -self.step, -self.step]
            self.n_points = Tracking.N_SCAN_POINTS

            # Record initial readings in state 3
            self.state = 3

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 2: Scanning
        elif self.state == 2:

            # Increase count
            self.count += 1
            # Go to measurement state
            self.state = 3

            # Check if all points have been scanned - find max value position
            if self.count == self.n_points:
                self.state = 4  # Check end conditions

                self.count = self.find_max_value()  # Find best position
                self.store_best_rx(self.local_rx_power_dBm[self.count],
                                   self.remote_rx_power_dBm[self.count])  # Store best rx power
                logging.info("ALIGNMENT: Optimal position found at %d! \n" % self.count)

            # Define new position
            self.new_position_x = self.initial_position_x + self.scan_points_x[self.count]
            self.new_position_y = self.initial_position_y + self.scan_points_y[self.count]

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 3: Measurements - wait for 5, calculate average
        elif self.state == 3:
            # Add new measurements
            self.local_rx_power_dBm[self.count] += rx_local  # Local
            self.remote_rx_power_dBm[self.count] += rx_remote  # Remote
            self.meas_count += 1  # Increment

            # Check if 5 measurements are obtained
            if self.meas_count == Tracking.N_MES:
                self.meas_count = 0  # Reset count
                self.state = 2  # Go to back to moving state
                self.local_rx_power_dBm[self.count] /= Tracking.N_MES  # Calculate average
                self.remote_rx_power_dBm[self.count] /= Tracking.N_MES

                logging.info("ALIGNMENT: Step: %d X: %f Y: %f Local: %f Remote: %f" % (
                self.count, self.new_position_x, self.new_position_y, self.local_rx_power_dBm[self.count],
                self.remote_rx_power_dBm[self.count]))
                logging.info("BACKLASH: %d %d STATE: %d %d\n" % (self.backlash.backlash_x, self.backlash.backlash_y, self.state, self.remote_state))
                with open('scan_output.txt', 'a') as f:
                    f.write("%d %f %f %f %f \n" % (
                    self.count, self.new_position_x, self.new_position_y, self.local_rx_power_dBm[self.count],
                    self.remote_rx_power_dBm[self.count]))
                    f.flush()

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 4: check stopping conditions
        elif self.state == 4:

            # Check if stopping condition was reached
            if self.n_points == Tracking.N_SCAN_POINTS_IDLE:
                self.state = 5  # Check end conditions
                self.count = 0  # Re-set count
            elif self.check_best_rx():
                self.state = 5  # Go to idle
                self.start_time = time.time()  # Store stat time
                self.count = 0  # Re-set count

                logging.info("Stopping conditions reached!\n")
            else:
                # Define new center
                self.new_position_x = self.initial_position_x + 2 * self.scan_points_x[self.count]
                self.new_position_y = self.initial_position_y + 2 * self.scan_points_y[self.count]
                self.state = 0
                self.reset_measurements()

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 5: Idle
        elif self.state == 5:

            # Calculate average
            self.new_average += rx_remote
            self.meas_count += 1

            # Check if 25
            if self.meas_count == Tracking.N_IDLE:
                self.new_average = self.new_average / Tracking.N_IDLE  # Calculate average
                logging.info(
                    "Idle state, new remote average: %f best remote average: %f\n" % (self.new_average, self.average))
                self.count += 1  # Increase average count

                # Start re-aligment
                if self.new_average < self.average - 3 or (
                            time.time() - self.start_time > 1500 and self.new_average < -15):
                    self.average = -40
                    self.state = -1
                    self.reset_measurements()
                    self.start_time = time.time()
                    self.local_rx_store = [-40] * 3
                    self.remote_rx_store = [-40] * 3
                    logging.info("Start alignment!\n")
                # New best average
                else:
                    # If new best position is found update average
                    if self.new_average > self.average:
                        self.average = self.new_average

                    if self.count > 4 and self.remote_state == 5:
                        logging.info("Check cross points in idle state, remote state %d!\n" % self.remote_state)
                        self.reset_measurements()
                        self.state = 3  # Go to measurment state
                        self.step = Tracking.IDLE_STEP
                        self.n_points = Tracking.N_SCAN_POINTS_IDLE
                        # Re-set step size
                        self.scan_points_x = [0, -self.step, 0, self.step, 0]  # Steps cross scan
                        self.scan_points_y = [0, 0, self.step, 0, -self.step]
                        # Set initial position
                        self.initial_position_x = self.new_position_x
                        self.initial_position_y = self.new_position_y

                # reset
                self.new_average = 0
                self.meas_count = 0

            time.sleep(1)
            return x, y

        # Wait for signal
        elif self.state == 100:
            if rx_local > -40 or rx_remote > -40:
                self.state = -2

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

    def reset_measurements(self):
        """Reset rx power and point count"""
        for i in range(Tracking.N_SCAN_POINTS):
            self.local_rx_power_dBm[i] = 0
            self.remote_rx_power_dBm[i] = 0
        self.count = 0  # Reset points count
        self.meas_count = 0  # Reset measurements count

    def find_max_value(self):
        """Find max scanned signal"""
        max_rx = -40
        pos = 0
        for i in range(self.n_points):
            new_rx = self.get_combined_power(self.local_rx_power_dBm[i], self.remote_rx_power_dBm[i])
            if new_rx > max_rx:
                max_rx = new_rx
                pos = i
        return pos

    def get_combined_power(self, rx_local, rx_remote):
        """Combine signal from local and remote unit based on the distance"""
        max_rx = rx_remote
        return max_rx

    def check_move(self, x, y):
        # Convert to position without backlash
        new_x, new_y = self.backlash.backlash_inverse(x, y)

        if self.new_position_x - new_x == 0 and self.new_position_y - new_y == 0:
            return True
        else:
            return False

    def store_best_rx(self, rx_local, rx_remote):
        # Move measurements
        self.local_rx_store[0] = self.local_rx_store[1]
        self.local_rx_store[1] = self.local_rx_store[2]
        self.local_rx_store[2] = rx_local

        self.remote_rx_store[0] = self.remote_rx_store[1]
        self.remote_rx_store[1] = self.remote_rx_store[2]
        self.remote_rx_store[2] = rx_remote

    def check_best_rx(self):
        # Find max and min of last three best power measurements
        max = self.remote_rx_store[0]
        min = self.remote_rx_store[0]
        for i in range(1, 3):
            if max < self.remote_rx_store[i]:
                max = self.remote_rx_store[i]
            if min > self.remote_rx_store[i]:
                min = self.remote_rx_store[i]

        logging.info("Measurements %f %f %f in range %f \n" % (
        self.remote_rx_store[0], self.remote_rx_store[1], self.remote_rx_store[2], max - min))
        # Check if range is smaller than 1
        if max - min < 1 and max > -10:
            return True
        elif self.remote_rx_store[2] > -4:
            return True
        else:
            return False

    def get_state(self):
        # Return current state
        return self.state


def mw_to_dbm(value):
    """Convert mW value to dBm."""

    if value > 0:
        value_dbm = 10 * math.log10(value)
    else:
        value_dbm = -40
    if value_dbm < -40:
        value_dbm = -40

    return value_dbm


# if len(sys.argv) < 2:
#    print("ERROR: Please specify KORUZA unit host.")
#    sys.exit(1)

if os.getuid() != 0:
    print("ERROR: Must be run as root.")
    sys.exit(1)

# Local unit
local = KoruzaAPI(KoruzaAPI.LOCAL_HOST)
# Get remote unit
while True:
    try:
        local_status = local.get_status()
        break
    except KoruzaAPIError, error:
        print("WARNING: API error ({}) while requesting local status.".format(error))
        logging.warning("WARNING: API error ({}) while requesting local status.".format(error))
        continue

remote = local_status['network']['peer']

# Tracking
alignment = Tracking()

# Open log file
logging.basicConfig(filename='alignment.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Processing loop.
print("INFO: Starting processing loop.")
time.sleep(2)
while True:
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
    remote_state = remote_status['alignment']['state']
    local_state = local_status['alignment']['state']

    # logging.info("INFO: Local state: %d Remote state: %d", local_state, remote_state)
    # print("INFO: Remote SFP RX power (dBm):", remote_rx_power_dbm)
    # print("INFO: Local SFP RX power (dBm):", local_rx_power_dbm)
    # print("INFO: Local motor position (x, y):", local_x, local_y)

    target_x, target_y = alignment.run(local_x, local_y, local_rx_power_dbm, remote_rx_power_dbm, remote_state)
    target = (target_x, target_y)

    # Report new state
    local.set_alignment(alignment.get_state(), [0,0,0,0])

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
    while True:
        try:
            # Check if target reached.
            current_motors = local.get_status()['motors']
            current = (current_motors['x'], current_motors['y'])

            if current == target:
                # logging.info("INFO: Target coordinates reached.\n")
                break

            if last_coordinates != current:
                last_coordinates_same = None
            elif last_coordinates_same is None:
                last_coordinates_same = time.time()

            last_coordinates = current

            # Check for stuck motors (coordinates didn't change in the last 5s).
            if last_coordinates_same is not None and time.time() - last_coordinates_same > 30:
                print("WARNING: Motors stuck when trying to reach target coordinates.")
                logging.warning("WARNING: Motors stuck when trying to reach target coordinates.")
                logging.warning("WARNING: Coordinates: %d %d" % (target_x, target_y))
                break

        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while confirming local move.".format(error))
            logging.warning("WARNING: API error ({}) while confirming local move.".format(error))
