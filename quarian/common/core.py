#!/usr/bin/env python3
"""
    Quarian
    Quarian class
"""

import glob
import importlib
import os
import shlex
import subprocess
import sys
import re
import time
import urllib

import requests
import web3

from configparser import ConfigParser
from .output import Output

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
    checklist = ['cron']
    allow_trailing_syncing = 500
    allow_trailing_stalled = 50
    check_every_seconds = 8
    ignore_firstrun_node = True
    get_highest_from = 'etherscan'

    check_options = {}
    global_options = {}


    def __init__(self, args):
        self.console = Output()
        if args.loglevel:
            self.loglevel = args.loglevel
        self.console.set_loglevel(self.loglevel)

        self._load_settings(args.settings_file)
        self._load_checks()

        self.console.info("Quarian started.")
        self.web3 = web3.Web3(web3.HTTPProvider(self.reference_node))


    def check(self, uri):
        """Check on Geth, and restart."""
        for check in self.checklist:
            check.set_geth_instance(uri)
            res = check.check(uri)
            if res == True:
                self._restart_geth(uri)
            else:
                continue


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
                elif source == 'infura':
                    res = self._get_highest_known_block_infura()
                    if res is not False:
                        highest.append(res)
                        providers.append('infura')
                elif source == 'geth':
                    res = self._get_highest_known_block_geth(self.DEFAULTS['geth_location'])
                    highest.append(res)
                    providers.append('geth')
                else:
                    self.console.warn("Unknown blockchain provider %s" % source)
            except:
                self.console.error("Error getting highest block from source %s" % source)
        if len(highest) == 0:
            self.console.error("Do not have a highest block from sources.")
            return (0, 'failure')
        best = max(highest)
        provider = providers[highest.index(best)]
        return (best, provider)


    def _geth_is_syncing(self):
        """check if geth is syncing"""
        return (self.web3.eth.syncing is not False)


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

    def _get_highest_known_block_infura(self):
        """Get the highest known block from Consensys Infura"""
        infura_uri = "https://mainnet.infura.io/%s" % (self.infura_api_key)
        try:
            infura_web3 = web3.Web3(web3.HTTPProvider(infura_uri))
            number = infura_web3.eth.blockNumber
            return int(number)
        except:
            self.console.error("Could not retrieve from Infura.")
        return False

    def _restart_geth(self, uri):
        """Restarts geth based upon restart_command. returns Boolean."""
        self.console.debug("Restart geth on node (%s)" % uri)

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


    def _load_checks(self):
        """Loads checks from the checks directory."""
        check_class_list = []
        checks_directory = os.path.realpath(os.path.join(
                                os.path.dirname(__file__), '..', 'checks'))
        self.console.debug("Loading checks from directory %s" % checks_directory)
        for filepath in glob.glob(os.path.join(checks_directory, '*.py')):
            if os.path.basename(filepath) == 'base.py':
                self.console.debug("Skipping analysis of base.py")
            class_re = "class\s+(.*)\([\w_]*[\s,]*CheckBase[\s,]*.*\)"
            compiled_class_re = re.compile(class_re)
            with open(filepath, 'r') as f:
                class_file = f.read().split("\n")
                for line in class_file:
                    result = re.match(compiled_class_re, line)
                    if result is not None:
                        class_name = result.groups()[0]
                        self.console.debug("Found class name %s in %s" % (class_name, filepath))
                        instance = self._instantiate_from_filepath(filepath, class_name)
                        check_class_list.append(instance)
        # instantiate class instances
        self.checklist = check_class_list


    def _instantiate_from_filepath(self, filepath, className):
        """Instantiate a check class from a filepath and className."""
        check_module = os.path.basename(filepath).replace('.py', '')
        mod = importlib.import_module("quarian.checks.%s" % check_module)
        cls = getattr(mod, className)
        self.console.debug("-> Importing class %s" % str(cls))
        check_options = {}
        if not check_module in self.check_options:
            self.console.warn("No options specified for check %s in file." % check_module)
        else:
            check_options = self.check_options[check_module]
        return cls(self.global_options, check_options, self)


    def _load_settings(self, settings_file=None):
        """Load settings.conf"""
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
                self.console.info("Using settings file %s" % location)
                location_filepath = location

        if location_filepath is None:
            raise FileNotFoundError("Cannot find Quarian configuration file.")

        config = ConfigParser()
        config.read(location_filepath)

        whitelisted_settings = [
            'reference_node',
            'user_agent',
            'check_every_seconds',
            'loglevel',
            'etherscan_api_key',
            'restart_command',
            'restart_command_type',
            'nodelist',
            'get_highest_from',
            'ignore_firstrun_node',
            'checklist',
            'infura_api_key'
        ]

        if 'quarian' not in config.sections():
            self.console.error("[quarian] section missing in configuration.")

        for section in config.sections():
            if section == 'quarian':
                for setting in whitelisted_settings:
                    try:
                        if setting in ['nodelist', 'checklist']:
                            exploded = config['quarian'][setting].split(',')
                            self.__setattr__(setting, exploded)
                            self.global_options[setting] = exploded
                        elif setting == 'get_highest_from':
                            potential_list = config['quarian']['get_highest_from'].split(',')
                            self.get_highest_from = potential_list
                            self.global_options['get_highest_from'] = self.get_highest_from
                        elif setting in ['check_every_seconds', 'allow_trailing_syncing', 'allow_trailing_stalled']:
                            self.__setattr__(setting, int(config['quarian'][setting]))
                            self.global_options[setting] = int(config['quarian'][setting])
                        else:
                            self.__setattr__(setting, config['quarian'][setting])
                            self.global_options[setting] = config['quarian'][setting]
                    except KeyError:
                        self.console.info("Settings file is missing key %s, using default" % setting)
                        continue
            elif section.find("quarian:check:") == 0:
                check_name = section[14:]
                self.check_options[check_name] = dict(config[section])

