"""
    cron.py
    Simply fires a restart once enough Quarian uptime has passed.
"""

import time
from .base import CheckBase

class CheckTimer(CheckBase):

    web3_reference = None
    web3_geth = None
    console = None

    restart_every_sec = None
    last_restart = None

    def __init__(self, global_options, check_options, core):
        super().__init__(global_options, check_options, core)
        self.last_restart = time.time()
        self.restart_every_sec = int(self.check_options['restart_every_sec'])

    def check(self, uri):
        """Returns a Boolean on whether or not Quarian should restart Geth."""
        now = time.time()
        if (now - self.last_restart) >= self.restart_every_sec:
            return True
        else:
            return False
