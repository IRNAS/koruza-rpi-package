from __future__ import print_function

import pprint
import requests
import sys
import json


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

        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'id': 1,
            'params': [self._session, object_name, method, parameters],
        }
        response = requests.post(
            'http://{}:{}{}'.format(self.host, self.port, self.path),
            data=json.dumps(payload),
            headers={'content-type': 'application/json'}
        ).json()

        if 'result' in response:
            code = response['result'][0]
            if code == KoruzaAPI.STATUS_OK:
                return response['result'][1]
            else:
                raise KoruzaAPIError(code)
        elif 'error' in response:
            print(response)
            raise KoruzaAPIError(response['error']['code'])

    def login(self, username, password):
        """Authenticate to the remote host.

        Authentication is only required for specific requests. Some requests
        may be performed without authentication.
        """
        response = self._call('session', 'login', {
            'username': username,
            'password': password,
            'timeout': 3600,
        })
        self._session = response['ubus_rpc_session']

    def logout(self):
        """Close session."""
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

if len(sys.argv) < 2:
    print('Please specify KORUZA unit host.')
    sys.exit(1)

api = KoruzaAPI(sys.argv[1])

status = api.get_status()
sfp_modules = api.get_sfp_modules()
sfp_diagnostics = api.get_sfp_diagnostics()

print('Status:')
pprint.pprint(status)
print('SFP modules:')
pprint.pprint(sfp_modules)
print('SFP diagnostics:')
pprint.pprint(sfp_diagnostics)
