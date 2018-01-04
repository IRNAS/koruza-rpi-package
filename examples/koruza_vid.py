from __future__ import print_function
import json
import math
import subprocess
import sys
import time
import requests
import logging
import datetime
import picamera
import picamera.array
import os
import cv2

# Image storage location.
CAMERA_STORAGE_PATH = 'camera'
TEMPLATE_PATH = 'examples/koruza.jpg'


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
                # logging.warning("Command sent: {}...".format(response[:30]))

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

    if value > 0:
        value_dbm = 10 * math.log10(value)
    else:
        value_dbm = -40
    if value_dbm < -40:
        value_dbm = -40

    return value_dbm

class Camera(object):
    def __init__(self, width, height, x_offset, y_offset):
        self._camera = None
        self._recording_start = None
        self.width = width
        self.heigth = 720
        self.snapshot_time = 60 # Time between snaps
        self.method = eval('cv2.TM_CCOEFF') # Matching method

        # Read template
        self.template = cv2.imread(TEMPLATE_PATH,0)
        self.w, self.h = self.template.shape[::-1]
        self.top_left = []
        self.remote_rx = -40
        self.offset_x = x_offset
        self.offset_y = y_offset

        # Ensure storage location exists.
        if not os.path.exists(CAMERA_STORAGE_PATH):
            os.makedirs(CAMERA_STORAGE_PATH)
            print("Dir created.")

    def snapshot(self, rx):
        self.remote_rx = rx # Update power
        now = datetime.datetime.now()

        try:
            self._camera = picamera.PiCamera()
            self._camera.resolution = (self.width, self.heigth)
            self._camera.hflip = True
            self._camera.vflip = True
            print("Camera initialised.")
        except picamera.PiCameraError:
            print("ERROR: Failed to initialize camera.")

        # Capture snapshot
        with picamera.array.PiRGBArray(self._camera) as output:
            self._camera.capture(output, format='bgr')
            # Store image to ndarray and convert it to grayscale
            frame = cv2.cvtColor(output.array, cv2.COLOR_BGR2GRAY)
            # Crop frame
            frame = frame[self.offset_y:self.offset_y+0.4*self.heigth, self.offset_x:self.offset_x+self.width]

        self._camera.close()
        print("Image captured")

        # Match template
        matched_frame = self.template_match(frame)
        # Save
        cv2.imwrite(os.path.join(
                    CAMERA_STORAGE_PATH,
                    'snapshot-{year}-{month:02d}-{day:02d}-{hour:02d}-{minute:02d}-{second:02d}-{RX:02f}.jpg'.format(
                        year=now.year,
                        month=now.month,
                        day=now.day,
                        hour=now.hour,
                        minute=now.minute,
                        second=now.second,
                        RX=self.remote_rx,
                    )
                ), matched_frame)
        print("Done")
        file.write("%s X:%d Y:%d RX:%.2f\n" % (now, self.top_left[0], self.top_left[1], self.remote_rx))
        time.sleep(self.snapshot_time)

    def template_match(self, frame):

        res = cv2.matchTemplate(frame,self.template,self.method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # Check movement
        update = False
        if self.top_left == []:
            self.top_left = max_loc
            update = True
        elif abs(self.top_left[0] - max_loc[0]) < 5 and abs(self.top_left[1] - max_loc[1]) < 5:
            self.top_left = max_loc
            update = True

        # If good enough signal update template
        if update:
            self.update_template(frame)

        bottom_right = (self.top_left[0] + self.w, self.top_left[1] + self.h)
        cv2.rectangle(frame,self.top_left, bottom_right, 0, 2)

        return frame

    def update_template(self, frame):
        tmp_frame = frame # Copy snapshot
        tmp_frame = tmp_frame[self.top_left[1]:self.top_left[1] + self.h, self.top_left[0]:+self.top_left[0] + self.w] # Crop
        self.template = tmp_frame # Update frame

        # Store
        cv2.imwrite(TEMPLATE_PATH, tmp_frame)
        print("TEMPLATE updated!")


if os.getuid() != 0:
    print("ERROR: Must be run as root.")
    sys.exit(1)

local = KoruzaAPI(KoruzaAPI.LOCAL_HOST)
while True:
    try:
        local_status = local.get_status()
        break
    except KoruzaAPIError, error:
        print("WARNING: API error ({}) while requesting local status.".format(error))
        logging.warning("WARNING: API error ({}) while requesting local status.".format(error))
        continue

width = local_status['camera_calibration']['width']
height = local_status['camera_calibration']['height']
offset_x = local_status['camera_calibration']['offset_x']
offset_y = local_status['camera_calibration']['offset_y']

remote = KoruzaAPI(local_status['network']['peer'])

Run = True
koruza_camera = Camera(width, height, offset_x, offset_y)
file = open('video_analysis.txt','w')

# Processing loop.
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

    # Take picture
    koruza_camera.snapshot(remote_rx_power_dbm)



