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

## Current custom fixture framing

The static R6 fixture has its feet at y=0, torso center at y=3, and head center
at y=4.5. Its face points toward negative Z. Camera setup uses 2013's
CoordinateFrame, Focus, and FieldOfView properties.

| Type | Eye | Look-at target | Vertical FOV |
| --- | --- | --- | --- |
| full_body | [7, 5, -10] | [0, 2.6, 0] | 35° |
| headshot | [2.8, 4.8, -5.2] | [0, 4.4, 0] | 24° |

These are tuned for this owned fixture. Arbitrary avatar accessories and body
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
