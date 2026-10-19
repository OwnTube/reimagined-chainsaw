# RCC2013

<img src="rcc2013/static/logo.png" width="66" height="66" alt="RCC2013 logo supplied by the project owner">

Experimental renderer work using archived November 2013 Roblox Player and Studio.

The complete deployments are downloaded directly from the user's supplied Roblonium archive, with pinned ZIP and executable SHA-256 digests in [packages.json](rcc2013/packages.json). The Studio PE reports version **2013.11.25.2**, a 2013-11-26 build timestamp, and x86 architecture; Player reports **0.130.0.40915**, also x86. These are archive-supplied files; their hashes identify the tested bytes, not independently verified vendor provenance.

Only our source and configuration are published here. The 2026 project remains preserved on its separate `rcc2026-ci` branch. The HTTP render worker has now returned two distinct PNGs from the real 2013 engine on native Windows.

## First native hypothesis

This Studio image contains the `-ide`, `-fileLocation`, and `-script` arguments and ships plain Lua built-in plugins. The first bounded Windows test opens an owned empty place and adds one independently owned plugin. That plugin creates a floor and red/green/blue blocks, positions the camera, and prints a random marker after its scene setup succeeds. Its source uses 2013-era Lua and engine APIs.

The probe captures the desktop, owned process window metadata, and redacted native logs. A desktop screenshot alone is not classified as a validated engine render. The executable is not patched.

[First native run](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39265795329) opened the owned place and initialized Direct3D 9 with Microsoft Basic Render Driver. The plugin failed because this old plugin environment has no `spawn` global. [Second native run](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39266372036) used synchronous initialization: the random `SCENE_READY` marker was emitted and the screenshot visibly shows the three colored blocks and original studded surfaces. Its owned render viewport is titled `QOgreWidget`, distinct from Studio's toolbar and panels.

## Verified checkpoint — 2026-10-19

Latest: [native player and console run 39308899770](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39308899770), source commit `e47a5db974d5b1cdc7046c1dba71a0478d81426f`, passed all three control-plane tests, three actual engine jobs, and the Chrome console integration check. The avatar PNG was visually inspected: it shows the yellow rounded head and smiling face, yellow arms, blue torso, green legs, and the old Humanoid name/health display. The console screenshot visibly includes the owner's supplied logo and this same avatar image. The avatar is a static owned R6 fixture, not a joined live player or a fetched account appearance.

| Latest native job | PNG dimensions | PNG SHA-256 |
| --- | --- | --- |
| Blocks | 512 × 512 | `bb51910a504dcde1dd7aabb42bf3d0f155cfb41080688379509a2450ec325ac3` |
| Uploaded place, custom camera | 640 × 360 | `d3f67dabe9c5fc14b5c8ed4ed9f8710389c8b23daeed8b86b0e55ccea883746f` |
| Classic R6 player | 512 × 512 | `d56fa8c6ab70c72fd68b16705e0088fa0110f79bbd8380b40bee22aa9af52672` |

`api-validation.json` records the independent scene markers, native viewport dimensions, and image hashes; `console-validation.json` identifies the exact avatar job and PNG shown by the browser. The images are `default-render.png`, `uploaded-render.png`, `avatar-render.png`, and `console-preview.png` in the Actions evidence artifact. The native portrait currently includes the old Humanoid name and health bar; suppression of that overlay is not implemented.

Earlier checkpoint:

[Native HTTP validation run 39268119152](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39268119152), source commit `5f3eae203a729c6113eeb176e6bc5d02ee78e463`, passed the two control-plane tests and two actual Studio render jobs. Both jobs emitted their own random scene-ready marker, captured the foreground process's `QOgreWidget`, and returned PNG bytes through the HTTP image endpoint. The downloaded images were also visually inspected: the first shows the studded floor with red/green/blue blocks; the second shows the uploaded orange/yellow blocks.

| Actual engine job | PNG dimensions | PNG SHA-256 |
| --- | --- | --- |
| Default owned scene | 870 × 578 | `c19036540b6dd7fe0e58f0782cf8bf82f1a56e8abdee47101303753a0cb505d6` |
| Uploaded local place | 1024 × 578 | `924af79b47fc482045283183eefb37603691628778dddad71589d5f7ff676750` |

The native evidence artifact includes `api-validation.json`, both returned images, per-job results, startup screenshots, and redacted engine logs. Its retention is seven days. The differing widths in that initial checkpoint reflect Studio's dock layout. Uploaded-place success checks the engine marker and native viewport capture; it does not automatically prove that every object or asset in an arbitrary place loaded correctly. These tests establish these two scenes only. Player was downloaded and identified but has not been launched or tested for joining.

