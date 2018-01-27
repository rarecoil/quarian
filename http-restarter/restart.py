#!/usr/bin/env python
"""
     restart.py

     An endpoint that takes the same settings from settings.conf and uses
     them to restart the Geth server. Use this if you're dealing with
     some type of tooling that will restart geth for you.

     Note you do *not* need to install all of quarian on the server to use this
     restarter. This may be copied independently of quarian to a geth node,
     and used to restart the service client side.

     Authentication happens one of two ways: either with a PSK (preshared key)
     or with TLS client cert on the reverse proxy in front of this listener.
     For no auth (trusted networks), set auth type to 'noauth'.
"""

import hashlib
import json
import os
import sys
import time

from configparser import ConfigParser
from subprocess import Popen, PIPE

from flask import Flask, jsonify, request, Response
app = Flask(__name__)

DEBUG = ('DEBUG' in os.environ)

restart_delay = 30
auth_type = 'noauth'
auth_token = None
restart_command = ''
listen_port = 8546

def gen_auth_token():
    """Creates a secret token for this server."""
    return str(hashlib.sha256(os.urandom(16)).hexdigest())

def authenticate_user_psk(http_bearer_token):
    """Returns a boolean if the bearer token matches the psk in memory."""
    global auth_token
    if http_bearer_token.find("Bearer ") == 0:
        http_bearer_token = http_bearer_token[7:]
    return (http_bearer_token == auth_token)

def load_settings(settings_file=None):
    """Load settings for the HTTP Restarter."""
    global restart_delay, auth_type, auth_token, restart_command, listen_port

    candidate_locations = [
        os.path.realpath(os.path.join(os.getcwd(), 'settings.conf')),
        '/etc/quarian/settings.conf',
        '/etc/quarian.conf',
        '/etc/default/quarian.conf',
        '/opt/quarian/settings.conf'
    ]
    # override if arg forced
    if settings_file is not None:
        candidate_locations = [settings_file]

    location_filepath = None
    for location in candidate_locations:
        if os.path.isfile(location):
            print("Using settings file %s" % location)
            location_filepath = location

    if location_filepath is None:
        raise FileNotFoundError("Cannot find Quarian configuration file.")

    config = ConfigParser()
    config.read(location_filepath)

    if 'quarian:restarter:http' not in config.sections():
        print("Configuration missing. Please add a quarian:restarter:http section.")
        sys.exit(1)
    else:
        restart_command = config['quarian:restarter:http'].get('restart_command', False)
        if not restart_command:
            print("restart_command must be specified in settings.")
            sys.exit(1)
        listen_port = int(config['quarian:restarter:http'].get('listen_port', 8546))
        restart_delay = config['quarian:restarter:http'].get('ignore_restart_requests_for_sec', 30)
        auth_type = config['quarian:restarter:http'].get('auth_type', 'noauth')
        if auth_type == 'psk':
            print("Selected PSK authentication.")
            auth_token = config['quarian:restarter:http'].get('auth_psk', False)
            if auth_token == 'INSECURE_PRESHARED_KEY_IS_HERE':
                print("Refusing to start with insecure PSK. Please change the PSK in your settings.conf.")
                sys.exit(1)
            elif auth_token == False:
                auth_token = gen_auth_token()
                print("No auth token specified, generating one for you.")
                print("Auth token to this server is %s" % auth_token)
        else:
            print("Warning: 'noauth' selected. Without upstream authentication or filtering, your server is subject to DoS")


@app.route('/')
def index():
    """Returns a basic JSON heartbeat."""
    return jsonify({ 'success': True })


@app.route('/restart', methods=['GET'])
def restart():
    """Restarts the geth instance."""
    global auth_type
    if auth_type == 'psk':
        auth_token = request.headers.get('authentication', False)
        if not auth_token:
            return Response(json.dumps({
                'success': False,
                'msg': 'Authentication required'
            }), 401, {'Content-type': 'application/json'})
        res = authenticate_user_psk(auth_token)
        if res is False:
            return Response(json.dumps({
                'success': False,
                'msg': 'Incorrect token'
            }), 403, {'Content-type': 'application/json'})

    # execute the shell command to restart geth
    proc = Popen(restart_command, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    code = proc.returncode
    success = (proc.returncode == 0)
    return jsonify({
            'success': success,
            'status_code': code,
            'stdout': stdout.decode(),
            'stderr': stderr.decode()
        })

if __name__ == '__main__':
    load_settings()
    app.run(debug=DEBUG, port=listen_port)