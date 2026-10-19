#!/usr/bin/env python3
"""Capture a guest build per instance. Downloads are never checked into source."""
import argparse
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mewtube.snapshot import asset_name
from mewtube.store import DATA

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
MAX_FILE = 20 * 1024 * 1024
WATCH_ID = 'jNQXAC9IVRw'  # Public guest HTML only; no video media is fetched.


def rewrite_origins(text, origin):
    # Workers have their own fetch/XHR globals, so the window bridge alone cannot
    # redirect hardcoded API origins inside worker bundles.
    for source in ('https://www.youtube.com', 'https://youtubei.googleapis.com', 'https://m.youtube.com'):
        text = text.replace(source, origin)
        text = text.replace(source.replace('/', '\\/'), origin.replace('/', '\\/'))
        text = text.replace(source.removeprefix('https:'), '//' + urllib.parse.urlsplit(origin).netloc)
    for source, prefix in (('fonts.gstatic.com', '/client-static/fonts'), ('www.gstatic.com', '/client-static/branding')):
        text = text.replace('https://' + source, origin + prefix)
        text = text.replace('https:\\/\\/' + source, (origin + prefix).replace('/', '\\/'))
        text = text.replace('//' + source, '//' + urllib.parse.urlsplit(origin).netloc + prefix)
    return text


def allowed(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != 'https' or asset_name(url) is None:
        return False
    if u.netloc == 'www.youtube.com':
        return u.path.startswith(('/s/desktop/', '/s/player/', '/s/_/ytmainappweb/'))
    if u.netloc == 'fonts.gstatic.com':
        return u.path.startswith('/s/i/') and asset_name(url).endswith(('.svg', '.png'))
    if u.netloc == 'www.gstatic.com':
        return u.path.startswith('/youtube/img/icons/') and asset_name(url).endswith(('.svg', '.png'))
    return False


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        guest_page = parsed.scheme == 'https' and parsed.netloc == 'www.youtube.com' and parsed.path in ('/', '/watch')
        if not guest_page and not allowed(newurl):
            raise ValueError('Unexpected redirect; capture stopped: ' + urllib.parse.urlsplit(newurl).netloc)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})
    with urllib.request.build_opener(Redirect()).open(req, timeout=30) as response:
        raw = response.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            raise ValueError('Asset exceeds capture size limit')
        return raw


def references(content):
    # Absolute and root-relative static paths, including JS module loader references.
    candidates = re.findall(r'(?:(?:https?:)?//(?:www\.youtube\.com|fonts\.gstatic\.com|www\.gstatic\.com))?/(?:s/(?:desktop|player|_/ytmainappweb|i)/|youtube/img/icons/)[^\s"\'<>`\\)]+', content)
    return {urllib.parse.urljoin('https://www.youtube.com', html_lib.unescape(u)) for u in candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latest', action='store_true', help='Replace an existing pinned guest build')
    parser.add_argument('--max-assets', type=int, default=120)
    args = parser.parse_args()
    origin = os.environ.get('PUBLIC_ORIGIN', 'http://localhost:3000').rstrip('/')
    if not re.fullmatch(r'https?://[A-Za-z0-9.\-\[\]:]+', origin):
        raise SystemExit('PUBLIC_ORIGIN must be an HTTP(S) origin without a path, credentials or query.')
    client = DATA / 'client'
    if (client / 'index.html').exists() and not args.latest:
        print('A client is already pinned. Use --latest to replace it.')
        return
    html = fetch('https://www.youtube.com/').decode('utf-8')
    if 'ytInitialData' not in html or '<ytd-app' not in html:
        raise SystemExit('YouTube returned a consent/challenge/non-desktop page; no build was pinned.')
    watch_html = None
    page_failures = []
    try:
        watch_html = fetch('https://www.youtube.com/watch?v=' + WATCH_ID).decode('utf-8')
        if 'ytInitialPlayerResponse' not in watch_html or '<ytd-app' not in watch_html:
            raise ValueError('Guest watch page did not contain the player bootstrap')
    except Exception as e:
        page_failures.append({'path': '/watch', 'error': type(e).__name__})
        watch_html = None
        print('Guest watch template unavailable:', type(e).__name__, flush=True)
    pending = sorted(u for u in references(html + (watch_html or '')) if allowed(u))
    # Observed dynamic icon requests from the captured client's browser trace.
    pending += ['https://fonts.gstatic.com/s/i/youtube_outline_experimental/search/v15/24px.svg',
                'https://fonts.gstatic.com/s/i/youtube_outline_experimental/menu/v1/24px.svg']
    raw_assets = {}
    failures = page_failures
    while pending and len(raw_assets) < args.max_assets:
        url = pending.pop(0)
        if url in raw_assets:
            continue
        try:
            raw = fetch(url)
            raw_assets[url] = raw
            print('Captured', urllib.parse.urlsplit(url).path, len(raw), flush=True)
            if asset_name(url).endswith(('.js', '.css')):
                pending.extend(sorted(u for u in references(raw.decode('utf-8')) if allowed(u) and u not in raw_assets and u not in pending))
        except Exception as e:
            failures.append({'host': urllib.parse.urlsplit(url).netloc, 'path': urllib.parse.urlsplit(url).path,
                             'error': type(e).__name__, 'status': getattr(e, 'code', None)})
    if not any(asset_name(u).endswith('.js') for u in raw_assets):
        raise SystemExit('No entry scripts captured; old pin left intact.')
    mapping = {u: '/client-assets/' + asset_name(u) for u in raw_assets}

    def rewrite(text):
        # Longer URLs first so path prefixes cannot consume another entry.
        for url, local in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(url, local)
            if url.startswith('https://www.youtube.com'):
                text = text.replace(url.removeprefix('https://www.youtube.com'), local)
        return rewrite_origins(text, origin)

    directory = client / 'assets'
    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for url, raw in raw_assets.items():
        name = asset_name(url)
        served = rewrite(raw.decode('utf-8')).encode() if name.endswith(('.js', '.css')) else raw
        (directory / name).write_bytes(served)
        entries.append({'url': url, 'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                        'served_sha256': hashlib.sha256(served).hexdigest()})
    # Retained only on this machine. It may contain anonymous visitor identifiers.
    staged = client / 'index.html.tmp'
    staged.write_text(rewrite(html))
    staged.replace(client / 'index.html')
    if watch_html:
        staged_watch = client / 'watch.html.tmp'
        staged_watch.write_text(rewrite(watch_html))
        staged_watch.replace(client / 'watch.html')
    else:
        (client / 'watch.html').unlink(missing_ok=True)
    (client / 'manifest.json').write_text(json.dumps({'capturedAt': int(time.time()), 'publicOrigin': origin, 'assets': entries,
        'watchTemplate': bool(watch_html), 'watchSourceId': WATCH_ID,
        'failures': failures, 'remaining': len(pending), 'status': 'experimental-unverified'}, indent=2))
    print(f'Pinned {len(entries)} assets; {len(failures)} failures, {len(pending)} remaining. Experimental client: /official')


if __name__ == '__main__':
    main()
