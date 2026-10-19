import importlib.util
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
from unittest.mock import patch
import mewtube.snapshot as snapshot
from mewtube.snapshot import asset_name, replace_json_assignment, asset_path

spec = importlib.util.spec_from_file_location('fetch_client', Path(__file__).resolve().parents[1] / 'scripts' / 'fetch_client.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class SnapshotTests(unittest.TestCase):
    def test_lazy_chunks_are_fixed_host_bounded_and_cached(self):
        import scripts.fetch_client as downloader
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'client' / 'assets').mkdir(parents=True)
            (root / 'client' / 'manifest.json').write_text('{"assets":[]}')
            path = '/s/_/ytmainappweb/_/js/k=test/m=watch'
            with patch.object(snapshot, 'DATA', root), patch.object(downloader, 'fetch', return_value=b'fetch("https://www.youtube.com/youtubei/v1/player")') as fetch:
                output = snapshot.dynamic_asset(path, 'http://localhost:3000')
                self.assertTrue(output.is_file())
                self.assertIn('http://localhost:3000/youtubei', output.read_text())
                self.assertEqual(snapshot.dynamic_asset(path, 'http://localhost:3000'), output)
                self.assertEqual(snapshot.dynamic_asset('/s/../../secret.js', 'http://localhost:3000').name, '__missing__')
                self.assertEqual(snapshot.dynamic_asset('/s/private/account.js', 'http://localhost:3000').name, '__missing__')
                fetch.assert_called_once_with('https://www.youtube.com' + path)

    def test_guest_masthead_preserved_and_account_link_is_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'client').mkdir()
            original = {'topbar': {'desktopTopbarRenderer': {
                'searchbox': {'fusionSearchboxRenderer': {'placeholderText': {'simpleText':'Search'}}},
                'topbarButtons': [{'buttonRenderer': {'navigationEndpoint': {'urlEndpoint': {'url':'https://accounts.google.test/'}}}}]}}}
            (root / 'client' / 'index.html').write_text('<html><head></head><script>var ytInitialData = '+json.dumps(original)+';</script></html>')
            with patch.object(snapshot, 'DATA', root), patch.object(snapshot.innertube, 'response', return_value={'contents': {'local':True}}):
                result = snapshot.shell(None, 'http://localhost:3000').decode()
            self.assertIn('fusionSearchboxRenderer', result)
            self.assertIn('/?signin=1', result)
            self.assertNotIn('accounts.google.test', result)
            self.assertIn('"local":true', result)
            self.assertIn('src="/bridge.js"', result)

    def test_console_scripts_start_in_fresh_interpreters(self):
        root = Path(__file__).resolve().parents[1]
        for script in ('fetch_client.py', 'manage_operator.py'):
            result = subprocess.run([sys.executable, str(root / 'scripts' / script), '--help'],
                                    cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)

    def test_modern_bundle_and_restricted_hosts(self):
        url = 'https://www.youtube.com/s/_/ytmainappweb/_/js/k=build/m=kevlar_base_module,kevlar_main_module'
        self.assertTrue(capture.allowed(url))
        self.assertTrue(asset_name(url).endswith('.js'))
        self.assertIn(url, capture.references('<script src="' + url + '"></script>'))
        self.assertFalse(capture.allowed('https://www.youtube.com.evil.test/s/player/test.js'))
        self.assertFalse(capture.allowed('http://127.0.0.1/s/player/test.js'))
        self.assertEqual(asset_path('../../secret').name, '__missing__')
        source = 'fetch("https://youtubei.googleapis.com/youtubei/v1/player");var x="https:\\/\\/www.youtube.com/youtubei/v1/guide";'
        rewritten = capture.rewrite_origins(source, 'http://localhost:3000')
        self.assertNotIn('googleapis.com', rewritten)
        self.assertNotIn('www.youtube.com', rewritten)
        self.assertIn('http://localhost:3000/youtubei/v1/player', rewritten)

    def test_bootstrap_replaced_without_script_injection(self):
        original = '<script>var ytInitialData = {"secret":"visitor-id", "nested":{"x":"};"}}; next();</script>'
        result = replace_json_assignment(original, 'ytInitialData', {'title':'</script><script>alert(1)</script>'})
        self.assertNotIn('visitor-id', result)
        self.assertEqual(result.count('</script>'), 1)
        self.assertIn('next();', result)


if __name__ == '__main__':
    unittest.main()
