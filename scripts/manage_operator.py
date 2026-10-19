#!/usr/bin/env python3
"""Grant or revoke operator rights from the host console, never by first signup."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mewtube.store import db, init

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['grant', 'revoke'])
parser.add_argument('username')
args = parser.parse_args()
init()
with db() as c:
    result = c.execute('UPDATE users SET admin=? WHERE username=?', (int(args.action == 'grant'), args.username))
    if not result.rowcount:
        raise SystemExit('No such account. Register on your instance first.')
print('Operator rights updated.')
