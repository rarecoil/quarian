# checks

In this directory are Quarian's various checks. If you want to write your own
check for quarian, just dump it in this directory and add it to your config.
For an example of a simple check, see `cron.py`, which simply triggers whenever
a certain amount of time has passed.

Note that all checks need to inherit from interface `interface.py`. Using
the interface's constructor will give you Web3 facilities to geth and the
reference node as `self.web3_geth` and `self.web3_reference`, respectively,
as well as `common.output` as `self.console` which works similarly to a JS
developer console (e.g. `console.info`, `console.warn`).