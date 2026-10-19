"""Serve only pinned, locally captured assets; never act as an open proxy."""
import hashlib
import json
import re
from urllib.parse import urlsplit
from . import innertube
from .store import DATA


def asset_path(name):
    if not re.fullmatch(r'[0-9a-f]{64}\.(js|css|png|jpg|webp|svg|woff2?|ico)', name):
        return DATA / 'client' / '__missing__'
    return DATA / 'client' / 'assets' / name


def original_asset(path):
    """Resolve dynamic root-relative requests only if the asset is already pinned."""
    try:
        manifest = json.loads((DATA / 'client' / 'manifest.json').read_text())
        for entry in manifest['assets']:
            if urlsplit(entry['url']).path == path:
                return asset_path(entry['file'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return DATA / 'client' / '__missing__'


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


def shell(c, origin):
    target = DATA / 'client' / 'index.html'
    if not target.is_file():
        return None
    html = target.read_text()
    initial = innertube.response(c, 'browse', {}, origin)
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
    html = replace_json_assignment(html, 'ytInitialPlayerResponse', {})
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
