# Continuation checkpoint

Repository: `vibecodeforever/reimagined-chainsaw`. Work only on `feat/mewtube`, draft PR #1. Do not merge or change repository visibility.

## Newest checkpoint: local response-integrity adapter (05:29 UTC continuation)

Started from branch head `944d906` in a fresh checkout; no in-progress Actions runs or newer branch writes were observed. Run `39201145405`, artifact `12163986946`, correctly reports official playback **false**: local media advances to 1.307733 s, but the wrapper mutates playability to ERROR and displays 282054944. Its container and independent checks passed.

A fresh guest-only pin (33 assets, zero failures) allowed static inspection of the actual main bundle. The function associated with diagnostic `282054944_a` requires `responseContext.mainAppWebResponseContext.trackingParam`, decodes its build-specific tracking envelope, and compares response fields. Missing metadata returns failure; its caller replaces playability with ERROR, removes videoDetails and installs the exact observed error renderer. This explains why decoding worked while the application rejected our response. No upstream video media or account was accessed.

The capture pipeline now inserts a small, explicit local-backend adapter at that identified gate. It accepts only OK responses bearing `mewtubeLocalResponse: true` **and** running on the exact instance origin. It retains the original tracking-integrity gate for unmarked, non-OK or other-origin responses. This is a modified captured client, not a claim to issue Google's tracking metadata. The actual player/renderer and strict error acceptance remain untouched. Unknown build shapes are left unchanged; manifest entries record adapter counts and original/served hashes. Lazy chunks use the same adaptation. Existing pins require recapture (`--latest`). Local player details also point thumbnails at local media rather than provoking upstream fallback requests.

The regression executes a synthetic gate in Node and checks marked local success, unmarked failure, ERROR failure, other-origin failure, original behavior and idempotence. Both observed main bundles match exactly one gate. Expanded sanitized browser diagnostics record response/playability key names and plain error reason, never complete responses or tracking payloads. Fresh runner playback evidence remains required before claiming this fixes playback.

Next: inspect the new browser artifact for playability OK, no error overlay, local media progress and matching official watch identity; inspect its screenshot. Only then move to native-client account/mutation compatibility. Do not confuse a green workflow or synthetic gate test with official playback success.

## Current status

The independent service works: local accounts, streaming uploads, FFmpeg MP4 conversion/thumbnails, range playback, search, channels, subscriptions, likes, comments, reports and host-granted operator controls. Docker Compose build/start and HTTP/FFmpeg health passed on GitHub Actions. Actual YouTube home components display a local uploaded title, thumbnail, creator and view count. The latest inspected screenshot also shows the real masthead and local MewTube account button.

**Stable official YouTube watch playback is not verified.** Run 39200490739 (commit 6a045d2) now proves that the actual `ytd-app #movie_player video` receives the local MP4 and advances: readyState 4, no HTMLMediaElement error, time 0.168607 s, duration 3.018005 s, local media HTTP response. However, its screenshot shows a YouTube wrapper error overlay (282054944). The previous single-sample playback=true result is insufficient and must not be reported as stable success.

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

## Fresh runner result and stricter acceptance

Browser artifact `12162898931` from run `39200490739` was uploaded at 04:40:00 UTC on October 19. The module-loader `Uc` exception is gone (`errors: []`). Actual YouTube home and watch components, masthead, local account button, title and description render. The local MP4 reaches the actual official media element and its clock advances. The independent browser checks and Docker health also pass.

The watch screenshot nevertheless shows “Something went wrong. Please try again later.” with error 282054944. Therefore the probe is tightened again: require a stability interval, actual wrapper state playing/ended, matching video ID, and no visible/error-class overlay. It also records player state, playability status and overlay text. A short fake-video burst followed by a stall now has regression coverage. The next browser result should identify whether the wrapper error persists and its state; investigate its player/bootstrap contract before implementing local-account mutations.

Evidence: https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39200490739/artifacts/12162898931

## Acceptance correction from run 39200829376

The sustained-media probe reached time 1.404131 s with readyState 4, wrapper state 1 and the correct local ID, but `getPlayerResponse().playabilityStatus.status` was **ERROR**. The screenshot still displayed error 282054944. This confirms that video-element progress and wrapper state alone cannot establish usable playback. The probe now also requires an OK player response and checks visible application-level playability-error renderers outside #movie_player. A pure acceptance regression rejects ERROR responses even when the underlying video advances. The next artifact records the response reason and overlay text for diagnosis.

The remaining blocker is the wrapper/bootstrap playability contract, not delivery or decoding of the local MP4. Investigate which player response/configuration replaces the injected OK bootstrap; do not begin claiming stable official playback or full feature parity.
