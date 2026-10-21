# Historical Studio reference implementation

The following records the earlier Studio-based renderer. The default project
entry point is now the custom service described in the root README. Studio
reference workflows are manual; they are not the custom RCC runtime.

# RCC2013

<img src="rcc2013/static/logo.png" width="66" height="66" alt="Project owner's RCC logo">

Local render API and console using the actual November 2013 Studio engine.
[packages.json](rcc2013/packages.json) pins complete Studio and Player
deployments, including ZIP and executable SHA-256. Studio identifies itself as
**2013.11.25.2**, x86, built 2013-11-26; Player as **0.130.0.40915**, x86.
Archive hashes identify tested bytes, not independently verified vendor
provenance. Executables are downloaded at runtime and are not committed.
The 2026 project remains on its separate `rcc2026-ci` branch.

The separate [local joining probe](docs/local-joining.md) now verifies an
owned game hosted by Studio and joined by the actual standalone 2013 Player,
including admission, replicated scene data, character movement, and a
RemoteEvent reply. Archived menu, chat, player-list, and backpack containers
now load in the standalone Player; full interaction and texture fidelity
remain under development.
The JSON thumbnail API remains a separate renderer.

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

The [R6 fixture](rcc2013/avatar.lua) loads the pinned deployment's bundled
`character3.rbxm` model. Its torso, arms, and legs explicitly use the five
dedicated `rbxasset://fonts/*.mesh` body assets, preserving their bevelled
character surfaces after the Humanoid is removed to suppress billboards.
The bundled head mesh and face remain; all parts are anchored and recolored
for the owned test appearance. These assets are referenced locally, never
redistributed in this repository. Native evidence records their SHA-256 and
five body-mesh markers. The earlier manual block fixture is superseded;
the replacement was validated in native Windows Studio and visually inspected.

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
scripts delegate framing to RCC; the owner’s supplied profile thumbnail now guides the full-body camera
reconstruction. Neither preset establishes original 2013 Roblox defaults.
See [source-by-source findings and positioning](docs/thumbnail-research.md).

The owner's uploaded RCC scripts are preserved in [templates](rcc2013/templates)
and have a local job-parameter adapter. A native probe confirmed that this
Studio build has no ThumbnailGenerator service, so those scripts' Click
calls cannot run unchanged here. The full-body Studio camera is reconstructed
from the supplied 150x200 profile image: eye [-2.44,5.06,-4.92], target
[0,2.4,0], FOV 58°. The headshot matches the supplied script's no-accessory
camera formula. Direct RCC template execution remains pending a compatible
runtime; it is not silently replaced by another engine version.


## Validation

Eight local test methods cover request validation, type routing, history, HTTP
delivery, and alpha recovery from known foreground colors and partial edges.
Their mock engine is separate from actual native evidence.
`windows_e2e.py` checks actual scene and GUI-removal markers, exact sizes,
five dedicated body-mesh markers, asset hashes, full-body margins, distinct
headshot/full-body images, and PNG alpha.
`console_capture.py` checks Chrome against a completed native player job.
Latest [reference-framing run 39433202145](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39433202145),
source `8f05824625642c886b9ffaac1d193f0f9016c320`, passed the eight existing
local checks, five native HTTP render jobs, and console validation. The new
450x600 portrait was visually inspected; alpha bounds (43,33,441,512) are
within five pixels of the supplied profile reference scaled to that size.
The transparent portrait PNG SHA-256 is
`8e2ae7fe6a3d907ac510fe3282fe0c06e8f628f2cb97129c0f64da503aa19b04`.
The 512x512 full-body output is
`d599e6449221d0f63b219479203a32248dbcda8ea00a829be255f80191d272f8`.
The headshot remains byte-identical to the previous dedicated-body checkpoint.
Both full-body sizes retain all six body parts, dedicated meshes, clear
background, opaque player pixels, and no overhead GUI.

Earlier [dedicated-body run 39319529320](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39319529320),
source commit `7c9317516f872873181d4e4b06449b967854827e`, passed eight local
tests, all four native HTTP render jobs, and Chrome console validation.
Both player outputs were visually inspected: the limbs and torso have their
dedicated bevelled geometry, including separation between the legs. Each
native player pass confirmed all five mesh assignments and the six bundled
asset identities. Both 512 × 512 RGBA outputs contain clear background and
opaque player pixels, with no overhead GUI. The headshot camera is unchanged.

