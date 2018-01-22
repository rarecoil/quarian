#!/usr/bin/env python3

import argparse
from quarian.common.core import Quarian

def main():
    parser = argparse.ArgumentParser(description="Monitors delinquent Geth nodes.")
    parser.add_argument('--settings-file', default=None,
        help="Path to a settings.conf file to use over default settings.")
    parser.add_argument('--loglevel', default='info',
        help="Log level.")
    args = parser.parse_args()
    q = Quarian(args)
    q.check_every()

if __name__ == "__main__":
    main()