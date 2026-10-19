"""Serve only pinned, locally captured assets; never act as an open proxy."""
import hashlib
import json
import re
import threading
from urllib.parse import urlsplit
from . import innertube
from .store import DATA

CAPTURE_LOCK = threading.Lock()


def asset_path(name):
    if not re.fullmatch(r'[0-9a-f]{64}\.(js|css|png|jpg|webp|svg|woff2?|ico)', name):
        return DATA / 'client' / '__missing__'
    return DATA / 'client' / 'assets' / name


def original_asset(path, source_url=None):
    """Resolve dynamic root-relative requests only if the asset is already pinned."""
    try:
        manifest = json.loads((DATA / 'client' / 'manifest.json').read_text())
        for entry in manifest['assets']:
            matches = entry['url'] == source_url if source_url else urlsplit(entry['url']).path == path
            if matches:
                return asset_path(entry['file'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return DATA / 'client' / '__missing__'


def dynamic_asset(path, origin):
    """Cache lazy client chunks from fixed public static paths, never arbitrary URLs."""
    from scripts.fetch_client import allowed, fetch, rewrite_origins
    missing = DATA / 'client' / '__missing__'
    url = 'https://www.youtube.com' + path
    if path.startswith('/client-static/fonts/'):
        url = 'https://fonts.gstatic.com/' + path.removeprefix('/client-static/fonts/')
    elif path.startswith('/client-static/branding/'):
        url = 'https://www.gstatic.com/' + path.removeprefix('/client-static/branding/')
    source_path = urlsplit(url).path
    if not re.fullmatch(r'/[A-Za-z0-9_.,=/\-]+', source_path) or '..' in source_path:
        return missing
    if not allowed(url):
        return missing
    existing = original_asset(source_path, url)
    if existing.is_file():
        return existing
    with CAPTURE_LOCK:
        existing = original_asset(source_path, url)
        if existing.is_file():
            return existing
        manifest_path = DATA / 'client' / 'manifest.json'
        try:
            manifest = json.loads(manifest_path.read_text())
            entries = manifest['assets']
            if len(entries) >= 500:
                return missing
            directory = DATA / 'client' / 'assets'
            used = sum(f.stat().st_size for f in directory.iterdir() if f.is_file())
            if used >= 384 * 1024 * 1024:
                return missing
            raw = fetch(url)
            if used + len(raw) > 384 * 1024 * 1024 or raw.lstrip().lower().startswith(b'<!doctype html'):
                return missing
            name = asset_name(url)
            served = rewrite_origins(raw.decode(), origin).encode() if name.endswith(('.js', '.css')) else raw
            temporary = directory / (name + '.tmp')
            temporary.write_bytes(served)
            temporary.replace(directory / name)
            entries.append({'url': url, 'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                            'served_sha256': hashlib.sha256(served).hexdigest(), 'runtime': True})
            staged = manifest_path.with_suffix('.json.tmp')
            staged.write_text(json.dumps(manifest, indent=2))
            staged.replace(manifest_path)
            return directory / name
        except (OSError, ValueError, KeyError, TypeError):
            return missing


def replace_json_assignment(html, name, value):
    pattern = re.compile(r'(?:var\s+)?' + re.escape(name) + r'\s*=\s*')
    for match in reversed(list(pattern.finditer(html))):
        try:
            _, end = json.JSONDecoder().raw_decode(html[match.end():])
        except ValueError:
            continue
        encoded = json.dumps(value, separators=(',', ':')).replace('<', '\\u003c')
        html = html[:match.end()] + encoded + html[match.end() + end:]
    return html


def shell(c, origin, watch_id=None, search_query=None):
    target = DATA / 'client' / ('watch.html' if watch_id else 'index.html')
    if not target.is_file():
        return None
    html = target.read_text()
    operation = 'next' if watch_id else ('search' if search_query is not None else 'browse')
    initial = innertube.response(c, operation, {'videoId': watch_id, 'query': search_query or ''}, origin)
    # Keep the guest masthead's renderer structure; replacing it with only feed
    # contents leaves the actual client's header as a permanent loading skeleton.
    match = re.search(r'(?:var\s+)?ytInitialData\s*=\s*', html)
    if match:
        try:
            guest, _ = json.JSONDecoder().raw_decode(html[match.end():])
            topbar = guest.get('topbar', {}).get('desktopTopbarRenderer')
            if isinstance(topbar, dict):
                topbar['topbarButtons'] = [{'buttonRenderer': {'style': 'STYLE_SUGGESTIVE', 'size': 'SIZE_SMALL',
                    'text': {'runs': [{'text': 'MewTube account'}]},
                    'navigationEndpoint': {'urlEndpoint': {'url': '/?signin=1'},
                        'commandMetadata': {'webCommandMetadata': {'url': '/?signin=1'}}}}}]
                initial['topbar'] = {'desktopTopbarRenderer': topbar}
        except (ValueError, AttributeError, TypeError):
            pass
    html = replace_json_assignment(html, 'ytInitialData', initial)
    player = innertube.response(c, 'player', {'videoId': watch_id}, origin) if watch_id else {}
    html = replace_json_assignment(html, 'ytInitialPlayerResponse', player)
    if watch_id:
        try:
            source_id = json.loads((DATA / 'client' / 'manifest.json').read_text()).get('watchSourceId', '')
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', source_id):
                html = html.replace(source_id, watch_id)
        except (OSError, ValueError, TypeError):
            pass
    # The bridge executes before captured inline code; all network APIs stay local.
    html = html.replace('<head>', '<head><script src="/bridge.js"></script>', 1)
    html = re.sub(r'<base\b[^>]*>', '', html, flags=re.I)
    html = re.sub(r'<link\b[^>]*rel=["\'](?:preconnect|dns-prefetch)["\'][^>]*>', '', html, flags=re.I)
    return html.encode()


def asset_name(url):
    suffix = url.split('?', 1)[0].rsplit('.', 1)[-1].lower()
    if '/s/_/ytmainappweb/_/js/' in url:
        suffix = 'js'
    elif '/s/_/ytmainappweb/_/ss/' in url:
        suffix = 'css'
    if suffix not in ('js', 'css', 'png', 'jpg', 'webp', 'svg', 'woff', 'woff2', 'ico'):
        return None
    return hashlib.sha256(url.encode()).hexdigest() + '.' + suffix