| Current dedicated-body output | PNG SHA-256 |
| --- | --- |
| Full body | `7220f21ea9f70ef9421408ec02b3520b5a749a807c19219eb2a3b235eeac6b16` |
| Headshot | `57b8c4364616b2a8462413f5af42637d48ec41b1abd1054ee5f612353e4c5381` |

Earlier [source-framing run 39317404183](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39317404183),
source commit `71c5f1b48e50d707c3e88e6f6ea7217e7f911aa4`, passed eight local tests,
four native HTTP jobs, and Chrome console validation. The headshot uses the
BubbaBlox v2 no-hat geometry and was visually inspected. Both native passes
reported eye approximately `[0.585271,4.5,-2.942356]`, target `[0,4.5,0.1]`,
and FOV approximately 30 degrees. Its 512 × 512 RGBA PNG SHA-256 is
`c8bdf5ece7685b3ff4b1bfa0d74052f56d0ddbbac70cc253ac1b3c453c0d4fb8`.
The result records the camera profile and actual engine camera markers. It
contains transparent background and opaque player pixels, with no GUI.
Its manually assembled body geometry is superseded by the dedicated-body run.

Earlier transparency checkpoint [native run 39316052306](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39316052306),
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

## Local game joining

[Run 39348329677](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39348329677),
source `b09758b8aab8bb4145a5805459fef70072a32007`, verified an owned game between
two separate unmodified 2013 Studio processes. The host owned its UDP port;
the client was admitted and received the server-only token and scene. The
host's beacon movement reached the client, the client's RemoteEvent reply
reached the host, and client-initiated character walking was observed on both
peers. Both Windows control tests passed and both native viewports were
captured. See [commands, engine evidence, and limits](docs/local-joining.md).

[Standalone Player run 39424173794](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39424173794),
source `df9766ab74d017c56e9b626f47f77aa972612b5c`, subsequently verified the
same admission, independent token, moving beacon, RemoteEvent reply, and
character movement using **RobloxPlayerBeta.exe**, with Studio hosting.
The Player's disposable copy uses a reserved local domain and a fresh script
public key; 21 equal-length data edits preserve its executable code. Both
peers enable the native `DebugLocalRccServerConnection` setting, and Player
connects to numeric loopback. Studio's executable remains unchanged.

[Archived interface run 39427990205](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39427990205),
source `a864aa917b962ebdf0cda30f60892a47f242a49c`, additionally verified all
four menu/chat/player-list/backpack containers while the network and character
checks passed. The default compatibility loader executes pinned archived Lua
inside the signed local bootstrap; native child CoreScript loading remains
unresolved. Twenty-two image assets are restored, with fifteen unavailable
IDs recorded. A container check does not prove every UI action or texture.
[Keyboard run 39430884973](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39430884973),
source `91f2a648f9496e04ae9c4309f34862509c152732`, subsequently passed all of
those checks plus OS-keyboard movement observed on both peers. The native
legacy key callback receives D, and the engine's HumanoidController moves the
character. The capture shows the archived inventory's first tool slot;
equipping and chat delivery remain untested. See [current native results and limits](docs/local-joining.md).
The bounded test removes its peers, exact local hosts-file entry, runtime
copies, and ephemeral signing key.

## Limits

This is a JSON wrapper around Studio's visible viewport, not a legacy RCC SOAP
implementation or headless renderer. A foreground desktop is required; the
renderer uses unmodified Studio. The standalone joining probe configures a
disposable Player copy as described above. Static fixture rendering does not establish account
appearance, clothing, accessory, animation, or arbitrary body-scale support.
Game joining is tested independently in `hosting2013`; two-Studio evidence
does not establish standalone RobloxPlayerBeta compatibility. The independent
Player evidence above establishes local joining, not public hosting.

[The Funnel Method review](docs/funnel-method-review.md) tracks a separate
hosting research path: its patch set targets a 2016 RCC with December 2013L
clients and requires a separate stock source tree. It has no standalone build
or published release in the inspected repository. Compatibility with our
November Player, or game joining through that path, has not been tested.

## References

- [Daniel-176's reverse-engineering wiki](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki)
- [Roblonium archive](https://archive.roblonium.com/Client/Windows/TODO/ROBLOX%20clients/)
- [REA](https://github.com/morluto/rea), used as `rea-agents@6.7.0` for read-only PE resource inspection; it identified x86 Studio and matched its executable digest.
