import importlib.util
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
import contextlib
import io
from unittest.mock import patch, Mock
import mewtube.snapshot as snapshot
from mewtube.snapshot import asset_name, replace_json_assignment, asset_path

spec = importlib.util.spec_from_file_location('fetch_client', Path(__file__).resolve().parents[1] / 'scripts' / 'fetch_client.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class SnapshotTests(unittest.TestCase):
    def test_window_bootstrap_forms_and_unknown_format_fail_closed(self):
        for assignment in ('window["ytInitialData"]', "window [ 'ytInitialData' ]", 'window.ytInitialData', 'let ytInitialData'):
            source = '<script>'+assignment+' = {"title":"Upstream sample"};</script>'
            self.assertEqual(snapshot.read_json_assignment(source, 'ytInitialData'), {'title':'Upstream sample'})
            replaced = replace_json_assignment(source, 'ytInitialData', {'title':'Local </script> title'})
            self.assertNotIn('Upstream sample', replaced)
            self.assertEqual(replaced.count('</script>'), 1)
            self.assertEqual(snapshot.read_json_assignment(replaced, 'ytInitialData'), {'title':'Local </script> title'})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'client').mkdir()
            (root / 'client' / 'index.html').write_text('<script>window["ytInitialData"]=loadBootstrap();</script>')
            with patch.object(snapshot, 'DATA', root):
                self.assertIsNone(snapshot.shell(None, 'http://localhost:3000'))

    def test_stringified_bootstrap_decodes_without_executing_javascript(self):
        payload = {'title': "Sample's </script> title", 'nested': {'text': 'brace }; and \\ quotes "'}}
        double = json.dumps(json.dumps(payload))
        single = "'" + double[1:-1].replace("'", "\\'") + "'"
        for literal in (double, single, r"'\x7b\x22title\x22:\x22Hex escape\x22\x7d'"):
            source = '<script>window["ytInitialData"] = JSON.parse('+literal+'); next();</script>'
            self.assertIsInstance(snapshot.read_json_assignment(source, 'ytInitialData'), dict)
            replaced = replace_json_assignment(source, 'ytInitialData', {'title':'Local </script>'})
            self.assertNotIn('JSON.parse(', replaced)
            self.assertEqual(replaced.count('</script>'), 1)
            self.assertIn('next();', replaced)
            self.assertEqual(snapshot.read_json_assignment(replaced, 'ytInitialData'), {'title':'Local </script>'})
        for expression in ('JSON.parse(makeData())', 'JSON.parse("{}", evil)', 'JSON.parse(\'\\xzz\')', 'loadBootstrap()'):
            self.assertIsNone(snapshot.read_json_assignment('var ytInitialData = '+expression, 'ytInitialData'))

    def test_local_player_adapter_is_scoped_and_preserves_original_gate(self):
        # Synthetic contract fixture, not downloaded client code.
        gate = ('var check=function(R){var context=R.responseContext.mainAppWebResponseContext;'
                'if(!context.trackingParam){var label="MISSING";throw Error("282054944_a");}'
                'return 7;};')
        adapted, count = capture.adapt_local_player(gate, 'http://localhost:3000')
        self.assertEqual(count, 1)
        self.assertIn('throw Error("282054944_a")', adapted)
        self.assertEqual(capture.adapt_local_player(adapted, 'http://localhost:3000'), (adapted, 0))
        self.assertEqual(capture.adapt_local_player('var unknown=function(){return 9;};', 'http://localhost:3000')[1], 0)
        script = adapted + '''
        const assert=require('node:assert/strict');
        global.window={location:{origin:'http://localhost:3000'}};
        const local={playabilityStatus:{status:'OK'},responseContext:{mainAppWebResponseContext:{mewtubeLocalResponse:true}}};
        assert.equal(check(local),1);
        const unmarked={playabilityStatus:{status:'OK'},responseContext:{mainAppWebResponseContext:{}}};
        assert.throws(()=>check(unmarked),/282054944_a/);
        local.playabilityStatus.status='ERROR';
        assert.throws(()=>check(local),/282054944_a/);
        local.playabilityStatus.status='OK';window.location.origin='https://www.youtube.com';
        assert.throws(()=>check(local),/282054944_a/);
        assert.equal(check({responseContext:{mainAppWebResponseContext:{trackingParam:'original'}}}),7);
        delete global.window;
        assert.equal(check({responseContext:{mainAppWebResponseContext:{trackingParam:'original'}}}),7);
        assert.throws(()=>check(unmarked),/282054944_a/);
        '''
        subprocess.run(['node', '-e', script], check=True, timeout=10)

    def test_capture_keeps_module_loader_url_contract(self):
        modern = 'https://www.youtube.com/s/_/ytmainappweb/_/js/k=build/m=base'
        html = '<html><head><script id="base-js" src="'+modern+'"></script></head><script>var ytInitialData={};var ytInitialPlayerResponse={};window._F_jsUrl="'+modern+'";</script><ytd-app></ytd-app></html>'
        def download(url):
            if url == 'https://www.youtube.com/' or '/watch?' in url:
                return html.encode()
            if '/results?' in url:
                return html.replace('var ytInitialData={};', 'var ytInitialData={"contents":{"twoColumnSearchResultsRenderer":{}}};').encode()
            return b'var loaded=true;' if '/_/js/' in url else b'<svg/>'
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(capture, 'DATA', Path(tmp)), patch.object(capture, 'fetch', side_effect=download), \
                 patch.dict('os.environ', {'PUBLIC_ORIGIN':'http://localhost:3000'}), \
                 patch.object(sys, 'argv', ['fetch_client.py']), contextlib.redirect_stdout(io.StringIO()):
                capture.main()
            shell = (Path(tmp) / 'client' / 'index.html').read_text()
            expected = 'http://localhost:3000/s/_/ytmainappweb/_/js/k=build/m=base'
            self.assertEqual(shell.count(expected), 2)
            self.assertNotIn('/client-assets/', shell)
            self.assertNotIn('www.youtube.com', shell)
            manifest = json.loads((Path(tmp) / 'client' / 'manifest.json').read_text())
            self.assertTrue(manifest['searchTemplate'])
            self.assertTrue((Path(tmp) / 'client' / 'search.html').is_file())
            entry = next(a for a in manifest['assets'] if a['url'] == modern)
            self.assertRegex(entry['file'], r'^[0-9a-f]{64}\.js$')
            self.assertTrue((Path(tmp) / 'client' / 'assets' / entry['file']).is_file())

    def test_lazy_chunks_are_fixed_host_bounded_and_cached(self):
        import scripts.fetch_client as downloader
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'client' / 'assets').mkdir(parents=True)
            (root / 'client' / 'manifest.json').write_text('{"assets":[]}')
            path = '/s/_/ytmainappweb/_/js/k=test/m=watch'
            with patch.object(snapshot, 'DATA', root), patch.object(downloader, 'fetch', return_value=b'fetch("https://www.youtube.com/youtubei/v1/player")') as fetch:
                miss = Mock()
                output = snapshot.dynamic_asset(path, 'http://localhost:3000', miss)
                self.assertTrue(output.is_file())
                self.assertIn('http://localhost:3000/youtubei', output.read_text())
                self.assertEqual(snapshot.dynamic_asset(path, 'http://localhost:3000', miss), output)
                miss.assert_called_once_with()
                with self.assertRaises(RuntimeError):
                    snapshot.dynamic_asset('/s/player/test/base.js', 'http://localhost:3000',
                                           Mock(side_effect=RuntimeError('Download quota reached')))
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
            with patch.object(snapshot, 'DATA', root), patch.object(snapshot.innertube, 'response', return_value={'contents': {}}):
                personal = snapshot.shell(None, 'http://localhost:3000', user={'username':'local_viewer'}).decode()
            self.assertIn('MewTube @local_viewer', personal)
            self.assertNotIn('MewTube @local_viewer', (root / 'client' / 'index.html').read_text())

    def test_console_scripts_start_in_fresh_interpreters(self):
        root = Path(__file__).resolve().parents[1]
        for script in ('fetch_client.py', 'manage_operator.py'):
            result = subprocess.run([sys.executable, str(root / 'scripts' / script), '--help'],
                                    cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)

    def test_search_reload_replaces_captured_home_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'client').mkdir()
            (root / 'client' / 'search.html').write_text('''<html><head></head><script>
                window['ytPageType']="browse"; window['ytCommand']={"browseEndpoint":{"browseId":"FEwhat_to_watch"}};
                window['ytUrl']='\\/results?search_query=upstream';
                var ytInitialData={"contents":{}};</script></html>''')
            query = 'Cats & <robots> 🐈'
            with patch.object(snapshot, 'DATA', root), patch.object(snapshot.innertube, 'response', return_value={'contents': {}}):
                result = snapshot.shell(None, 'http://localhost:3000', search_query=query).decode()
            command = snapshot.read_json_assignment(result, 'ytCommand')
            self.assertEqual(command['searchEndpoint']['query'], query)
            self.assertEqual(snapshot.read_json_assignment(result, 'ytUrl'), command['commandMetadata']['webCommandMetadata']['url'])
            self.assertEqual(snapshot.read_json_assignment(result, 'ytPageType'), 'search')
            self.assertEqual(command['commandMetadata']['webCommandMetadata']['webPageType'], 'WEB_PAGE_TYPE_SEARCH')
            self.assertNotIn('FEwhat_to_watch', result)
            self.assertNotIn('<robots>', result)
            self.assertNotIn('search_query=upstream', result)
            (root / 'client' / 'search.html').unlink()
            (root / 'client' / 'index.html').write_text('<script>var ytInitialData={};</script>')
            with patch.object(snapshot, 'DATA', root):
                self.assertIsNone(snapshot.shell(None, 'http://localhost:3000', search_query=query),
                                  'Missing search capture must not silently use a home template')

    def test_modern_bundle_and_restricted_hosts(self):
        url = 'https://www.youtube.com/s/_/ytmainappweb/_/js/k=build/m=kevlar_base_module,kevlar_main_module'
        self.assertTrue(capture.allowed(url))
        self.assertTrue(asset_name(url).endswith('.js'))
        self.assertIn(url, capture.references('<script src="' + url + '"></script>'))
        self.assertFalse(capture.allowed('https://www.youtube.com.evil.test/s/player/test.js'))
        self.assertFalse(capture.allowed('http://127.0.0.1/s/player/test.js'))
        self.assertTrue(capture.allowed('https://fonts.gstatic.com/s/i/youtube_outline_experimental/menu/v1/24px.svg'))
        self.assertFalse(capture.allowed('https://fonts.gstatic.com/private/account.js'))
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
