#!/usr/bin/env python3
"""Bounded local browser-test fixtures; no HTTP endpoint or upstream data."""
import argparse
import json
import re
import secrets
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mewtube.store import DATA, db

MARKER = 'MewTube disposable browser liked-playlist fixture'
ID = re.compile(r'[A-Za-z0-9_-]{11}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'clean'])
    parser.add_argument('--source')
    parser.add_argument('--user')
    parser.add_argument('--ids', nargs='*', default=[])
    args = parser.parse_args()
    with db() as c:
        if args.action == 'clean':
            for identifier in args.ids:
                if not ID.fullmatch(identifier):
                    raise SystemExit('Invalid fixture identifier')
                row = c.execute('SELECT description FROM videos WHERE id=?', (identifier,)).fetchone()
                if row and row['description'] == MARKER:
                    c.execute('DELETE FROM videos WHERE id=?', (identifier,))
                    shutil.rmtree(DATA / 'media' / identifier, ignore_errors=True)
            print('{}')
            return
        if not args.source or not args.user or not ID.fullmatch(args.source) or not ID.fullmatch(args.user):
            raise SystemExit('A local source video and user are required')
        source = c.execute("SELECT * FROM videos WHERE id=? AND status='ready'", (args.source,)).fetchone()
        if not source or not c.execute('SELECT 1 FROM users WHERE id=?', (args.user,)).fetchone():
            raise SystemExit('Fixture source/user unavailable')
        directory = DATA / 'media' / args.source
        if not all((directory / name).is_file() for name in ('video.mp4', 'thumb.jpg')):
            raise SystemExit('Fixture media unavailable')
        identifiers = []
        for index in range(1, 41):
            identifier = secrets.token_urlsafe(8)
            target = DATA / 'media' / identifier
            target.mkdir()
            for name in ('video.mp4', 'thumb.jpg'):
                shutil.copyfile(directory / name, target / name)
            c.execute('''INSERT INTO videos(id,owner,title,description,status,duration,size,created)
                         VALUES(?,?,?,?,'ready',?,?,?)''',
                      (identifier, source['owner'], f'Pagination fixture {index:02}', MARKER,
                       source['duration'], source['size'], source['created'] - index))
            c.execute('INSERT INTO likes VALUES(?,?)', (args.user, identifier))
            identifiers.append(identifier)
        print(json.dumps({'ids': identifiers, 'lastTitle': 'Pagination fixture 40'}))


if __name__ == '__main__':
    main()
