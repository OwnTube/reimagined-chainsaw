import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from mewtube import store

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'MewTube disposable browser liked-playlist fixture'


class BrowserFixtureTests(unittest.TestCase):
    def test_seed_cleanup_handles_dash_ids_and_preserves_user_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            with patch.object(store, 'DATA', data):
                store.init()
                with store.db() as c:
                    c.execute('INSERT INTO users(id,username,password) VALUES(?,?,?)', ('fixtureuser','fixture_user','unused'))
                    for identifier, description in [('fixturesrc1','Source content'),('-leading001',MARKER),('real-video1','User content')]:
                        c.execute("INSERT INTO videos(id,owner,title,description,status,duration,created) VALUES(?,?,?,?,'ready',1,100)",
                                  (identifier,'fixtureuser',identifier,description))
                        directory = data / 'media' / identifier
                        directory.mkdir()
                        for name in ['video.mp4','thumb.jpg']:(directory / name).write_bytes(b'Local fixture bytes')
            env = {**os.environ, 'DATA_DIR':str(data)}
            def run(*args):
                return subprocess.run([sys.executable,str(ROOT / 'scripts/seed_browser_library.py'),*args],
                                      cwd=ROOT,env=env,text=True,capture_output=True,timeout=10,check=True)
            seeded = json.loads(run('seed','--source','fixturesrc1','--user','fixtureuser').stdout)
            self.assertEqual(len(seeded['ids']),40)
            run('clean','--ids-json',json.dumps(seeded['ids']+['-leading001','real-video1']))
            with sqlite3.connect(data / 'mewtube.sqlite3') as c:
                self.assertEqual(set(row[0] for row in c.execute('SELECT id FROM videos')), {'fixturesrc1','real-video1'})
                self.assertEqual(c.execute('SELECT count(*) FROM likes').fetchone()[0],0)
            self.assertTrue((data / 'media/real-video1/video.mp4').is_file())
            self.assertTrue((data / 'media/fixturesrc1/video.mp4').is_file())
            self.assertTrue(all(not (data / 'media' / identifier).exists() for identifier in seeded['ids']+['-leading001']))
