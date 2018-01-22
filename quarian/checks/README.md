# checks

In this directory are Quarian's various checks. If you want to write your own
check for quarian, just dump it in this directory and add it to your config.
For an example of a simple check, see `cron.py`, which simply triggers whenever
a certain amount of time has passed.

Note that all checks need to inherit from the base class `base.py`. Using
the base's constructor will give you Web3 facilities to geth and the
reference node as `self.web3_geth` and `self.web3_reference`, respectively,
as well as `common.output` as `self.console` which works similarly to a JS
developer console (e.g. `console.info`, `console.warn`).

The `check` method is the most important. It must return a boolean value.
If it returns `True`, Quarian will attempt to restart the geth node.