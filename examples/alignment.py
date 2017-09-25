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
                #logging.warning("Command sent: {}".format(response))

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

# Backlash class
class Backlash(object):
    BACKLASH = 130 # Backlash

    def __init__(self):
        """Initialise all variables"""

        self.backlash_x = 0 # Movement direction
        self.backlash_y = 0

        self.new_position_x = 0 # New position
        self.new_position_y = 0

        self.old_position_x = 0 # Prev position
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
    N_MES = 5
    N_STOP = 3 # Number of consecitive times maximum is found at the center
    N_IDLE = 100 # Number of averaged mesurments in idle state
    TIMEOUT = 1000 # Timeout for single alignment session

    def __init__(self):
        """Initialise all variables"""

        self.backlash = Backlash() # Backlash class

        self.step = 50 # Step size

        self.scan_points_x = [0, -self.step, -self.step, -self.step, 0, self.step, self.step, self.step, 0] # Steps circle scan
        self.scan_points_y = [0, -self.step, 0, self.step, self.step, self.step, 0, -self.step, -self.step]

        self.initial_position_x = 0 # Innitial position - middle of the square
        self.initial_position_y = 0

        self.new_position_x = 0 # New position
        self.new_position_y = 0

        self.remote_x = 0 # Remote position for motion controll

        self.local_rx_power_dBm = [0]*Tracking.N_SCAN_POINTS # Local power log
        self.remote_rx_power_dBm = [0]*Tracking.N_SCAN_POINTS # Remote power log
        self.local_rx_store = [-40]*3
        self.remote_rx_store = [-40]*3

        self.average = -40 # Power average for idle state
        self.new_average = 0 # new power average for idle state
        # Counters:
        self.count = 0 # Points count
        self.meas_count = 0 # Measurement count
        self.stop_count = 0 # Number of consecitive times maximum is found at the center

        self.state = -2 # States
        self.start_time = time.time()
        self.motors_stuck = 0

    def run(self, x, y, x_remote, y_remote, rx_local, rx_remote):

        # Print out position
        # logging.info("New position: X: %d Y: %d wantedX: %d wantedY: %d\n" %(x,y, self.new_position_x - self.backlash_x*Tracking.BACKLASH, self.new_position_y - self.backlash_y*Tracking.BACKLASH))

        # Check if requested position was reached
        if self.state > 0 and not self.check_move(x,y):
            logging.info("POSITION NOT REACHED, RE-SEND!\n")
            self.new_position_x += 2 # Try changing position

            # Check stuck time
            if self.motors_stuck == 0:
                self.motors_stuck = time.time()
            elif time.time() - self.motors_stuck > 200:
                self.motors_stuck = 0
                self.state = -2

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE: -2: Initialise backlash
        if self.state == -2:
            logging.info("INITIALISE BACKLASH!\n")

            # Define new position
            self.new_position_x, self.new_position_y = self.backlash.init_backlash(x,y)

            # Initialise other variables
            self.state = -1
            self.count = 0
            self.meas_count = 0
            self.stop_count = 0

            # Reset measurements
            self.reset_measurements()

            # Initialise steps
            if self.new_position_x % 2 == 1:
                self.new_position_x += 1
                self.backlash.reset_position(self.new_position_x, self.new_position_y) # Update position without changing backlash

            logging.info("Go to: %f %f %f %f \n" % (self.new_position_x, self.new_position_y, self.local_rx_power_dBm[self.count], self.remote_rx_power_dBm[self.count]))

            return self.new_position_x, self.new_position_y

        # STATE -1: Check other unit status before attempting alignment
        elif self.state == -1:

            if(remote_x % 2 == 0):

                if(self.remote_x == x_remote):
                    logging.info("Remote unit is not moving, start alignment!\n")
                    self.remote_x = 0 # re-set
                    self.new_position_x += 1 # Denote start of alignment
                    self.backlash.reset_position(self.new_position_x, self.new_position_y) # Update position without changing backlash
                    self.state = 0 # Start alignment
                else:
                    self.remote_x = x_remote
                    time.sleep(15)

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 0: monitoring
        elif self.state == 0:
            # Check for timeout
            if time.time() - self.start_time > Tracking.TIMEOUT:
                self.state = 5 # Go to idle state
                self.new_position_x -= 1 # Mark end of the alignment
                self.backlash.reset_position(self.new_position_x, self.new_position_y) # Update position without changing backlash
                print("TIMEOUT!\n")
                logging.info("TIMEOUT!\n")
            else:
                self.state = 1
                print("ALIGNMENT: Alignment started!\n")
                logging.info("ALIGNMENT: Alignment started!\n")

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 1: initialise
        elif self.state == 1:
            # save initial position, subtract backlash
            self.initial_position_x = self.new_position_x
            self.initial_position_y = self.new_position_y

            # Determine step size
            if rx_remote < -20:
                self.step = 100
            else:
                self.step = 50

            # Re-set step size
            self.scan_points_x = [0, -self.step, -self.step, -self.step, 0, self.step, self.step, self.step, 0] # Steps circle scan
            self.scan_points_y = [0, -self.step, 0, self.step, self.step, self.step, 0, -self.step, -self.step]

            # Record initial readings in state 3
            self.state = 3
            logging.info("ALIGNMENT: Initialise!\n")
            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 2: scanning
        elif self.state == 2:

            # Increase count
            self.count += 1
            # Go to measurement state
            self.state = 3

            # Check if all points have been scanned - find max value position
            if self.count == Tracking.N_SCAN_POINTS:
                self.state = 4 # Check end conditions
                self.count = self.find_max_value() # Find best position
                self.store_best_rx(self.local_rx_power_dBm[self.count], self.remote_rx_power_dBm[self.count]) # Store best rx power
                logging.info("ALIGNMENT: Optimal position found at %d! \n" % self.count)

            # Define new position
            self.new_position_x = self.initial_position_x + self.scan_points_x[self.count]
            self.new_position_y = self.initial_position_y + self.scan_points_y[self.count]

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 3: wait for 10 measurements, calculate average
        elif self.state == 3:
            # Add new measurements
            self.local_rx_power_dBm[self.count] += rx_local
            self.remote_rx_power_dBm[self.count] += rx_remote
            self.meas_count += 1 # Increment

            # Check if 10 measurements are obtained
            if self.meas_count == Tracking.N_MES:
                self.meas_count = 0 # Reset
                self.state = 2 # Go to moving state
                # Calculate average
                self.local_rx_power_dBm[self.count] /= Tracking.N_MES
                self.remote_rx_power_dBm[self.count] /= Tracking.N_MES

                logging.info("ALIGNMENT: Step: %d X: %f Y: %f Local: %f Remote: %f" % (self.count, self.new_position_x, self.new_position_y, self.local_rx_power_dBm[self.count], self.remote_rx_power_dBm[self.count]))
                logging.info("BACKLASH: %d %d \n" % (self.backlash.backlash_x, self.backlash.backlash_y))
                with open('scan_output.txt','a') as f:
                    f.write("%d %f %f %f %f \n" % (self.count, self.new_position_x, self.new_position_y, self.local_rx_power_dBm[self.count], self.remote_rx_power_dBm[self.count]))
                    f.flush()

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 4: check stopping conditions
        elif self.state == 4:

            # Check if stopping condition was reached
            if self.check_best_rx():
                self.state = 5 # Go to idle
                self.start_time = time.time() # Store stat time
                self.new_position_x -= 1 # Mark end of movement
                self.backlash.reset_position(self.new_position_x, self.new_position_y) # Update position without changing backlash
                self.stop_count = 0
                logging.info("Stopping conditions reached!\n")
            else:
                # Define new center
                self.new_position_x = self.initial_position_x + 2 * self.scan_points_x[self.count]
                self.new_position_y = self.initial_position_y + 2 * self.scan_points_y[self.count]
                self.state = 6 # Re-set and continue

            return self.backlash.backlash_forward(self.new_position_x, self.new_position_y)

        # STATE 5: Idle
        elif self.state == 5:

            # Calculate average
            self.new_average += rx_remote
            self.meas_count += 1

            # Check if 100
            if self.meas_count == Tracking.N_IDLE:
                self.new_average = self.new_average / Tracking.N_IDLE # Calculate average
                logging.info("Idle state, new remote average: %f\n" % self.new_average)

                # Start re-aligment
                if self.new_average < self.average - 3 or (time.time() - self.start_time > 1500 and self.new_average < -15):
                    self.average = -40
                    self.state = -1
                    self.reset_measurements()
                    self.start_time = time.time()
                    self.local_rx_store = [-40]*3
                    self.remote_rx_store = [-40]*3
                # New best average
                elif self.new_average > self.average:
                    self.average = self.new_average

                # reset
                self.new_average = 0
                self.meas_count = 0

            time.sleep(1)
            return x,y

        # STATE 6: re-set
        else:
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

    def check_move(self, x, y):
        # Convert to position without backlash
        new_x, new_y = self.backlash.backlash_inverse(x,y)

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
        for i in range(1,3):
            if max < self.remote_rx_store[i]:
                max = self.remote_rx_store[i]
            if min > self.remote_rx_store[i]:
                min = self.remote_rx_store[i]

        logging.info("Measurements %f %f %f in range %f \n" % (self.remote_rx_store[0], self.remote_rx_store[1], self.remote_rx_store[2], max - min))
        # Check if range is smaller than 1
        if max - min < 1 and max > -10:
            return True
        elif self.remote_rx_store[2] > -4:
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
alignment = Tracking()