The first API attempt failed before starting Studio because SQLite context managers commit transactions without closing their connections. Connections now close explicitly, and the Windows tests pass with normal temporary-directory cleanup.

## Local renderer API

On a Windows machine with a visible desktop session:

```text
cd rcc2013
python -m pip install Pillow
python download.py
python server.py
```

Open `http://127.0.0.1:64313/` for the branded render console. It uses the owner's original transparent logo, the actual render API, local place uploads, camera presets, PNG downloads, and the twenty most recent persisted jobs. It contains no simulated render output.

The service listens on `127.0.0.1:64313` and serializes render jobs through one native Studio worker. Job state is persisted in SQLite. The worker uses the identified native viewport's bounds to capture a clean PNG after the owned camera/scene plugin emits its marker. It verifies the executable digest before every launch. The default fixture additionally requires visible red, green, and blue pixel regions.

| Request | Result |
| --- | --- |
| `GET /` | Render console with the project logo |
| `GET /health` | Service identity and deployment presence |
| `GET /v1/renders` | Twenty most recent persisted render jobs |
| `POST /v1/renders` with `{}` | Queue the owned three-block scene; returns job `id` |
| `POST /v1/renders` with `{"scene":"avatar"}` | Queue the owned classic R6 player fixture |
| `POST /v1/places` with raw `.rbxl`/`.rbxlx` bytes | Store a place by SHA-256; returns `place_id` |
| `POST /v1/renders` with `place_id`, optional `camera` and `size` | Queue an uploaded local place; cannot be combined with a built-in `scene` |
| `GET /v1/renders/{id}` | Queued/running/succeeded/failed state and native evidence |
| `GET /v1/renders/{id}/image` | PNG after success; HTTP 409 while unavailable |

Camera input accepts `position`, `target`, and `fov`, for example `{"position":[19,15,23],"target":[0,2,0],"fov":50}`. Optional `size` is `{"width":512,"height":512}`. The worker restores and resizes only its owned Studio window until the native viewport matches the requested dimensions; it does not stretch, crop, or resample the PNG. Both dimensions must be integers between 128 and 2048. The worker fails explicitly if the requested viewport cannot fit its desktop or Studio's minimum window layout. Omit `size` for the existing viewport. [Sizing run 39308295354](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39308295354) passed actual native 512 × 512 and 640 × 360 image checks, including a custom camera on the uploaded scene.

Inputs are validated numeric data, not Lua source. Uploads are limited to 8 MiB; the pending queue is limited to sixteen jobs. Three control-plane tests exercise invalid camera/size input, scene selection, path rejection, HTTP status handling, console assets, history, and image delivery with an explicitly mocked engine. `windows_e2e.py` separately tests the actual engine through HTTP with the default blocks, an uploaded place, and the R6 player fixture. `console_capture.py` uses a fresh Chrome profile to check that console JavaScript selects a completed native avatar job and displays its actual image endpoint.

## Classic R6 player

Select **Classic R6 player** in the console, or submit:

```json
{"scene":"avatar","size":{"width":512,"height":512}}
```

The owned [avatar fixture](rcc2013/avatar.lua) builds a six-part character with a Humanoid, invisible root, and Motor6D joints. It uses the 2013 engine's Head mesh and the verified archive's bundled `content/textures/face.png`, referenced locally with `rbxasset://`. It does not fetch a modern account's appearance. All parts are anchored for a static portrait. The default avatar camera faces its front at `[7,5,-10]` toward `[0,2.6,0]`, with a 35-degree field of view. The native validator requires the random R6-construction marker, exact requested dimensions, and visible yellow/blue/green regions. Visual inspection is still required to confirm the face and appearance.

This is a new JSON render-job API around the 2013 engine. It does not implement legacy RCCService SOAP methods or game joining. Rendering currently captures the visible native viewport, so a desktop session and foreground Studio window are required; it is not a headless GPU renderer or transparent-background thumbnail service. Account-specific avatars, clothing/accessory loading, and animation are not implemented yet.

## References

- [Daniel-176's reverse-engineering wiki](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki), inspected revision `a7a6802ed56263dfb8c97e199b2c65bce1db33a6`.
- [Roblonium archive](https://archive.roblonium.com/Client/Windows/TODO/ROBLOX%20clients/), providing both complete deployment ZIPs.
- [REA](https://github.com/morluto/rea), used locally as `rea-agents@6.7.0` for independent read-only PE resource inspection. It identified the Studio image as x86 and matched the executable digest above. No engine code was executed by that inspection.
