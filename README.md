# RCC2013

<img src="rcc2013/static/logo.png" width="66" height="66" alt="Project owner's RCC logo">

Local render API and console using the actual November 2013 Studio engine.
[packages.json](rcc2013/packages.json) pins complete Studio and Player
deployments, including ZIP and executable SHA-256. Studio identifies itself as
**2013.11.25.2**, x86, built 2013-11-26; Player as **0.130.0.40915**, x86.
Archive hashes identify tested bytes, not independently verified vendor
provenance. Executables are downloaded at runtime and are not committed.
The 2026 project remains on its separate `rcc2026-ci` branch.

## Thumbnail types

| API `type` | Subject | Output |
| --- | --- | --- |
| `headshot` | Classic R6 head and shoulders | Transparent RGBA PNG, no name/health display |
| `full_body` | Entire classic R6 character | Transparent RGBA PNG, no name/health display |
| `game_thumbnail` | Uploaded local place or owned blocks | Opaque PNG with scene environment |

The console uses the owner's original logo and supports type selection,
camera presets, uploads, twenty persisted recent jobs, and PNG downloads.
Its checkerboard previews transparency and is not baked into the PNG.

## Run locally

Native Windows with a visible desktop session is required:

```text
cd rcc2013
python -m pip install Pillow
python download.py
python server.py
```

Open `http://127.0.0.1:64313/`. Jobs run serially in one Studio worker and
persist in SQLite. Uploads are limited to 8 MiB; the pending queue to sixteen.

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Branded render console |
| `GET /health` | Service identity and deployment presence, not an engine self-test |
| `POST /v1/renders` | Queue a job; returns `id` |
| `GET /v1/renders` | Twenty most recent persisted jobs |
| `GET /v1/renders/{id}` | Job state and native evidence |
| `GET /v1/renders/{id}/image` | PNG after success; HTTP 409 while unavailable |
| `POST /v1/places` | Raw .rbxl/.rbxlx upload; returns SHA-256 `place_id` |

Example request bodies:

```json
{"type":"headshot","size":{"width":512,"height":512}}
```

```json
{"type":"full_body","size":{"width":512,"height":512}}
```

```json
{"type":"game_thumbnail","place_id":"<uploaded place SHA-256>","size":{"width":640,"height":360}}
```

Omit `place_id` for the owned block scene. Player modes use the R6 fixture and
reject an uploaded place. The older `{"scene":"avatar"}` request maps to
`full_body`; an empty request remains the owned game scene. Optional `camera`
accepts finite numeric three-component `position`/`target` and `fov`
between 10 and 100. Arbitrary Lua source is not accepted.

Player thumbnails default to 512 × 512. Dimensions must be integers between
128 and 2048. The worker restores/resizes only its owned Studio window until
the native viewport matches. Requests fail if the dimensions cannot fit the
desktop or Studio minimum layout. PNGs are not resized or cropped afterward.
Custom camera framing may crop a subject; the default full-body test requires
margins on all sides.

## Rendering and positioning

The owned [R6 fixture](rcc2013/avatar.lua) builds six visible parts, an invisible
root, joints, a Humanoid, and the engine's Head mesh. Its smile uses the pinned
deployment's bundled face texture locally. All parts are anchored. Before
capture the Humanoid is detached to prevent automatic name/health billboards;
the geometry and face remain.

Player alpha comes from two matching native frames against contrasting solid
backdrops, with calibrated backdrop RGB and fixed lighting. The worker rejects
missing scene markers, insufficient contrast, obstructed calibration patches,
dimension mismatch, and excessive registration error. Alpha recovery preserves
black/white/blue foreground pixels instead of deleting a chosen color. Both
original native passes remain in evidence. Game thumbnails retain the scene
environment and use one native capture.

The supplied wiki was searched at revision
`a7a6802ed56263dfb8c97e199b2c65bce1db33a6`. Its RCC examples invoke
ThumbnailGenerator with sky hiding enabled; its web API reference separates
avatar, headshot, and game types. **No exact headshot/full-body camera-positioning
Lua script was found in that revision.** A subsequent revival-source search
found headshot geometry in BubbaBlox v2 and Economy Simulator. The headshot now
uses BubbaBlox's no-hat R6 case: head-level camera, 3-stud distance, 11.25-degree
side angle, 0.1-stud target offset, and 30-degree FOV. The inspected full-body
scripts delegate framing to RCC; our full-body camera remains custom. Neither
preset is claimed to establish original 2013 Roblox defaults.
See [source-by-source findings and positioning](docs/thumbnail-research.md).

## Validation

Eight local test methods cover request validation, type routing, history, HTTP
delivery, and alpha recovery from known foreground colors and partial edges.
Their mock engine is separate from actual native evidence.
`windows_e2e.py` checks actual scene and GUI-removal markers, exact sizes,
full-body margins, distinct headshot/full-body images, and PNG alpha.
`console_capture.py` checks Chrome against a completed native player job.
Latest [native run 39316052306](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39316052306),
source commit `24aaa4baab49464bdd260b425a2a6fc2331b13a1`, passed all six local
tests, four actual HTTP render jobs (six native Studio launches), and Chrome
console validation. Both player PNGs were visually inspected: the smiling
2013 player is isolated with no sky, name, health bar, or other UI. Alpha values
include zero in the background and 255 in the player. The full-body fixture
fits the frame; the headshot has its own closer camera framing.

| Verified output | Size | PNG SHA-256 |
| --- | --- | --- |
| Full body | 512 × 512 RGBA | `0d994bbbfe7c1d5308c66ed7b3273919bb9740d182a4380902929c44fcb50b39` |
| Headshot | 512 × 512 RGBA | `0400d269a17191b5b822414ee64cafacc2616307cdc8637c5a673642fad198a3` |

The artifact contains `full-body-render.png`, `headshot-render.png`, opaque
scene images, per-pass results, `api-validation.json`, and the branded console
preview and validation report. The reported matte registration residual p99
was 3 and 4 RGB levels, respectively. Alpha above 0.96 is snapped to one for
the opaque fixture to tolerate small native shading differences; this is a
wrapper reconstruction rather than direct RCC render-target alpha.

Earlier checkpoints:

- [39268119152](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39268119152): first scene and uploaded-place PNGs through HTTP.
- [39308295354](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39308295354): exact 512 × 512 / 640 × 360 native viewport sizes and custom camera passed.
- [39308899770](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39308899770): first smiling R6 and branded console; its sky and name/health overlay are superseded by the new player-thumbnail contract.

Artifacts retain result JSON, returned PNGs, native matte passes, diagnostic
screenshots, and redacted engine logs for seven days. A PNG or a mocked HTTP
test alone does not establish engine rendering.

## Limits

This is a JSON wrapper around Studio's visible viewport, not a legacy RCC SOAP
implementation or headless renderer. A foreground desktop is required; the
executable is not patched. Static fixture rendering does not establish account
appearance, clothing, accessory, animation, arbitrary body-scale, or game-joining
support. Player was downloaded and identified but has not been launched for joining.

## References

- [Daniel-176's reverse-engineering wiki](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki)
- [Roblonium archive](https://archive.roblonium.com/Client/Windows/TODO/ROBLOX%20clients/)
- [REA](https://github.com/morluto/rea), used as `rea-agents@6.7.0` for read-only PE resource inspection; it identified x86 Studio and matched its executable digest.
