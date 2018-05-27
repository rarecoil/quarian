"""
    locallogidle.py

    Looks for no activity in a Geth stderr log by parsing the log's
    timestamps and comparing to the current time. Restarts geth if
    no activity is noted. Sometimes geth will fail with 
    "Synchronisation failed" and then stop downloading, even though
    it still has a high peer count.

    Note that this check expects the logs for geth to be on the same
    filesystem as quarian. This check does not work in a clustered
    environment in which you may want to restart geth via http.

    This is mostly useful for nodes stalling during initial sync of
    the state trie. The "chaintip" check is better for production
    nodes that need to stay up to date. However, this check covers
    a lot of potential sins with Geth at the risk of being slightly
    overzealous at restarting the system.
"""

import time
import os
import re
from .base import CheckBase


class CheckLocalLogIdle(CheckBase):

    web3_reference = None
    web3_geth = None
    console = None

    grace_period = 600
    allow_idle_sec = 120
    last_check = None

    geth_log_location = None

    def __init__(self, global_options, check_options, core):
        super().__init__(global_options, check_options, core)
        self.grace_period = int(self.check_options['grace_period'])
        self.allow_idle_sec = int(self.check_options['allow_idle_sec'])
        if 'geth_log_location' in self.check_options:
            filepath = os.path.abspath(self.check_options['geth_log_location'])
            if os.path.isfile(filepath):
                self.geth_log_location = filepath
            else:
                raise IOError("Cannot find geth log at %s" % filepath)
        else:
            raise IOError("geth_log_location is not specified for logidle check.")


    def check(self, uri):
        """Returns a Boolean on whether or not Quarian should restart Geth."""
        now = time.time()
        last_log_time = self._get_last_log_entry_timestamp()
        if self.last_check is not None:
            timedelta = now - last_log_time
            if (now + self.grace_period > self.last_check) and timedelta > self.allow_idle_sec:
                self.console.warn("✘  Node is stalled by %d seconds, attempting restart (%s)" % (timedelta, uri))
                self.last_check = now
                return True
            else:
                return False
        else:
            self.last_check = now


    def _get_last_log_entry_timestamp(self):
        # https://stackoverflow.com/questions/3346430/what-is-the-most-efficient-way-to-get-first-and-last-line-of-a-text-file
        with open(self.geth_log_location, "rb") as f:
            f.readline() 
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
            lastline = f.readline().trim()
        if len(lastline) > 20:
            now_struct_time = time.localtime(time.time())
            last_log_timestamp = time.mktime(
                time.strptime(
                    lastline[6:20]+"|"+str(now_struct_time.tm_year), 
                    '%m-%d|%H:%M:%S|%Y'))
            return last_log_timestamp
        return None 
            