"""
    interface.py
    Quarian Check Base Class
"""

from web3 import Web3, HTTPProvider
from quarian.common.output import Output

class CheckBase(object):

    web3_reference = None
    web3_geth = None
    console = None

    global_options = None
    check_options = None

    def __init__(self, global_options, check_options, core):
        """Configures the check. Do bootstrapping here."""
        self.global_options = global_options
        self.check_options = check_options
        self.web3_reference = Web3(HTTPProvider(self.global_options['reference_node']))
        self.core = core
        self.console = core.console

    def set_geth_instance(self, uri):
        """Set self.web3_geth for check module use."""
        self.web3_geth = Web3(HTTPProvider(uri))

    def check(self, uri):
        """Returns a Boolean on whether or not Quarian should restart Geth."""
        raise NotImplementedError(
            "The check method has not been implemented by this check.\n" + \
            "All Quarian checks must have a check method. Please add this.")