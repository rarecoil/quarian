"""
    chaintip.py

    Checks for a lag against the chain tip. If the geth node is a certain
    number of blocks behind / trailing a canonical mainnet block, then
    restart the node.
"""
import time
import requests
from .base import CheckBase

class CheckChainTip(CheckBase):

    web3_reference = None
    web3_geth = None
    console = None

    global_options = None
    check_options = None

    allow_trailing_syncing = 1000
    allow_trailing_stalled = 500

    restart_grace_period_strategy = 'fixed'
    restart_grace_period_sec = 60
    restart_grace_period_adaptive_blocks_per_sec = 3

    last_restart = None
    adaptive_grace_period_target = None

    def __init__(self, global_options, check_options, core):
        super().__init__(global_options, check_options, core)

        if 'ignore_firstrun_node' in self.global_options:
            self.ignore_firstrun_node = bool(self.global_options['ignore_firstrun_node'])

        if 'allow_trailing_syncing' in self.check_options:
            self.allow_trailing_syncing = int(self.check_options['allow_trailing_syncing'])
        if 'allow_trailing_stalled' in self.check_options:
            self.allow_trailing_stalled = int(self.check_options['allow_trailing_stalled'])

        # grace period settings
        if 'restart_grace_period_strategy' in self.check_options:
            proposed_strategy = self.check_options['restart_grace_period_strategy']
            if proposed_strategy in ['fixed', 'adaptive']:
                self.restart_grace_period_strategy = proposed_strategy
            else:
                self.console.error("Restart grace period strategy %s is " + \
                    "not supported. Defaulting to fixed." % proposed_strategy)

        if 'restart_grace_period_sec' in self.check_options:
            self.restart_grace_period_sec = int(self.check_options['restart_grace_period_sec'])
        if 'restart_grace_period_adaptive_blocks_per_sec' in self.check_options:
            self.restart_grace_period_adaptive_blocks_per_sec = \
                int(self.check_options['restart_grace_period_adaptive_blocks_per_sec'])

    def check(self, uri):
        """Check if the node is trailing the chain tip."""

        self.console.debug("Checking node... (%s)" % uri)
        try:
            actual_highest, provider = self.core.get_highest_known_block()
            current_block, syncing  = self._get_current_highest_block_geth(uri, True)
        except requests.exceptions.ConnectionError:
            self.console.error("Connection Failed, attempting restart (%s)" % uri)
            return self._issue_restart()
        except requests.exceptions.Timeout:
            self.console.error("Connection Timeout, attempting restart (%s)" % uri)
            return self._issue_restart()
        self.console.debug("Block reported: %d (%s)" % (current_block, uri))

        restart_trigger = False
        if (actual_highest < current_block):
            # Why are our canonical sources behind this instance?
            self.console.warn("Canonical source %s is behind this node." % provider)
        elif (actual_highest > current_block):
            # calculate delta and handle messaging
            delta = actual_highest - current_block
            if syncing is True:
                # node is still syncing.
                if delta >= self.allow_trailing_syncing:
                    if self.ignore_firstrun_node and current_block == 0:
                        self.console.info("Node trailing (Δ %d), ignored because of firstrun (%s)" % (delta, uri))
                    else:
                        self.console.warn("✘  Node (syncing) trailing (Δ %d), attempting restart (%s)" % (delta, uri))
                        return self._issue_restart(delta)
            else:
                if delta >= self.allow_trailing_stalled:
                     self.console.warn("✘  Node (stalled) trailing (Δ %d), attempting restart (%s)" % (delta, uri))
                     return self._issue_restart(delta)

        if restart_trigger is False:
            self.console.debug("✅  Node within spec (Δ %d) (%s)" % ((actual_highest - current_block), uri))
        return True


    def _issue_restart(self, blockdelta=None):
        """Issue a restart, but only if the time is not within the grace period."""
        now = time.time()
        if self.last_restart is None:
            self.last_restart = now
            return True

        if self.restart_grace_period_strategy == 'fixed':
            delta = (now - self.last_restart)
            if delta > self.restart_grace_period_sec:
                self.last_restart = time.time()
                return True
        elif self.restart_grace_period_strategy == 'adaptive':
            if self.adaptive_grace_period_target is None:
                if blockdelta is None:
                    # got a connection error, just restart
                    self.last_restart = time.time()
                    return True
                else:
                    self.adaptive_grace_period_target = now + (blockdelta *
                        self.restart_grace_period_adaptive_blocks_per_sec)
                    self.console.debug("Adaptive grace period set to catch " + \
                        "up on block delta. Time set to %s." % \
                        time.strftime('%Y-%m-%d %H:%M:%S',
                            time.localtime(self.adaptive_grace_period_target)))
            if now >= self.adaptive_grace_period_target:
                self.console.debug("Time has not yet reached adaptive grace period, ignoring.")
                self.last_restart = time.time()
                return True
        return False


    def _get_current_highest_block_geth(self, uri, reportSyncing=False):
        """Get the highest block geth is currently at"""
        if reportSyncing:
            syncing = (self.web3_geth.eth.syncing is not False)
            return (self.web3_geth.eth.blockNumber, syncing)
        return self.web3_geth.eth.blockNumber