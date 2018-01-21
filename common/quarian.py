#!/usr/bin/env python3
"""
    Quarian
    Quarian class
"""

import os
import shlex
import subprocess
import time
import urllib

import requests
import web3

from configparser import ConfigParser
from common.output import Output

class Quarian(object):
    """Quarian primary class. Expects to be run locally with
    a single Geth instance."""

    SUPPORTED_SOURCES = ['geth','etherscan','etherchain']

    # actual flags/options
    # if you add something here, whitelist it in _load_settings
    reference_node = "http://localhost:8545/"
    user_agent = "Quarian/0.1 (//github.com/10a7/quarian)"
    check_every = 8
    loglevel = "debug"
    etherscan_api_key = "PUT_YOUR_API_KEY_HERE"
    restart_command = "supervisorctl restart geth"
    restart_command_type = "shell"
    nodelist = ["http://localhost:8545/"]
    allow_trailing_syncing = 500
    allow_trailing_stalled = 50
    check_every_seconds = 8
    ignore_firstrun_node = True
    get_highest_from = 'etherscan'

    last_block_height_check = None
    check_block_height_every_sec = 60
    allow_lag_of = 50 # allow geth to trail behind this many blocks


    def __init__(self, args):
        self.console = Output()
        self._load_settings(args.settings_file)
        if args.loglevel:
            self.loglevel = args.loglevel

        self.console.set_loglevel(self.loglevel)
        self.console.info("Quarian started.")
        self.web3 = web3.Web3(web3.HTTPProvider(self.reference_node))


    def check(self, uri, highest=None):
        """Check on Geth, and restart."""
        self.console.debug("Checking node... (%s)" % uri)
        try:
            if highest is None:
                actual_highest, provider = self.get_highest_known_block()
            current_block, syncing  = self._get_current_highest_block_geth(uri, True)
        except requests.exceptions.ConnectionError:
            self.console.error("Connection Failed, attempting restart (%s)" % uri)
            self._restart_geth(uri)
            return
        except requests.exceptions.Timeout:
            self.console.error("Connection Timeout, attempting restart (%s)" % uri)
            self._restart_geth(uri)
            return
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
                        restart_trigger = True
                    else:
                        self.console.warn("✘  Node (syncing) trailing (Δ %d), attempting restart (%s)" % (delta, uri))
                        self._restart_geth(uri)
                        restart_trigger = True
            else:
                if delta >= self.allow_trailing_stalled:
                     self.console.warn("✘  Node (stalled) trailing (Δ %d), attempting restart (%s)" % (delta, uri))
                     self._restart_geth(uri)
                     restart_trigger = True

        if restart_trigger is False:
            self.console.debug("✅  Node within spec (Δ %d) (%s)" % ((actual_highest - current_block), uri))


    def check_every(self, sec=None):
        if sec is None:
            sec = int(self.check_every_seconds)
        self.console.debug("Setting up polling at every %d seconds" % sec)
        actual_highest, provider = self.get_highest_known_block()
        self.console.info("Actual highest block: %d via %s" % (actual_highest, provider))
        while True:
            for node in self.nodelist:
                if node.find("http://") != 0:
                    node = 'http://' + node
                self.check(node)
            time.sleep(sec)


    def get_highest_known_block(self):
        """Get the highest known block from data sources."""
        highest = []
        providers = []
        for source in self.get_highest_from:
            try:
                if source == 'etherscan':
                    res = self._get_highest_known_block_etherscan()
                    if res is not False:
                        highest.append(res)
                        providers.append('etherscan')
                elif source == 'etherchain':
                    res = self._get_highest_known_block_etherchain()
                    if res is not False:
                        highest.append(res)
                        providers.append('etherchain')
                elif source == 'geth':
                    res = self._get_highest_known_block_geth(self.DEFAULTS['geth_location'])
                    highest.append(res)
                    providers.append('geth')
                else:
                    self.console.warn("Unknown blockchain provider %s" % source)
            except:
                self.console.error("Error getting highest block from source %s" % source)
        best = max(highest)
        provider = providers[highest.index(best)]
        return (best, provider)


    def _geth_is_syncing(self):
        """check if geth is syncing"""
        return (self.web3.eth.syncing is not False)


    def _get_current_highest_block_geth(self, uri, reportSyncing=False):
        """Get the highest block geth is currently at"""
        webthree = web3.Web3(web3.HTTPProvider(uri))
        if reportSyncing:
            syncing = (webthree.eth.syncing is not False)
            return (webthree.eth.blockNumber, syncing)
        return webthree.eth.blockNumber


    def _get_highest_known_block_geth(self):
        """Get the highest block from the local geth, the highest known
        if geth is still syncing. Note that this is likely not going to
        be tracking the true highest if you are just syncing or geth
        is really far behind."""
        try:
            syncing = self.web3.eth.syncing
            if syncing is False:
                return (self.web3.eth.blockNumber, syncing)
            else:
                return self.web3.eth.syncing['highestBlock']
        except requests.ConnectionError:
            self.console.error("Can't connect to canonical geth.")


    def _get_highest_known_block_etherscan(self):
        """Get the highest block from etherscan"""
        uri = "https://api.etherscan.io/api"
        res = requests.get(uri,
            data={ 'module': 'proxy', 'action':
                'eth_blockNumber',
                'apikey': self.etherscan_api_key },
            headers= { 'user-agent': self.user_agent },
            timeout=5)

        if res.status_code == 200 and res.json():
            try:
                block_number = int(res.json()['result'], 16)
                return block_number
            except KeyError:
                return False
        return False


    def _get_highest_known_block_etherchain(self):
        """Get the highest block from etherchain.org as nicely as possible"""

        uri = 'https://www.etherchain.org/blocks/data?draw=0&start=0&length=0'
        res = requests.get(uri,
            headers = { 'user-agent': self.user_agent },
            timeout=5)
        if res.status_code == 200:
            try:
                return res.json()['recordsTotal']
            except KeyError:
                return False
        return False


    def _restart_geth(self, uri):
        """Restarts geth based upon restart_command. returns Boolean."""
        self.console.debug("Restart geth on node (%s)" % uri)
        return # short circuit for testing other functionality

        if self.restart_command_type == 'shell':
            # dont trust this wont expand later, escape it for shell
            # this seems exactly like the kind of thing that will come in
            # from a DB and we don't want injection
            uri = shlex.quote(uri)
            cmd = self.restart_command.replace("$NODE_URL", uri)
            self.console.debug("Executing SHELL command `%s`" % cmd)
            proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                self.console.error("Subprocess returned status code %d" % proc.returncode)
                return False
            self.console.debug("Subprocess STDOUT: %s" % stdout)
            self.console.debug("Subprocess STDERR: %s" % stderr)
            return True

        elif self.restart_command_type == 'http':
            cmd = self.restart_command.replace("$NODE_URL", urllib.quote(uri))
            self.console.debug("Executing GET to NODE_URL %s" % self.restart_command)
            try:
                res = requests.get(self.restart_command,
                    headers = { 'user-agent': self.user_agent },
                    timeout=5)
                if res.status_code == 200:
                    return True
                else:
                    self.console.error("Restart URI returned %d" % (res.status_code))
                    return False
            except requests.ConnectionError:
                self.console.error("Restart command failed with connection error (%s)" % self.restart_command)
                return False
            except requests.ConnectTimeout:
                self.console.error("Restart command failed with timeout (%s)" % self.restart_command)
                return False


    def _load_settings(self, settings_file=None):
        """Load settings.conf"""
        candidate_locations = [
             os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'settings.conf')),
            '/etc/quarian/settings.conf',
            '/etc/quarian.conf',
            '/etc/default/quarian.conf',
            '/opt/quarian/settings.conf'
        ]
        # override if arg forced
        if settings_file is not None:
            candidate_locations = [settings_file]

        for location in candidate_locations:
            if os.path.isfile(location):
                self.console.info("Using settings file %s" % location)

        config = ConfigParser()
        config.read(location)

        whitelisted_settings = [
            'reference_node',
            'user_agent',
            'check_every_seconds',
            'loglevel',
            'etherscan_api_key',
            'restart_command',
            'restart_command_type',
            'nodelist',
            'allow_trailing_syncing',
            'allow_trailing_stalled',
            'get_highest_from',
            'ignore_firstrun_node'
        ]

        if 'quarian' in config.sections():
            for setting in whitelisted_settings:
                try:
                    if setting == 'nodelist':
                        self.nodelist = config['quarian']['nodelist'].split(',')
                    elif setting == 'get_highest_from':
                        potential_list = config['quarian']['get_highest_from'].split(',')
                        self.get_highest_from = potential_list
                    elif setting in ['check_every_seconds', 'allow_trailing_syncing', 'allow_trailing_stalled']:
                        self.__setattr__(setting, int(config['quarian'][setting]))
                    else:
                        self.__setattr__(setting, config['quarian'][setting])
                except KeyError:
                    self.console.info("Settings file is missing key %s, using default" % setting)
                    continue
        else:
            self.console.warn("Settings file is missing [quarian] section.")

