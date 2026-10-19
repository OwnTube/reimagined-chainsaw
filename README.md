# MewTube

A self-hosted video service and an **experimental backend for a locally captured YouTube web client**. Inspired by Xitter and Meowcord's architecture: capture a client per instance, serve assets locally, and answer its APIs from your own database.

**Early alpha. A GitHub runner rendered and played a local uploaded video through the captured client’s actual `ytd-app` and player components, with OK playability and no error overlay. The independent interface and HTTP service also pass integration tests. Full YouTube client compatibility has not been established.** `/official` serves a guest snapshot with local bootstrap data and a small InnerTube API subset. This is an independent project, not affiliated with YouTube or Google.

## Start it

Requires Python 3.12+ and FFmpeg/FFprobe. No Python packages, API keys, or Google account are needed.

```sh
python -m mewtube.server
# open http://localhost:3000
```

Create an account in the web interface, open **Your studio**, and upload a video. To make that account an instance operator:

```sh
python scripts/manage_operator.py grant YOUR_USERNAME
```

The first registration does **not** become an operator. Only someone with host-console access can grant that role.

### Docker

```sh
cp .env.example .env
docker compose up -d --build
# Register in the web interface, then:
docker compose exec mewtube python scripts/manage_operator.py grant YOUR_USERNAME
```

The default Docker port is bound to the host's loopback interface. Put an HTTPS reverse proxy in front of it for remote access; set `PUBLIC_ORIGIN` to the exact browser-facing origin. Configure its request-size limit and upload timeout. The container runs as an unprivileged user. The Docker Compose stack built, started and passed its HTTP/FFmpeg health check on a disposable GitHub runner.

## Capture the official guest client

```sh
python scripts/fetch_client.py
# or inside Docker:
docker compose exec mewtube python scripts/fetch_client.py
# open http://localhost:3000/official
```

This downloads guest home/watch HTML and allowlisted static assets from YouTube; it does not download any upstream video media. It does not use your Google login, proxy YouTube videos, or import YouTube accounts. Captures stay in ignored `data/client/` and must not be committed. Capture uses `PUBLIC_ORIGIN` to rewrite hardcoded API origins for workers as well as the window transport; recapture after changing that origin. `--latest` replaces the pin. Recapture after upgrading from hashed build URLs: the native module loader needs its original `/s/_/.../_/js/k=...` path, which the server now resolves locally through the manifest. A manifest records original and served SHA-256 hashes and failed downloads. Use the banner’s independent-UI link (or `/?native=1`) to leave captured-client mode. The site CSP blocks external browser connections. Lazy chunks may be fetched by the server only from fixed public YouTube build paths and the two observed Google icon path families, with 20 MB per-file, 500-file and 384 MB cache limits; arbitrary hosts, API URLs and traversal paths are rejected.

The observed guest build used desktop `5d669aa8`, player `0229cd64`, and newer `/s/_/ytmainappweb/` main bundles. The latest local guest pin obtained **33 assets with zero reported download failures**. That count does not prove that every dynamically loaded module was discovered, or that the UI works.

The captured client is explicitly adapted, not unmodified: its response-integrity gate expects Google's obfuscated tracking metadata and otherwise displays error 282054944 even over a playing local video. Capture inserts an exact-instance-origin exception for OK responses marked by this local backend; it preserves the original gate for all other responses. The manifest records whether the known gate was identified and adapted, plus the original/served hashes. Unknown builds remain experimental and unchanged. Recapture older pins with `--latest`. This does not obtain Google tracking credentials, unlock upstream media, remove actual player errors, or replace the official video player.

## Implemented

