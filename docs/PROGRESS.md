# Continuation checkpoint

Repository: `vibecodeforever/reimagined-chainsaw`. Work only on `feat/mewtube`, draft PR #1. Do not merge or change repository visibility.

## Newest checkpoint: local response-integrity adapter (05:29 UTC continuation)

**Basic captured-client playback is now verified.** Run `39205467552` at commit `0c2c417` produced browser artifact `12165159132` at 05:38:17 UTC on October 19. The actual `ytd-app #movie_player video` advanced to 1.307446 s, readyState 4, no media error, wrapper state 1, matching local video ID and local MP4 HTTP response. Playability is OK, no visible/error-class overlay, and strict acceptance is true. Its saved watch screenshot was inspected: generated color bars, official controls, local title/description and masthead are visible, with no error screen. This is one fixture/build, not full YouTube compatibility. Container health passed; REA remained in progress when the browser artifact was read.

The controller follow-up also passes: run `39205725634`, artifact `12165482920` at 05:41:20 UTC, verifies official pauseVideo, seekTo and playVideo with bounded state/media checks on an eight-second fixture. Strict playback remains true, playability OK and no overlay. The adapter was also executed against the actual ignored pinned main-bundle gate: marked local OK returns success; unmarked missing-metadata responses retain the original failure.

The next implementation adds a native toggleButtonRenderer Like/Unlike action to the watch page, using the observed likeEndpoint target/videoId and /like/like, /like/removelike paths. Those endpoints authorize only the existing local HttpOnly session, validate nested targets, require ready local media and preserve Origin/custom-header checks. Inserts/removals are idempotent and committed before success. Signed-in bootstrap reflects the persisted like and the masthead displays the local username; guest buttons point only to local sign-in. This is not Google account emulation. Local verification covers 15 Python methods plus both JS suites, including cross-session isolation and personalized shell non-persistence.

Run `39205978794` (commit `a243797`), artifact `12166210031` at 05:44:38 UTC, preserves strict playback/control success. Its inspected screenshot shows the native Like button and local username, but native mutations and guest sign-in are **not yet verified**: the probe looked for legacy ytd-video-primary-info-renderer/ytd-toggle-button-renderer elements absent under this build's button rework. No native like POST occurred. The probe now targets the actual button's accessible role/label, records a sanitized button inventory, and checks persisted aria-pressed after reload. Native count toggling and accessibilityData/toggledAccessibilityData now follow the observed bundle's field handling. The next runner result must prove clicks reach local mutations.

Run `39206271933` (commit `07236ba`), artifact `12165787501` at 05:48:09 UTC, confirms native click reaches `/youtubei/v1/like/removelike`, but receives 400 and leaves state unchanged. The captured main bundle applies gzip in its request-construction path when `wug_networking_gzip_request` is enabled; that flag is true in the pinned guest configuration. Our JSON reader previously parsed encoded bytes directly. It now accepts gzip with **both encoded and decoded 1 MB limits**, bounded streaming decompression, 400 for corrupt/truncated gzip, 413 for expansion beyond the cap, and 415 for unknown encodings. Tests cover each case. Runner native diagnostics now record only endpoint/status/gzip/error text, never raw request/context bodies.

Local sign-in return is also implemented: guest and masthead links carry a return destination, the independent local auth dialog signs into the existing local session, and only exact `/official` or `/official?v=<11-character ID>` paths may be used after login. A separate JS regression rejects external/protocol-relative URLs, other routes, extra parameters, fragments, traversal and double encoding. The browser tests the real guest button as either an accessible link or button (navigation buttons may render anchors), then signs in using only its disposable generated local account and checks return to the captured watch page. These new runner results remain pending.

