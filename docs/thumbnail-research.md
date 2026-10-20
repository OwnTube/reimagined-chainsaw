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
| full_body | [-2.44, 5.06, -4.92] | [0, 2.4, 0] | 58° |
| headshot | [0.585270966, 4.5, -2.942355841] | [0, 4.5, 0.1] | 30° |

The full-body preset reconstructs the owner's supplied profile thumbnail
rather than claiming RCC's internal transform. The 150x200 reference
`e797908ced9d74ed0383b46d95a10e30.png` has SHA-256
`89de5b7bd3bfcd1935f9caf1239725c442299253293fab6bc6428f2d992a3718`;
its alpha bounds are (16,12,147,171). A local silhouette fit against the
bundled R6 meshes selected an opposite-side view at approximately -26.4° yaw
and 25° elevation. The rounded coordinates above preserve that view, with FOV and focus height
calibrated against an actual native portrait capture. The fit
is ambiguous from a single image, and its analytical model is not native
rendering proof. The native 450x600 portrait check requires the corresponding
reference bounds within 10 pixels, plus alpha, margins, and engine markers.
Square requests use the same camera and preserve all body parts.

The headshot remains equivalent to the supplied headshot.lua's no-accessory
case. It uses head CFrame, three-stud distance, -pi/16 yaw, +0.1 local Z target,
and 30° base FOV. Accessories and arbitrary body scales remain unimplemented
in the Studio fixture; their presence in an RCC template is not engine proof.

## Owner-supplied RCC scripts — 2026-10-20

The original `headshot.lua` and `thumbnail.lua` attachments are preserved
byte-for-byte in `rcc2013/templates`, with SHA-256 pins and checkout attributes
that prevent Windows line-ending conversion. `provided_scripts.py` prepares
job copies using only owned numeric-loopback HTTP endpoints, supplied avatar
JSON, dimensions, and job parameters. Camera formulas and the five Click
arguments remain intact. Three local-copy corrections fix Instance.New,
the undefined url used by ScriptInformationProvider, and full-body render(1)
ignoring the configured user ID. The attachments are not edited.

The headshot uses GraphicsMode 4 and Click('png', width, height, true, true).
The full-body template uses GraphicsMode 2 and
Click('png', width, height, true, false); it delegates framing to native
ThumbnailGenerator and contains no numeric full-body camera coordinates.
Site, appearance/asset loading, and upload placeholders must be supplied; the
files are not standalone jobs without that backend.

[Native compatibility run 39431967946](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39431967946),
source `77699697449fd9e7262db33fdfeb4312d3202eff`, observed the exact Studio
error: `'ThumbnailGenerator' is not a valid Service name`. The native report
has `thumbnail_generator_available=false`, `provided_scripts_executed=false`,
and `engine_render_validated=false`. That workflow's success means the
capability probe was observed, **not** that either RCC script rendered.
The existing Studio renderer cannot run these Click calls unchanged. A
compatible native RCC runtime remains missing for direct execution; no newer
engine is silently substituted or advertised as a 2013 RCC build. The Studio
image reconstruction is a separate supported path.

## Alpha and UI removal in the Studio wrapper

This project still captures the native 2013 Studio viewport; it does not claim
to implement RCC's internal ThumbnailGenerator. Before player capture the
owned fixture's Humanoid is detached, preventing the old engine's automatic
name and health display. Its anchored geometry, explicit body meshes, head
mesh, and face remain.

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

## Dedicated classic body geometry

The initial fixture used ordinary Parts for the torso and limbs; removing its
Humanoid to suppress UI left those parts with plain box geometry. The pinned
Studio deployment contains a native `content/fonts/character3.rbxm` character
template plus `torso.mesh`, `leftarm.mesh`, `rightarm.mesh`, `leftleg.mesh`, and
`rightleg.mesh`. Each of these body meshes has 42 vertices and 44 triangles,
including bevelled edges; the torso spans 2 × 2 × 1 studs and each limb 1 × 2 × 1.

The renderer now loads that local character template, normalizes its anchored
parts to the existing camera coordinate system, and explicitly assigns those
five body meshes before removing the Humanoid. The bundled head mesh and face
are retained. All assets are read from the pinned runtime download, without
copying proprietary model or mesh bytes into this repository. Each native
pass records the six asset hashes and five Lua body-mesh assignment markers.
This remains a static classic R6 appearance, not arbitrary account/body-package
loading.

[Windows run 39319529320](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39319529320)
at source commit `7c9317516f872873181d4e4b06449b967854827e` passed eight local
tests, four actual HTTP render jobs, and the console check. Both player PNGs
were visually inspected: rounded bevels are visible on the torso and limbs,
with separated leg edges. The 512 × 512 full-body PNG has 204,963 transparent
and 57,181 opaque pixels; its SHA-256 is
`7220f21ea9f70ef9421408ec02b3520b5a749a807c19219eb2a3b235eeac6b16`.
The headshot retains its source-equivalent camera and no-GUI behavior, with
SHA-256 `57b8c4364616b2a8462413f5af42637d48ec41b1abd1054ee5f612353e4c5381`.
All four native player passes reported the same bundled asset hashes and all
five dedicated body-mesh assignments. The underlying 2013 classic R6 body
still has a block-shaped silhouette; other body packages are not implemented.

## Native verification of the owner's profile framing

[Run 39433202145](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39433202145),
source `8f05824625642c886b9ffaac1d193f0f9016c320`, passed eight local renderer
checks, five native HTTP jobs, and console validation. All returned native
player passes confirmed the original six bundled asset hashes, five dedicated
body meshes, GUI removal, exact output size, and matching camera markers.
The portrait is 450x600 RGBA with alpha bounds (43,33,441,512), compared with
reference bounds (48,36,441,513) at that scale. Clear corners and margins
remain; the full character fits the frame. The 512x512 square variant also
passed. Both were captured through the native Studio viewport and alpha
recovery, not by transforming the supplied picture.

| Output | SHA-256 |
| --- | --- |
| Full body, 450x600 portrait | `8e2ae7fe6a3d907ac510fe3282fe0c06e8f628f2cb97129c0f64da503aa19b04` |
| Full body, 512x512 | `d599e6449221d0f63b219479203a32248dbcda8ea00a829be255f80191d272f8` |
| Headshot, 512x512 | `57b8c4364616b2a8462413f5af42637d48ec41b1abd1054ee5f612353e4c5381` |

The portrait was visually inspected. Its colors and face belong to the owned
fixture; this validates reconstructed framing, not the reference account's
clothing/appearance or execution of native RCC ThumbnailGenerator.
