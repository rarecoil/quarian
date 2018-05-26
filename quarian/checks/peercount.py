"""
    peercount.py

    Checks for dropped peers. Geth nodes on unreliable network interfaces
    will often drop all peers on initial fast sync and then not download
    state entries or block headers/receipts.
"""

import time
from .base import CheckBase

class CheckPeerCount(CheckBase):

    web3_reference = None
    web3_geth = None
    console = None

    global_options = None
    check_options = None

    min_peer_count = 5
    grace_period = 300
    last_check = None

    def __init__(self, global_options, check_options, core):
        super().__init__(global_options, check_options, core)
        self.min_peer_count = int(self.check_options['min_peer_count'])
        self.grace_period = int(self.check_options['grace_period'])

    def check(self, uri):
        """Returns a Boolean on whether or not Quarian should restart Geth."""
        num_peers = self.web3_geth.net.peerCount
        now = time.time()
        self.console.debug("Node has peer count %d, minimum %d (%s)" % (num_peers, self.min_peer_count, uri))
        if self.last_check is not None:
            if num_peers < self.min_peer_count and (now + self.grace_period > self.last_check):
                self.last_check = now
                self.console.warn("✘  Node is below minimum peer count %d, attempting restart (%s)" % (self.min_peer_count, uri))
                return True
        else:
            self.last_check = now
        return False