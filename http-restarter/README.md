# Quarian HTTP Restarter

This is a simple, Flask-based HTTP-RPC endpoint that you can use on remote geth
nodes. If this is listening on your geth server, you can then use Quarian to
restart it remotely vs. running Quarian on every endpoint in your cluster.

Authentication may happen via PSK (pre-shared key) or "noauth" internally. This
is because Quarian does not want to handle authentication, and shouldn't. In
most production instances this RPC API should be behind an HTTP reverse proxy
which handles the heavy lifting and filters requests to this endpoint. For
example, I do not personally use the PSK endpoint, and rely on nginx and a PKI
to handle [mutual TLS authentication](https://en.wikipedia.org/wiki/Mutual_authentication).

### Usage

This script, like Quarian, requires Python 3. On your server running geth, you
will need to:

0. Copy this directory and your Quarian `settings.conf`.
1. `pip3 install -r requirements.txt`
2. `python3 restart.py`

This script will then run and will listen for requests. `POST` to `/restart` will
issue the command `restart_command` as a shell command.

### Configuring Quarian to use it

You will need to change Quarian to use `http` instead of `shell` in its
`restart_command_type` field. Assuming you are using the Quarian defaults,
set `restart_command` to `http://$NODE_URI:8546/restart`. This will make a GET
request to the restart endpoint.