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


def dynamic_asset(path, origin, on_miss=None):
    """Cache lazy client chunks from fixed public static paths, never arbitrary URLs."""
    from scripts.fetch_client import allowed, fetch, rewrite_origins, adapt_local_player
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
        if on_miss:
            on_miss()
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
            adapted = 0
            if name.endswith(('.js', '.css')):
                source = rewrite_origins(raw.decode(), origin)
                if name.endswith('.js'):
                    source, adapted = adapt_local_player(source, origin)
                served = source.encode()
            else:
                served = raw
            temporary = directory / (name + '.tmp')
            temporary.write_bytes(served)
            temporary.replace(directory / name)
            entries.append({'url': url, 'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                            'served_sha256': hashlib.sha256(served).hexdigest(), 'runtime': True,
                            'localPlayerAdapter': adapted})
            staged = manifest_path.with_suffix('.json.tmp')
            staged.write_text(json.dumps(manifest, indent=2))
            staged.replace(manifest_path)
            return directory / name
        except (OSError, ValueError, KeyError, TypeError):
            return missing


def assignment_pattern(name):
    key = re.escape(name)
    return re.compile(r'(?<![\w$])(?:(?:var|let|const)\s+)?(?:' + key +
                      r'|window\s*(?:\.\s*' + key + r'|\[\s*["\']' + key + r'["\']\s*\]))\s*=\s*')


def decode_assignment(source):
    """Decode JSON or JSON.parse(string-literal), never execute captured code."""
    parse = re.match(r'JSON\.parse\(\s*', source)
    if not parse and not source.startswith("'"):
        return json.JSONDecoder().raw_decode(source)
    position = parse.end() if parse else 0
    if position >= len(source) or source[position] not in ('"', "'"):
        raise ValueError('Expected a string literal')
    quote = source[position]
    position += 1
    chars = []
    escapes = {'n':'\n', 'r':'\r', 't':'\t', 'b':'\b', 'f':'\f', 'v':'\v',
               '\\':'\\', '/':'/', '"':'"', "'":"'"}
    while position < len(source):
        char = source[position]
        position += 1
        if char == quote:
            if not parse:
                return ''.join(chars), position
            close = re.match(r'\s*\)', source[position:])
            if not close:
                raise ValueError('Only a single literal argument is supported')
            return json.loads(''.join(chars)), position + close.end()
        if char in '\n\r':
            raise ValueError('Unescaped line break')
        if char != '\\':
            chars.append(char)
            continue
        if position >= len(source):
            break
        escaped = source[position]
        position += 1
        if escaped in ('u', 'x'):
            size = 4 if escaped == 'u' else 2
            digits = source[position:position + size]
            if len(digits) != size or not re.fullmatch(r'[0-9A-Fa-f]+', digits):
                raise ValueError('Invalid string escape')
            chars.append(chr(int(digits, 16)))
            position += size
        elif escaped in escapes:
            chars.append(escapes[escaped])
        else:
            raise ValueError('Unsupported string escape')
    raise ValueError('Unterminated string literal')


def read_json_assignment(html, name):
    for match in assignment_pattern(name).finditer(html):
        try:
            value, _ = decode_assignment(html[match.end():])
            return value
        except ValueError:
            continue
    return None


def replace_json_assignment(html, name, value):
    pattern = assignment_pattern(name)
    for match in reversed(list(pattern.finditer(html))):
        try:
            _, end = decode_assignment(html[match.end():])
        except ValueError:
            continue
        encoded = json.dumps(value, separators=(',', ':')).replace('<', '\\u003c')
        html = html[:match.end()] + encoded + html[match.end() + end:]
    return html


def shell(c, origin, watch_id=None, search_query=None, user=None, browse_id=''):
    target = DATA / 'client' / ('watch.html' if watch_id else ('search.html' if search_query is not None else
                              ('playlist.html' if browse_id == 'VLLL' else 'index.html')))
    if not target.is_file():
        return None
    html = target.read_text()
    guest = read_json_assignment(html, 'ytInitialData')
    if not isinstance(guest, dict) or (watch_id and not isinstance(read_json_assignment(html, 'ytInitialPlayerResponse'), dict)):
        # Never serve an unrecognized bootstrap containing upstream titles,
        # actions or account destinations alongside our local media response.
        return None
    operation = 'next' if watch_id else ('search' if search_query is not None else 'browse')
    initial = innertube.response(c, operation, {'videoId': watch_id, 'query': search_query or '', 'browseId': browse_id}, origin, user)
    if initial is None:
        return None
    initial['mewtubeLocalBootstrap'] = True
    # Keep the guest masthead's renderer structure; replacing it with only feed
    # contents leaves the actual client's header as a permanent loading skeleton.
    if guest:
        try:
            topbar = guest.get('topbar', {}).get('desktopTopbarRenderer')
            if isinstance(topbar, dict):
                account_url = innertube.sign_in_url(watch_id)
                topbar['topbarButtons'] = [{'buttonRenderer': {'style': 'STYLE_SUGGESTIVE', 'size': 'SIZE_SMALL',
                    'text': {'runs': [{'text': 'MewTube @' + user['username'] if user else 'MewTube account'}]},
                    'navigationEndpoint': {'urlEndpoint': {'url': account_url},
                        'commandMetadata': {'webCommandMetadata': {'url': account_url}}}}}]
                if user:
                    button = topbar['topbarButtons'][0]['buttonRenderer']
                    button.pop('navigationEndpoint')
                    button['serviceEndpoint'] = innertube.account_menu_endpoint()
                initial['topbar'] = {'desktopTopbarRenderer': topbar}
        except (ValueError, AttributeError, TypeError):
            pass
    html = replace_json_assignment(html, 'ytInitialData', initial)
    if operation == 'browse':
        destination = (innertube.liked_endpoint() if browse_id == 'VLLL' else
                       innertube.channel_endpoint(browse_id) if browse_id and browse_id not in ('FEsubscriptions', 'FEwhat_to_watch')
                       else innertube.browse_endpoint(browse_id or 'FEwhat_to_watch',
                            '/feed/subscriptions' if browse_id == 'FEsubscriptions' else '/'))
        html = replace_json_assignment(html, 'ytCommand', destination)
        html = replace_json_assignment(html, 'ytUrl', destination['commandMetadata']['webCommandMetadata']['url'])
        if browse_id == 'VLLL':
            html = replace_json_assignment(html, 'ytPageType', 'playlist')
    elif operation == 'search':
        destination = innertube.search_endpoint(search_query)
        html = replace_json_assignment(html, 'ytCommand', destination)
        html = replace_json_assignment(html, 'ytUrl', destination['commandMetadata']['webCommandMetadata']['url'])
        html = replace_json_assignment(html, 'ytPageType', 'search')
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