Run `39206643681` (commit `16cbd12`), artifact `12165792915` at 05:52:27 UTC, exposed another probe assumption: the official player was correctly cued (state 5, playability OK, no error), but the probe called the underlying video.play() while the official controller had not selected a source. Its inspected screenshot shows the normal large Play button, not a player error. The probe now mutes through the official API and clicks that visible official button, or starts through playVideo when already initialized, before measuring media progress. Mutation checks now run independently whenever the correct official watch player has OK playability, so autoplay/cue state cannot hide unrelated API diagnostics. The latest gzip/mutation/handoff proof is still pending.

Run `39206894107` (commit `f1a6a94`), artifact `12166162190` at 05:55:35 UTC, passes local media/control checks but its inspected screenshot shows the upstream sample's title, creator and Like action over local media. This **does not establish a correct local watch page**. It differs from the earlier inspected 0c2c417/a243797 screenshots which showed the local title and account button. Native action diagnostics correctly failed; no native like API call occurred in this run. Exact upstream bootstrap variant is not yet established. Replacement now recognizes bare, window.property and quoted window[property] JSON assignments; capture/shell refuse unsupported JSON bootstrap formats. Tests cover each form, script escaping and fail-closed behavior. Capture logs only assignment forms; browser diagnostics record a local bootstrap marker and account-presence booleans. Strict playback acceptance now additionally requires the actual watch heading to display the local title, so this mismatch cannot be reported as success. Local verification now passes 16 Python methods and three JS suites. A further regression preserves original adapter behavior in worker/non-window realms, and auth-return validation rejects trailing control whitespace.

Started from branch head `944d906` in a fresh checkout; no in-progress Actions runs or newer branch writes were observed. Run `39201145405`, artifact `12163986946`, correctly reports official playback **false**: local media advances to 1.307733 s, but the wrapper mutates playability to ERROR and displays 282054944. Its container and independent checks passed.

A fresh guest-only pin (33 assets, zero failures) allowed static inspection of the actual main bundle. The function associated with diagnostic `282054944_a` requires `responseContext.mainAppWebResponseContext.trackingParam`, decodes its build-specific tracking envelope, and compares response fields. Missing metadata returns failure; its caller replaces playability with ERROR, removes videoDetails and installs the exact observed error renderer. This explains why decoding worked while the application rejected our response. No upstream video media or account was accessed.

The capture pipeline now inserts a small, explicit local-backend adapter at that identified gate. It accepts only OK responses bearing `mewtubeLocalResponse: true` **and** running on the exact instance origin. It retains the original tracking-integrity gate for unmarked, non-OK or other-origin responses. This is a modified captured client, not a claim to issue Google's tracking metadata. The actual player/renderer and strict error acceptance remain untouched. Unknown build shapes are left unchanged; manifest entries record adapter counts and original/served hashes. Lazy chunks use the same adaptation. Existing pins require recapture (`--latest`). Local player details also point thumbnails at local media rather than provoking upstream fallback requests.

The regression executes a synthetic gate in Node and checks marked local success, unmarked failure, ERROR failure, other-origin failure, original behavior and idempotence. Both observed main bundles match exactly one gate. Expanded sanitized browser diagnostics record response/playability key names and plain error reason, never complete responses or tracking payloads. The fresh playback proof is recorded above.

Next: inspect native Like/Unlike click, persistence/reload, local username and guest sign-in diagnostics; fix any concrete renderer/command mismatch. Then expand subscriptions/comments and local-account handoff without Google accounts. Do not confuse a green workflow or HTTP test with official-client mutation success.

## Current status

The independent service works: local accounts, streaming uploads, FFmpeg MP4 conversion/thumbnails, range playback, search, channels, subscriptions, likes, comments, reports and host-granted operator controls. Docker Compose build/start and HTTP/FFmpeg health passed on GitHub Actions. Actual YouTube home components display a local uploaded title, thumbnail, creator and view count. The latest inspected screenshot also shows the real masthead and local MewTube account button.

**Basic official watch playback is verified by the newest checkpoint above; full compatibility remains experimental.** Earlier run 39200490739 proved local media delivery but still displayed wrapper error 282054944. Historical progress-only results below must not be confused with the newer strict acceptance and screenshot evidence.

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
