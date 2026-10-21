# RCC2013 — custom RCCService

<img src="rcc2013/static/logo.png" width="66" height="66" alt="Project owner’s RCC logo">

An original **Windows x64 C++ `RCCService.exe`**, with the owner's logo embedded
as its icon. It owns the UDP endpoint and starts **`RCCRenderWorker.exe`**, our
packaged offscreen renderer. Neither component launches Studio. The renderer
currently uses our Python/NumPy rasterizer bundled into an executable; it has
not yet been rewritten in C++.

**Hosting is unfinished.** The real, locally configured November 2013 Player
accepts the custom service's connection and applies all 15 server-generated
built-in service GUIDs. Roblox world replication, character admission, Lua
simulation, and playable joining are not implemented. This application checkpoint
must never be called a full join.

## Verified checkpoint

[Native Windows run 39548968777](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39548968777),
source `3fe4a2d6dd7e743449af8f43ead6c1bdfd9d7566`, verified:

| Capability | Actual result |
| --- | --- |
| Native C++ service builds with owner icon | Passed |
| UDP port belongs to `RCCService.exe` | Passed |
| Real Player `ConnectionAccepted`, with Studio absent | Passed |
| Original globals sender: 15 server-only random GUIDs observed in native Player objects | Passed; no Studio |
| Continuous native recording | Passed; globals checkpoint, no playable world |
| Headshot, full body, game and item rendering through EXE entry point | All four passed |
| Transparent avatars/items and no GUI objects created | Passed for tested fixtures |
| Original 2013 lighting/material parity | Unverified; current lighting is our approximation |
| Playable game, player replication and physics | Not implemented |

See [custom service development](docs/custom-rcc.md) for exact evidence, limits,
and the next protocol work. The old [Studio reference](docs/studio-reference-renderer.md)
is retained for comparisons, with manual workflows only.

The next source revision adds bounded reliable fragmentation and an original
40,010-byte descriptor sender. Its new native validation is pending; ACKs will
prove transport delivery only, not world replication or playable joining.

## Use the executable bundle

The native workflow commits the two tested executables and a hash/build manifest
to [`server2013/bin`](server2013/bin). Its Actions artifact also retains evidence.
No Roblox executable is included in that bundle.

Place both EXEs in the same directory. For avatar mesh/texture data, restore only
the seven pinned data assets using the source helper:

```text
cd rcc2013
python restore_custom_assets.py --destination ../server2013/bin/content
cd ../server2013/bin
RCCService.exe -console
```

Open `http://127.0.0.1:64313/` for the console. Our native host listens on numeric
loopback UDP port 53640. Close the console or press Ctrl+C to stop the service
and its worker. `--network-only` runs the globals/network experiment without a renderer.
Use `--help` for port, content, data, output and bounded-duration options.

The helper checks the full pinned archive hash, extracts only six `.mesh` files
and `face.png`, and checks each data-file hash. It extracts no EXE or DLL.
The binary bundle requires no separately installed Python; the restoration
helper is currently a source setup step. Owned block/item scenes can render
without these optional avatar assets.

## Render API

The SQLite job queue, asset delivery and logo-branded console are shared by the
custom worker. `POST /v1/renders` accepts:

```json
{"type":"headshot","size":{"width":512,"height":512}}
```

```json
{"type":"full_body","size":{"width":450,"height":600}}
```

```json
{"type":"game_thumbnail","size":{"width":640,"height":360}}
```

```json
{"type":"item","asset_id":3,"size":{"width":512,"height":512}}
```

Upload local assets with `POST /v1/assets?kind=mesh|texture|model`, or an XML
place with `POST /v1/places`. Poll `/v1/renders/{id}` and download
`/v1/renders/{id}/image`. Avatar/item outputs are straight RGBA PNGs; game
thumbnails are opaque. Unsupported geometry fails explicitly. Arbitrary Lua is
not executed by the render API. `/health` identifies `custom_software`.

The current custom renderer supports the owned classic R6 fixture, static Block
Parts, uploaded version-2 meshes and PNG mesh textures. XML place/model rendering
supports only this geometry subset. Terrain, animation, materials beyond our
simple shading, arbitrary avatars/accessories, and general binary places remain
unfinished. No game scripts, GUI, health/name displays or Studio chrome are
instantiated in a custom render.

## Build and tests

The [native service workflow](.github/workflows/rcc2013-native-service.yml) builds
with MSVC, embeds the owner's icon, packages the renderer, runs native tests,
records the Player connection, then publishes only our tested EXEs and notices.
The complete owned source and build scripts are committed. Download identities
for archived reference deployments remain in `rcc2013/packages.json`.

```text
python -m pip install Pillow numpy
python -m unittest discover -s rcc2013 -p "test_*.py" -v
python -m unittest discover -s server2013 -p test_transport.py -v
```

The custom renderer tests forbid process launches while exercising rasterization,
dependency integrity, item cleanup, the real queue and image validation. Native
Windows tests separately exercise the actual packaged executables. The 2026
experiment remains untouched on its own branch.

### Exact 2013 protocol mapping (2026-10-21)

The bounded native reference probe decoded 288 class, 814 property and 244 event
names/network IDs plus 159 type entries using the public RakNet Huffman format.
The complete initial descriptor message was decoded with zero remaining bits. The observed mapping
and provenance are in `server2013/protocol/descriptor-0.130.0.40915.json`; see
`docs/custom-rcc.md` for the native evidence and validation gate. This prepares
application replication work. **The custom host still has no playable world;
`game_join_validated=false`.**
