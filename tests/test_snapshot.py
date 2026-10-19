import importlib.util
import json
from pathlib import Path
import unittest
from mewtube.snapshot import asset_name, replace_json_assignment, asset_path

spec = importlib.util.spec_from_file_location('fetch_client', Path(__file__).resolve().parents[1] / 'scripts' / 'fetch_client.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class SnapshotTests(unittest.TestCase):
    def test_modern_bundle_and_restricted_hosts(self):
        url = 'https://www.youtube.com/s/_/ytmainappweb/_/js/k=build/m=kevlar_base_module,kevlar_main_module'
        self.assertTrue(capture.allowed(url))
        self.assertTrue(asset_name(url).endswith('.js'))
        self.assertIn(url, capture.references('<script src="' + url + '"></script>'))
        self.assertFalse(capture.allowed('https://www.youtube.com.evil.test/s/player/test.js'))
        self.assertFalse(capture.allowed('http://127.0.0.1/s/player/test.js'))
        self.assertEqual(asset_path('../../secret').name, '__missing__')

    def test_bootstrap_replaced_without_script_injection(self):
        original = '<script>var ytInitialData = {"secret":"visitor-id", "nested":{"x":"};"}}; next();</script>'
        result = replace_json_assignment(original, 'ytInitialData', {'title':'</script><script>alert(1)</script>'})
        self.assertNotIn('visitor-id', result)
        self.assertEqual(result.count('</script>'), 1)
        self.assertIn('next();', result)


if __name__ == '__main__':
    unittest.main()
