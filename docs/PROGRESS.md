# Continuation checkpoint

Repository: `vibecodeforever/reimagined-chainsaw`. Work only on `feat/mewtube`, draft PR #1. Do not merge or change repository visibility.

## Current status

The independent service works: local accounts, streaming uploads, FFmpeg MP4 conversion/thumbnails, range playback, search, channels, subscriptions, likes, comments, reports and host-granted operator controls. Docker Compose build/start and HTTP/FFmpeg health passed on GitHub Actions. Actual YouTube home components display a local uploaded title, thumbnail, creator and view count. The latest inspected screenshot also shows the real masthead and local MewTube account button.

**Official YouTube watch playback is not verified.** Never substitute independent-interface playback, an attached video element, or API tests for that claim.

## Latest investigation and fixes (October 19, 2026)

Read the branch afresh at `d404d1a1095c13e9285a252cf63ca92d4895705b`. Its latest workflow run `39182748691` was cancelled after the browser step ran from 00:53:51 to 01:13:08 UTC. Artifact `12157262164` contained screenshots and server.log but no browser.json: the probe awaited HTMLMediaElement.play() indefinitely. The official-home screenshot confirms the masthead fix worked; it does not prove watch playback.

Two concrete problems were corrected:

1. **Module loader URL contract.** The downloaded current main bundle's loader validates that its script URL contains `/_/js/` (or `/_/ss/`) and `/k=`. It throws `Uc` for the hashed `/client-assets/<hash>.js` path previously emitted by capture. New captures retain original build paths on the local origin. Hashes remain internal storage filenames, resolved by the fixed-host manifest cache. Existing instances must recapture with `python scripts/fetch_client.py --latest`.
2. **Unbounded browser probe.** A new self-contained playback probe times out both a pending play() promise and a video that never advances. It records media ready/network states, source path, error code and timing without URL queries. The browser script checkpoints browser.json through each phase, has per-call bounds and a process watchdog, and uploads browser diagnostics before REA. Official playback additionally requires the actual `ytd-app #movie_player video`, correct local watch ID, progressing time and a local media response.

Captured watch links now force a full local navigation into the pinned watch template. This deliberately avoids the unimplemented SPA POST /watch envelope. Modified clicks retain normal browser behavior. This does not introduce a replacement player or claim SPA parity.

Local verification after the fixes: **13 Python test methods pass**, including real FFmpeg conversion, byte ranges, sessions, ownership, interactions/moderation, interrupted-upload recovery and captured/native mode transitions. `node tests/bridge.test.mjs` and `node tests/playback_probe.test.mjs` pass. The new capture regression checks actual output URLs, and the media tests include never-settling, stalled, rejected and progressing play promises. Browser syntax check passes. Fresh CI evidence is the next source of truth.

## Earlier evidence and caveats

- Reference study: Xittered/xitter and meowcorded/meowcord pin official clients per instance, preserve native renderer/API contracts and implement their own local backends. See docs/research.md.
- Initial home-only guest capture obtained 23 assets with zero failures. A later home+watch pin obtained 26 assets with seven icon failures; do not call that pin zero-failure. Icon sources were subsequently corrected to fixed fonts.gstatic.com /s/i/ and www.gstatic.com /youtube/img/icons/ families.
- REA 6.7.0 failed locally because this container's ps cannot inspect itself. Run 39181319724 completed a partial runner analysis: 12 parsed JS files, 1,371 findings, heap limitations on large main/player bundles. It is not a complete static analysis.
- Run 39181670534 exposed an older false-positive watch test: the click had loaded the independent player. Screenshots, not the old generic-video flag, establish that fact.
- A streaming RequestInit bug caused local POSTs to fail with ERR_ALPN_NEGOTIATION_FAILED. The bridge now buffers API bodies and strips upstream auth/visitor headers. Binary log_event telemetry is acknowledged and discarded.
- Lazy static cache permits fixed public build/icon hosts and path families only, with 20 MB per-file, 500-file and 384 MB cache limits; no forwarded credentials or arbitrary proxy URLs.
- Full client authentication, Studio and mutation compatibility remain unimplemented. Use local independent-interface features meanwhile.

## Next priority

1. Inspect the newest CI browser artifact and `browser.json`, especially the strict official-player result and saved media state. Fix the next concrete loader, bootstrap or player-response failure. Do not wait for REA before reading the browser artifact.
2. If a pinned watch page still cannot boot, use its loader stack/failed static paths and local bootstrap state. Preserve native build URL metadata, keep all traffic local, and never import upstream user accounts or video media.
3. After actual official-player proof, implement local account/mutation adapters using observed contracts. Add search/guide/channel coverage as evidence warrants it.
4. Improve global upload disk quotas and transcoder isolation without breaking the self-contained service.

## Boundaries

No Google account or personal credentials are needed or authorized. Never commit downloaded clients, cookies, raw HARs, secrets, user uploads, SQLite data, node_modules or evidence artifacts. Do not globally alter agent configuration. Use connected GitHub tools and expected-head checks for writes; avoid conflicting changes if another worker has advanced this branch. Update this checkpoint with concrete commits/checks and honest limits.
