# quarian
#### control delinquent geth nodes

[Quarian](http://masseffect.wikia.com/wiki/Quarian) is a controller meant to
shepherd Geth instances that are not performing properly, and alert/report on
problems with a Geth instance. If Geth is not running properly, it will
restart Geth with a command of your choosing.

Features:

* **Remote node monitoring via JSON-RPC**: Can monitor remote nodes and issue
  HTTP requests to servers to cause geth restarts, if you have tooling on that
  side to restart geth
* **Easy to read logs**: Nice easy UTF-8 + color logging output to stdout
* **Multiple canonical sources for chain tip**: Supports Etherscan, Etherchain, and your own geth nodes


### Configuration

Settings for Quarian are specified in `settings.conf`. Quarian will look here
for settings, as well as:

* `/etc/quarian/settings.conf`
* `/etc/quarian.conf`
* `/etc/default/quarian.conf`
* `/opt/quarian/settings.conf`

in that order. The `settings.conf` file contains configuration information
for Quarian.


### Installation & Use

Quarian is alpha software and is not yet an egg. Quarian is written for **Python 3**. Download and run:

```
pip3 install -r requirements.txt
./quarian.py
```

There are also some argument flags. You can see these by using `quarian.py -h`.


### License

GNU GPL v3.