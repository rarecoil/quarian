"""
    proxy.py
    Attempts a connection to a reverse proxy in front of Geth. Useful
    for nodes wrapped behind a reverse HTTP proxy. Supports TLS client cert
    in PEM format.
"""

import time

import requests

from .base import CheckBase

class CheckProxy(CheckBase):

    web3_reference = None
    web3_geth = None
    console = None

    last_restart = None
    tls_client_cert_path = None
    restart_delay = 30

    def __init__(self, global_options, check_options, core):
        super().__init__(global_options, check_options, core)
        self.last_restart = time.time()
        self.restart_delay = int(self.check_options.get('restart_delay_sec', 30))
        self.tls_client_cert_path = self.check_options.get('tls_client_cert_file', None)
        self.restart_codes = self.check_options.get('restart_codes', '500,502,503').split(',')
        self.user_agent = self.global_options.get('user_agent', 'Quarian/CheckProxy (//github.com/10a7/quarian)')

    def check(self, uri):
        """Returns a Boolean on whether or not Quarian should restart Geth."""
        now = time.time()
        if (now - self.last_restart) <= self.restart_delay:
            self.console.debug("Not restarting node due to proxycheck, still in delay period.")
            return False

        json_data = '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":'+str(int(time.time()))+'}'
        request_with_cert = False
        if self.tls_client_cert_path is not None:
            if os.path.isfile(self.tls_client_cert_path):
                request_with_cert = True
            else:
                self.console.error("TLS client certificate path %s is not a file." % self.tls_client_cert_path)

        if request_with_cert is True:
            req = requests.post(uri,
                data=json_data,
                cert=self.tls_client_cert_path,
                headers={'user-agent': self.user_agent,
                    'content-type': 'application/json' })
        else:
            req = requests.post(uri,
                data=json_data,
                headers={'user-agent': self.user_agent,
                    'content-type': 'application/json' })

        if req.status_code in self.restart_codes:
            self.console.warn("✘  Node failed proxy check with status code %d, attempting restart." % req.status_code)
            self.last_restart = now
            return True
        else:
            self.console.debug("✅  Node within spec, reverse proxy returned status code %d" % req.status_code)

        return False
