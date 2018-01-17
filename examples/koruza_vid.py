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

    CAMERA_STORAGE_PATH = 'camera'
    TEMPLATE_PATH = 'examples/koruza.jpg'
    RESOLUTION = (1280,720)
    TEMPLATE_OFFSET = 17
    TEMPLATE_SIZE = 2 * TEMPLATE_OFFSET + 1
    SNAPSHOT_TIME = 60
    METHOD = eval('cv2.TM_CCOEFF') # Matching method
    SHIFT_THRESHOLD = 10

    def __init__(self, off_x, off_y):
        self._camera = None
        self._offset_x = offset_x
        self._offset_y = offset_y

        # Ensure storage location exists.
        if not os.path.exists(self.CAMERA_STORAGE_PATH):
            os.makedirs(self.CAMERA_STORAGE_PATH)
            print("Dir created.")

        # Set crop data
        self._crop_x = self._offset_x - 0.2 * self.RESOLUTION[0]
        if self._crop_x < 0:
            self._crop_x = 0
        elif self._crop_x + 0.4 * self.RESOLUTION[0] > self.RESOLUTION[0]:
            self._crop_x = int(self.RESOLUTION[0] * 0.6)

        self._crop_y = self._offset_y - 0.2 * self.RESOLUTION[1]
        if self._crop_y < 0:
            self._crop_y = 0
        elif self._crop_y + 0.4 * self.RESOLUTION[1] > self.RESOLUTION[1]:
            self._crop_y = int(self.RESOLUTION[1] * 0.6)

        # Top left corner of the template with respect to cropped snapshot
        self._initial_top_left = (int(self._offset_x - self.TEMPLATE_OFFSET - self._crop_x), int(self._offset_y - self.TEMPLATE_OFFSET - self._crop_y))
        self._top_left = self._initial_top_left

        print(self._crop_x, self._crop_y)
        print(self._top_left)

        # Read template
        self._template = []
        frame = self.snapshot()
        self.update_template(frame)
        cv2.imwrite(os.path.join(self.CAMERA_STORAGE_PATH,'test-template.jpg'),self._template)
        self._remote_rx = -40


    def snapshot(self):

        try:
            self._camera = picamera.PiCamera()
            self._camera.resolution = self.RESOLUTION
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
            cv2.imwrite(os.path.join(self.CAMERA_STORAGE_PATH,'test-snapshot.jpg'),frame)
            # Crop
            frame = frame[self._crop_y:self._crop_y + 0.4 * self.RESOLUTION[1], self._crop_x:self._crop_x + 0.4 * self.RESOLUTION[0]]

        self._camera.close()

        return frame


    def track(self, rx):

        self._remote_rx = rx # Update power
        now = datetime.datetime.now()

        # Take new frame
        frame = self.snapshot()

        # Match template
        matched_frame = self.template_match(frame)
        # Save
        cv2.imwrite(os.path.join(
                    self.CAMERA_STORAGE_PATH,
                    'snapshot-{year}-{month:02d}-{day:02d}-{hour:02d}-{minute:02d}-{second:02d}-{RX:02f}.jpg'.format(
                        year=now.year,
                        month=now.month,
                        day=now.day,
                        hour=now.hour,
                        minute=now.minute,
                        second=now.second,
                        RX=self._remote_rx,
                    )
                ), matched_frame)

        # Save template
        cv2.imwrite(os.path.join(
                    self.CAMERA_STORAGE_PATH,
                    'template-{year}-{month:02d}-{day:02d}-{hour:02d}-{minute:02d}-{second:02d}-{RX:02f}.jpg'.format(
                        year=now.year,
                        month=now.month,
                        day=now.day,
                        hour=now.hour,
                        minute=now.minute,
                        second=now.second,
                        RX=self._remote_rx,
                    )
                ), self._template)
        print("Done")
        file.write("%s X:%d Y:%d RX:%.2f\n" % (now, self._top_left[0], self._top_left[1], self._remote_rx))

        time.sleep(self.SNAPSHOT_TIME)

    def template_match(self, frame):

        res = cv2.matchTemplate(frame,self._template,self.METHOD)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # Check movement
        update = False
        if abs(self._top_left[0] - max_loc[0]) < self.SHIFT_THRESHOLD and abs(self._top_left[1] - max_loc[1]) < self.SHIFT_THRESHOLD:
            self._top_left = max_loc
            update = True
        else:
            file.write("WARNING: X:%d Y:%d RX:%.2f\n" % (max_loc[0], max_loc[1], self._remote_rx))

        # If good enough signal update template
        if update:
            self.update_template(frame)

        bottom_right = (self._top_left[0] + self.TEMPLATE_SIZE, self._top_left[1] + self.TEMPLATE_SIZE)
        cv2.rectangle(frame,self._top_left, bottom_right, 0, 2)

        return frame

    def update_template(self, frame):
        self._template = frame.copy() # Copy snapshot
        self._template = self._template[self._top_left[1]:self._top_left[1] + self.TEMPLATE_SIZE, self._top_left[0]:self._top_left[0] + self.TEMPLATE_SIZE] # Crop

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

offset_x = 590
offset_y = 327

remote = KoruzaAPI(local_status['network']['peer'])

Run = True
koruza_camera = Camera(offset_x, offset_y)
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
    koruza_camera.track(remote_rx_power_dbm)



