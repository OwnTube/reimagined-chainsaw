# RCC2013

Experimental renderer work using archived November 2013 Roblox Player and Studio.

The complete deployments are downloaded directly from the user's supplied Roblonium archive, with pinned ZIP and executable SHA-256 digests in [packages.json](rcc2013/packages.json). The Studio PE reports version **2013.11.25.2**, a 2013-11-26 build timestamp, and x86 architecture; Player reports **0.130.0.40915**, also x86. These are archive-supplied files; their hashes identify the tested bytes, not independently verified vendor provenance.

Only our source and configuration are published here. The 2026 project remains preserved on its separate `rcc2026-ci` branch. A real 2013 scene has now been observed in native Studio; the HTTP render-worker path is being verified next.

## First native hypothesis

This Studio image contains the `-ide`, `-fileLocation`, and `-script` arguments and ships plain Lua built-in plugins. The first bounded Windows test opens an owned empty place and adds one independently owned plugin. That plugin creates a floor and red/green/blue blocks, positions the camera, and prints a random marker after its scene setup succeeds. Its source uses 2013-era Lua and engine APIs.

The probe captures the desktop, owned process window metadata, and redacted native logs. A desktop screenshot alone is not classified as a validated engine render. The executable is not patched. The next implementation step depends on actual scene/script evidence from this run.

[First native run](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39265795329) opened the owned place and initialized Direct3D 9 with Microsoft Basic Render Driver. The plugin failed because this old plugin environment has no `spawn` global. [Second native run](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39266372036) used synchronous initialization: the random `SCENE_READY` marker was emitted and the screenshot visibly shows the three colored blocks and original studded surfaces. Its owned render viewport is titled `QOgreWidget`, distinct from Studio's toolbar and panels.

## Local renderer API

On a Windows machine with a visible desktop session:

```text
cd rcc2013
python -m pip install Pillow
python download.py
python server.py
```

The service listens on `127.0.0.1:64313` and serializes render jobs through one native Studio worker. Job state is persisted in SQLite. The worker uses the identified native viewport's bounds to capture a clean PNG after the owned camera/scene plugin emits its marker. It verifies the executable digest before every launch. The default fixture additionally requires visible red, green, and blue pixel regions.

| Request | Result |
| --- | --- |
| `GET /health` | Service identity and deployment presence |
| `POST /v1/renders` with `{}` | Queue the owned three-block scene; returns job `id` |
| `POST /v1/places` with raw `.rbxl`/`.rbxlx` bytes | Store a place by SHA-256; returns `place_id` |
| `POST /v1/renders` with `place_id` and optional `camera` | Queue an uploaded local place |
| `GET /v1/renders/{id}` | Queued/running/succeeded/failed state and native evidence |
| `GET /v1/renders/{id}/image` | PNG after success; HTTP 409 while unavailable |

Camera input accepts `position`, `target`, and `fov`, for example `{"position":[19,15,23],"target":[0,2,0],"fov":50}`. The input is validated numeric data, not Lua source. Uploads are limited to 8 MiB; the pending queue is limited to sixteen jobs. Two control-plane tests exercise invalid camera input, path rejection, HTTP status handling, and image delivery with an explicitly mocked engine. `windows_e2e.py` separately tests the actual engine through HTTP with both the default scene and an uploaded place.

This is a new JSON render-job API around the 2013 engine. It does not implement legacy RCCService SOAP methods or game joining. Rendering currently captures the visible native viewport, so a desktop session and foreground Studio window are required; it is not a headless GPU renderer or transparent-background thumbnail service. Requested output sizing and avatar-specific setup are not implemented yet.

## References

- [Daniel-176's reverse-engineering wiki](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki), inspected revision `a7a6802ed56263dfb8c97e199b2c65bce1db33a6`.
- [Roblonium archive](https://archive.roblonium.com/Client/Windows/TODO/ROBLOX%20clients/), providing both complete deployment ZIPs.
- [REA](https://github.com/morluto/rea), used locally as `rea-agents@6.7.0` for independent read-only PE resource inspection. It identified the Studio image as x86 and matched the executable digest above. No engine code was executed by that inspection.
