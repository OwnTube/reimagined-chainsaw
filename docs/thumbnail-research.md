# Thumbnail and positioning research

Inspected 2026-10-19: Daniel-176/Roblox-Reverse-Engineering-Wiki revision
`a7a6802ed56263dfb8c97e199b2c65bce1db33a6` (181 tracked files).
The current repository was searched for headshot, thumbnail, camera,
CurrentCamera, CoordinateFrame, FieldOfView, CFrame, and positioning terms.

## What the supplied wiki actually contains

| Source | Finding |
| --- | --- |
| [Research/thumbs](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki/blob/a7a6802ed56263dfb8c97e199b2c65bce1db33a6/Research/thumbs) | Small RCC examples for 2007/8 and 2015+ create/load a local player and invoke ThumbnailGenerator. No explicit camera positioning. |
| [Thumbnail rendering guide](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki/blob/a7a6802ed56263dfb8c97e199b2c65bce1db33a6/articles/infrastructure/api/thumbnails.md) | Repeats those rendering examples. No headshot framing script or camera transform. |
| [RCC overview](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki/blob/a7a6802ed56263dfb8c97e199b2c65bce1db33a6/articles/rccservice/windows/how2rcc.md) | Documents ThumbnailGenerator.Click arguments: image format, width, height, and hideSky; returns base64 image data. It does not document its internal camera algorithm. |
| [Web API reference](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki/blob/a7a6802ed56263dfb8c97e199b2c65bce1db33a6/articles/infrastructure/api/thumbnails-web-api.md) | Lists avatar, avatar-headshot, avatar-bust, and game-thumbnail endpoints/types. It describes a 2020-era web API, not the exact 2013 render scripts. |
| Research gameserver and camera-fix notes | Discuss gameplay camera scripts/flags, not thumbnail camera positions. |

No exact headshot/full-body positioning Lua script was found in this revision.
Our camera presets must therefore be described as custom, rather than original
Roblox RCC camera coordinates. The guide's final Click argument is documented
as hideSky; that signature alone is not proof of the alpha behavior of every
Studio/RCC build.

## Revival source findings — 2026-10-19

The subsequent source-code search did find a headshot positioning algorithm
outside the wiki. Sources were read as text; their servers and setup scripts
were not executed.

| Source and revision | Headshot positioning | Full-body positioning |
| --- | --- | --- |
| [BubbaBlox v2 headshot](https://github.com/harryzawg/bubbablox-v2/blob/6e355d803dd332797ae714b65e72f71c5bd08c2e/renderer/scripts/player/headshot.lua), revision `6e355d803dd332797ae714b65e72f71c5bd08c2e` | Eye at head height, 3 studs away, 11.25-degree side angle; target offset 0.1 stud toward positive local Z. No-hat FOV 30 degrees. Accessories can raise target up to 0.5 stud and widen FOV toward 130. | [thumbnail.lua](https://github.com/harryzawg/bubbablox-v2/blob/6e355d803dd332797ae714b65e72f71c5bd08c2e/renderer/scripts/player/thumbnail.lua) optionally selects an existing ThumbnailCamera, then delegates to ThumbnailGenerator; no numeric full-body transform in that file. |
| [Economy Simulator headshot](https://github.com/ccr0/economy-simulator/blob/b96fda81a4814ee8ae93bb7d4002a725d029c013/services/game-server/scripts/player/headshot.lua), revision `b96fda81a4814ee8ae93bb7d4002a725d029c013` | Same head-level distance, angle, and target formula; no-hat FOV 40, expanding toward 60. | [thumbnail.lua](https://github.com/ccr0/economy-simulator/blob/b96fda81a4814ee8ae93bb7d4002a725d029c013/services/game-server/scripts/player/thumbnail.lua) delegates full-body framing to ThumbnailGenerator. |
| [Economy Simulator Fixed headshot](https://github.com/SrCookie450/economy-simulator-fixed/blob/56e79049f210388ad046f115bd7a1ee30e343f7c/services/game-server/scripts/player/headshot.lua), revision `56e79049f210388ad046f115bd7a1ee30e343f7c` | Same position formula; no-hat FOV 30, expanding toward 100. | Only the headshot script was used for this comparison. |

The source headshot eye formula uses a yaw of negative pi/16 and a forward
look vector multiplied by 3, added to the head's transform. For our upright
identity-rotation head at [0,4.5,0], that becomes eye
[0.585270966,4.5,-2.942355841] and target [0,4.5,0.1]. The new independent
geometry helper derives these coordinates numerically. It does not import
the revival's asset-loading, networking, or server code.

The headshot default now follows BubbaBlox's **no-hat R6 case**. This is not a
claim that those later RCC scripts establish original 2013 Roblox defaults.
Their FOV differences are retained in this comparison instead of silently
treating all revival versions as identical. Accessory-aware zoom and rotated
or resized heads are not implemented. Full-body framing remains custom
because the inspected full-body scripts do not expose RCC's internal framing.

## Current fixture framing

The static R6 fixture has its feet at y=0, torso center at y=3, and head center
at y=4.5. Its face points toward negative Z. Camera setup uses 2013's
CoordinateFrame, Focus, and FieldOfView properties.

| Type | Eye | Look-at target | Vertical FOV |
| --- | --- | --- | --- |
| full_body | [7, 5, -10] | [0, 2.6, 0] | 35° |
| headshot | [0.585270966, 4.5, -2.942355841] | [0, 4.5, 0.1] | 30° |

The full-body preset is custom; the headshot is the source-equivalent no-hat
case described above. Arbitrary avatar accessories and body
scales require bounds-aware framing, which is not implemented.

## Alpha and UI removal in the Studio wrapper

This project still captures the native 2013 Studio viewport; it does not claim
to implement RCC's internal ThumbnailGenerator. Before player capture the
owned fixture's Humanoid is detached, preventing the old engine's automatic
name and health display. Its anchored geometry, joints, mesh, and face remain.

Two native frames use the same scene, camera, viewport dimensions, and fixed
lighting, against contrasting solid planar backdrops. The observed backdrop
RGB is calibrated from clear upper corner patches. The pair satisfies
I = alpha × foreground + (1 − alpha) × background. Their difference determines
alpha; the foreground is recovered as straight RGBA. This does not delete
pixels by their color, so black, white, or blue avatar pixels are retained.

The worker rejects insufficient contrast, obstructed calibration patches,
dimension mismatch, and excessive registration residual. It retains both
native passes and per-pass engine evidence. Transparent PNGs are not proof of
arbitrary clothing, accessory, animation, or account-appearance compatibility.
Game thumbnails retain the scene background and use a single native capture.

The fixture's surfaces are opaque. Alpha above 0.96 is snapped to one so small
shading differences across native process starts do not make solid skin faintly
translucent. Lower alpha remains available for edge reconstruction, but
transparent clothing/accessories have not been validated. This is a measured
wrapper approximation, not a claim of RCC's internal render-target alpha.

## Native verification of the source-equivalent headshot

[Windows run 39317404183](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39317404183)
passed all eight local tests, four HTTP render jobs, and the browser console
check at source commit `71c5f1b48e50d707c3e88e6f6ea7217e7f911aa4`.
Both native headshot passes logged eye approximately
[0.585271,4.5,-2.942356], target [0,4.5,0.1], and a 30-degree FOV, within the
old engine's floating-point precision. The 512 × 512 PNG was visually
inspected: closer, nearly front-facing head framing, transparent background,
no overhead or other GUI. Its SHA-256 is
`c8bdf5ece7685b3ff4b1bfa0d74052f56d0ddbbac70cc253ac1b3c453c0d4fb8`.