# Open log file
logging.basicConfig(filename='alignment.log',level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)


# Processing loop.
stuck_counter = 0
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

    # print("INFO: Distance:", distance)
    # print("INFO: Remote SFP RX power (dBm):", remote_rx_power_dbm)
    # print("INFO: Local SFP RX power (dBm):", local_rx_power_dbm)
    # print("INFO: Local motor position (x, y):", local_x, local_y)

    target_x, target_y = alignment.run(local_x, local_y, remote_x, remote_y, local_rx_power_dbm, remote_rx_power_dbm)

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
    while True:
        try:
            # Check if target reached.
            current_motors = local.get_status()['motors']
            current = (current_motors['x'], current_motors['y'])

            if current == target:
                # logging.info("INFO: Target coordinates reached.\n")
                stuck_counter = 0
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
                logging.warning("DEBUG: --- Current status dump ---")
                logging.warning(local.get_status())
                logging.warning("DEBUG: ---------------------------")

                stuck_counter += 1
                if stuck_counter > 1:
                    logging.warning("DEBUG: Stuck more than once. Algorithm paused, running debug procedure.")
                    logging.warning("DEBUG: Trying to move motors to (0, 0).")
                    local.move_motor(0, 0)
                    logging.warning("DEBUG: Command sent, waiting 15 seconds before status update.")
                    time.sleep(15)
                    logging.warning("DEBUG: --- Current status dump ---")
                    logging.warning(local.get_status())
                    logging.warning("DEBUG: ---------------------------")
                break
        except KoruzaAPIError, error:
            print("WARNING: API error ({}) while confirming local move.".format(error))
            logging.warning("WARNING: API error ({}) while confirming local move.".format(error))