- Local registration, scrypt password hashes, opaque cookie sessions, sign-in/out.
- Video upload, one durable processing queue, FFmpeg conversion to a progressive H.264/AAC MP4, and thumbnails. Maximum duration: one hour.
- Home, title/description search, channel feeds, subscriptions, and creator studio.
- Native HTML5 playback, byte ranges, suffix ranges, and HEAD requests.
- Likes, comments, creator metadata changes, deletion, and abuse reports.
- Host-granted operators can inspect reports, remove videos, and inspect unknown client calls.
- InnerTube-shaped `browse`, `search`, `player`, and `next` responses backed by local videos.
- Instance-local guest client capture, current main-bundle URL handling, bootstrap replacement, and fetch/XHR transport adapter.
- HTTP integration tests and a GitHub Actions browser/REA diagnostic workflow.

## Known limits

- **Basic official home/watch rendering and local video playback passed a strict runner test and screenshot inspection (run 39205467552).** This remains experimental, not parity with Xitter, Meowcord, or YouTube. Official-client sign-in, Studio, comments, likes, playlists, channel management, and subscriptions are not adapted yet. Use the independent interface for these supported local features.
- No federation, live streaming, Shorts, adaptive bitrate/HLS/DASH, captions, notifications, email verification, password recovery, or private videos.
- Uploads become public when processing finishes. View counts currently count authenticated play events and are not unique-view analytics.
- A single process and one transcoder serve a small instance; not a production-scale video platform. No total storage quota, mature abuse controls, or resumable upload support yet.
- Earlier runs exposed module-loader URL failures, navigation into the independent UI, hung play promises and an error overlay over advancing media. These were corrected and the latest basic playback proof requires sustained media progress, matching official wrapper state/identity, local HTTP media delivery, OK playability and no error renderer. The probe saves bounded diagnostics; follow-up coverage exercises official pause/seek/resume controls. See the progress log for exact evidence and limits.
- REA 6.7.0 was invoked locally, but aborted when process ownership inspection hit this container's broken `ps` implementation (`fatal library error, lookup self`). A subsequent Ubuntu run completed with partial coverage: 12 JavaScript files parsed and 1,371 findings, while large player/main-bundle analysis hit heap limits. Neither result establishes complete analysis.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `PUBLIC_ORIGIN` | `http://localhost:3000` | Exact public origin; used for CSRF checks and player URLs |
| `PORT` | `3000` | Native HTTP listener port |
| `BIND` | `0.0.0.0` | Native bind address |
| `DATA_DIR` | `data` | SQLite, original pending uploads, converted media, local client archive |
| `MAX_UPLOAD_MB` | `500` | Maximum incoming video size |
| `SIGNUPS` | `1` | Set `0` to close registration |
| `HOST_PORT` | `3000` | Compose host port |

Back up the complete data directory with the service stopped; retain SQLite alongside its media. Never commit it or `.env`. To change ports, update `PUBLIC_ORIGIN` too. FFmpeg and FFprobe must be on `PATH`.

## Verify

```sh
python -m unittest discover -s tests -v
node --check web/app.js
node --check web/bridge.js
node tests/bridge.test.mjs
node tests/playback_probe.test.mjs
```

The tests start a disposable service, generate an audiovisual test pattern, upload and transcode it, read its MP4/thumbnails/ranges, verify auth and ownership, exercise interactions/moderation and InnerTube responses, reject nonvideo/playlist uploads, and test safe bootstrap replacement.

On a normal host with a supported browser environment:

```sh
npm install --ignore-scripts
npx playwright install chromium
mkdir -p evidence
ffmpeg -v error -y -f lavfi -i testsrc2=size=640x360:rate=24 -f lavfi -i sine=frequency=440 -t 8 -c:v libx264 -pix_fmt yuv420p -c:a aac evidence/sample.mp4
# Run the server separately, then:
npm run test:browser
```

`evidence/browser.json` distinguishes independent-client playback from captured-client results. A successful independent client must not be reported as a successful official client.

See [research](docs/research.md), [architecture](docs/architecture.md), and [continuation notes](docs/PROGRESS.md).

## License

Original implementation: MIT. No Xitter, Meowcord, or YouTube source is included. Xitter and Meowcord are AGPL-3.0-only; any later reuse of their code must preserve the applicable license obligations. Downloaded YouTube assets are third-party software, separately governed, and are not covered by this repository's license.
