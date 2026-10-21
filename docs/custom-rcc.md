# Custom RCC development checkpoint

The user explicitly replaced the Studio-host approach with an original RCC and
requested a compiled Windows executable, their supplied logo, all render types,
native Player tests, recordings, committed source/binaries and overnight work.
Do not return to searching for a 2013 RCC archive or call hidden Studio an RCC.

## Original native host

`server2013/native/RCCService.cpp` is our C++ implementation, built with MSVC
and the Windows SDK. `RCCService.rc` embeds an ICO made from the exact existing
owner logo at `rcc2013/static/logo.png`. No proprietary engine code is copied.

It implements numeric-loopback, single-peer RakNet protocol 5 negotiation,
the 96-byte connection acceptance, 94-byte new-incoming confirmation, 64-bit
timestamps, pings, ACK parsing, bounded reliable-control retransmission,
reliable duplicate suppression, ordered receive buffering and bounded split
reassembly. Unknown Roblox application messages are retained only as IDs,
lengths and SHA-256. This is a research transport, not a production game server.
Congestion control, reconnects, complete NAK handling and wraparound/loss testing
are not complete. There is no public listener or production authentication.

Reference run [39472992617](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39472992617)
observed the working Studio/Player control connection through our unchanged
loopback UDP relay. It decoded 1,444 datagrams and 793 messages without a parser
error. The initial server application messages were IDs 129, 130 and 131; ID 130
was 40,010 bytes across 28 fragments. This records wire observations, not an
assumption that a later engine's serialization is compatible.

The transport layout was compared with the public
[RakNet reference](https://github.com/facebookarchive/RakNet/tree/master/Source).
The user-provided [wiki](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki/tree/a7a6802ed56263dfb8c97e199b2c65bce1db33a6/articles/rccservice/windows)
documents RCC jobs and SOAP; it does not supply a complete original 2013 engine.
REA 6.7.0's PE resource inspector verified the exact Player identity and the
first native host's PE32+ x64 identity/resource inventory. No decompiled engine
code, real account credential or private signing key was published.

## Native executable proof

Run [39508547826](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39508547826),
source `c3f9ab180734c646f59084b93b04837809bfebd8`, built the first native EXE:

- `RCCService.exe`: 344,064 bytes, SHA-256
  `94b1e78c6660433f46197446a6b8f007783f1f1f8d8adc66c4581b2705855952`.
- Same-process UDP ownership and native Player `ConnectionAccepted` both passed.
- Studio deployment/process absence was checked before and after.
- Continuous silent recording: 13.5 seconds, 162 frames, 1024x768 at 12 FPS,
  SHA-256 `b2ac9ea656c4de2a659102e7266dbde28d52d54ac249d3bedc3e5241bf059142`.
- `probe_checkpoint_passed=true`, **`game_join_validated=false`**.

Run [39509102731](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39509102731),
source `a24836d8b1a434864445c49a4f5fdc4f76c66baf`, also built and exercised the
packaged renderer through the native C++ entry point:

| Output | Bytes | SHA-256 |
| --- | --- | --- |
| RCCService.exe | 344064 | `5cf4fee5c650624f2b1a45d6eab346cb64986926885c0ecf63c131bb641a49e6` |
| RCCRenderWorker.exe | 27980092 | `9e032f7837997e8aacfb3224b0a954ff6117e920b5d257177bdd02c94a555d76` |

The native supervisor launched its worker, owned UDP, served the logo through
the worker's HTTP console, completed four queued render jobs and delivered PNGs
whose hashes matched their job records. The worker is a packaged Python/NumPy
implementation; only the service/network host is currently native C++.
The workflow subsequently verifies a real Player transport connection again.
The generated `server2013/bin/build.json` is authoritative for later builds.

## Studio-free rendering

`rcc2013/software_render.py` implements perspective projection, triangle
rasterization, a depth buffer, interpolated normals/UVs, local PNG textures,
Lambert shading, two-times supersampling, and straight-alpha output. It does
not use a Roblox process or screenshot a viewport. No GUI runtime exists in it.
It reads six dedicated locally restored 2013 meshes and the face texture for
the owned R6 fixture. These optional runtime data are pinned separately and are
not bundled with the executable publication.

| Native packaged job | Verified output SHA-256 |
| --- | --- |
| Headshot, 512x512 | `88e74ee3fb973a29a59d65cbb29ea530b4186b52cc666d2165424859af2e8ac6` |
| Full body, 450x600 | `4d790875e19dc24716abcbf1049c8263441a59b061f89c20feab87b1e2fdbcd1` |
| Game thumbnail, 640x360 | `dcd297d6dcfe192b15a90130b2c68406c781f92c37286861145ea00496a3bf93` |
| Owned textured sword, 512x512 | `bff4d6d09c41bcb88332dab22389ade23e96adf259972d9c292ce674f9c939d9` |

The current renderer deliberately rejects unsupported geometry/dependencies.
It is a static subset: Block Parts, XML containers, uploaded version-2 meshes,
PNG textures and a small explicit BrickColor palette. It does not implement
Terrain, original material shaders, decals on arbitrary place geometry, game
simulation, clothing compositing or arbitrary avatar appearances. Head/file
mesh behavior and lighting are not established as identical to Studio.
Headshots retain a transparent margin above the head. Full bodies/items fail
if they touch the image border. Fully transparent pixels have RGB zeroed.

The asset store sanitizes item models before storage, drops scripts/GUI/
Humanoids/joints, validates local dependencies, and verifies immutable bytes
before each read. The custom renderer reads canonical local bytes directly;
that is separate from the tested HTTP delivery endpoints. It never claims the
custom worker fetched assets over HTTP when it actually read local storage.

## Next work in order

1. Start by reading current source, binary manifest and Actions, not a stale
   scratch checkout. All work stays on `rcc2013-ci`.
2. Implement the 2013 Roblox application handshake/schema and initial replicated
   world. Compare only owned loopback test traffic and explicit read-only binary
   observations. Transport acceptance alone is already proved; repeating it
   without a new hypothesis is not progress.
3. Require a server-only random token received from native Player scene data,
   followed by bidirectional RemoteEvent/character updates. Do not put the world
   or expected server token in the client bootstrap and count it as replication.
4. Add simulation/character control, then record a continuous actual playable
   connection with our C++ host and no Studio process. The old Studio-hosted
   walk/video is only a reference.
5. Expand the custom renderer's supported scene/avatar formats and compare its
   output against historical reference images; maintain transparent GUI-free
   avatar/item output. Keep rendering parity claims separate from geometry.

The older Studio subject cleanup test began failing at the native dark pass in
run 39437930120 and remained failing in 39509102593. That reference regression
is not fixed or relabeled as success. Reference workflows are manual now; the
new native/custom pipeline is the active development path.

## Binary publication completed

[Run 39518669688](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39518669688)
passed the native build, all four packaged render jobs, the recorded native
Player transport connection with Studio absent, and binary publication.
The generated commit `796a378` added both tested EXEs, the hash manifest and
open-source runtime notices under `server2013/bin`. Source commit is
`ff3674c8bf5c4e75f73ccbdd158829f5e898abb3`. Native service SHA-256 is
`abf02a2d7f0160b46fa409c67c7d97ab0b46628ef22a13b15a93cdf6ed83c7cb`;
worker SHA-256 is
`848ce15a5155c97c70737fad474128a8eca3bafc40675a9784ad2d426f6649a4`.
`game_join_validated` remains false. Subsequent source changes need a new
verified build before replacing these binary identities.

## Exact-build application research (2026-10-21)

The later, MIT-licensed [Sala dissector](https://github.com/Arisstath/raknet-dissector/tree/1d25a8915c87606ed15cdefe02e8a99b37d7bb09)
labels `0x81` globals, `0x83` replication and `0x8a` ticket submission, but its
schema negotiation uses `0x97`, not the observed 2013 server's `0x82` message.
Its layouts are research leads, **not validated 2013 codecs**. No implementation
was copied into the custom host on that basis.

`hosting2013/schema_observer.py` now examines only server-to-client ID `0x82`.
It looks for a fixed allowlist of public API symbols at all eight bit alignments
and, separately, inside complete checksum-valid bounded zlib streams starting
within the first 32 body bytes. Output contains symbol positions and at most six
preceding/four following format bytes, not replayable application bodies. Client
tickets, globals, scripts, geometry and other unknown packets remain metadata
only. It explicitly reports `layout_validated=false`. Four synthetic tests cover
sensitive-message exclusion, bit offsets, compressed bounds/checksums, and
out-of-order split reconstruction. The dedicated Windows observation workflow
uses the existing owned Studio reference strictly as a protocol oracle; it does
not change the Studio-free product or its published binary manifest.

Reference observation [39525404964](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39525404964)
passed on source `7c99a9228afa1bf7adde46332b968b71d2d296cf`: 362 datagrams,
170 messages, zero frame decode errors, and reference-only replication/movement
checks passed. ID `0x82` was again 40,010 bytes (SHA-256
`07f8029b53d1216f29e459a623cc84e7e5980085e294b57c930b861151ea774a`).
No allowlisted symbols or complete zlib stream were found. This rules out those
specific encodings; it does not show that the message lacks a descriptor table.

Read-only inspection of the exact hash-pinned Player identified a separate
`0x82` handler that reads three counted descriptor dictionaries and uses a
RakNet-style compressed-string path. `descriptor_codec.py` implements bounded
MSB-first reading and the public BSD-licensed RakNet Huffman format, with the
upstream frequency data/license/patent notice retained under `raknet_reference`.
The table framing and compressed integer byte order are new hypotheses requiring
a native observation. The decoder exports names/IDs only after all three tables
pass bounds and string-length/identifier checks. It sends no application packet,
does not replay reference messages, and does not implement a world. Static
instruction text stays outside the repository. REA's resource inspector again
verified the exact x86 input; its objdump provider was unavailable on this host.

Native observation [39541722885](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39541722885)
on source `ead0ec3e15077b64831a60f70e1ad55b99010160` verified the new decoder:
all three dictionaries decoded, with 288 classes, 814 properties and 244 events.
All IDs form contiguous sets starting at zero. Compressed integer byte order
was big endian; the little-endian candidate failed its bit-length bound. The
three tables consume 293,884 bits, leaving 26,196 bits in the 40,010-byte message.
Names and IDs are preserved in
`server2013/protocol/descriptor-0.130.0.40915.json`, with exact input/run hashes.
For example: Part 162, Workspace 287, Players 173, StringValue 250,
RemoteEvent 193; Instance:Name 404, Instance:Parent 442, StringValue:Value 735.
These are this observed connection's mappings, not a universal table for all
2013 clients. No packet body, script key, executable or engine code is included.

The remaining handler reads a 16-bit pair count followed by pairs of aligned
16-bit-length strings. The next bounded probe checks that configuration-tail
hypothesis and exports names plus value lengths/hashes, never values. This is
separate from globals `0x81`, GUID encoding and replication `0x83`, which remain
unimplemented in the custom native host. The published EXEs remain unchanged
because these changes are protocol research tooling, not a verified host update.

Tail observation [39542021352](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39542021352)
on source `1f4e785d7c88eb64d0468610cc843c75a7ba8abf` passed the reference join
and repeated the three dictionary mappings. Reading a configuration pair count
immediately after the third dictionary produced zero, but left 26,180 bits.
Therefore that offset is **not** the end of the schema. The exact Player's
handler conditionally reads a fourth descriptor dictionary before the final
configuration-pair section. The observer now tests both three/four dictionaries
with strict complete-message accounting; partial dictionaries cannot set
`schema_complete=true`. A new synthetic fixture covers this boundary. The next
reference run tests the fourth-dictionary hypothesis, not transport acceptance.

## Complete ID 0x82 decode verified

[Run 39542227943](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39542227943),
source `39cc8bbeb9df2c20052b336b39354773d9b70944`, passed native reference
joining/movement and the 14-test Windows suite. The four-dictionary candidate
consumed exactly **320,080 bits, zero remaining**. Counts were 288 classes,
814 properties, 244 events, and 159 type entries, followed by three configuration
pairs. The fourth table ends at bit 319,267. The complete message hash matches
the earlier observations. This verifies this message's framing, not the custom
host's application handshake or world replication.

Each dictionary is a big-endian uint32 count, followed by entries containing
a big-endian uint32 ID, big-endian uint32 decoded character count, and a RakNet
Huffman compressed string. The string's compressed-bit-count integer uses the
network-endian RakNet compressed-integer representation. Fields are not generally
byte aligned. After the fourth dictionary come a big-endian uint16 pair count
and two uint16-length strings per pair; each raw string's bytes begin at the
next byte boundary. Configuration values are retained only as lengths/hashes.

The checked-in descriptor fixture now contains all four ID/name tables and
redacted configuration fields. IDs, rather than names, must remain the identity:
`AnimationTrackState:AdjustAnimation` has two event IDs, and several type entries
share names. The standalone `verify_schema_observation.py` gate requires a fully
consumed pinned message and compares every ID/name to the reviewed fixture. It
rejects a partial parse even when the reference join succeeds. Native product
binaries were not rebuilt for these research-only changes.

Next implementation steps are original packet encoding, `0x81` globals/service
GUIDs, then `0x83` instance/property replication. Read-only exact-build leads:
the Player's `0x81` handler starts with a single bit (and a feature-dependent
second bit), unlike the later Sala layout. Its service GUID reader uses a
cached scope plus a variable-bit-width index. These are static observations
requiring owned wire validation before a sender is implemented. Do not copy the
later six-byte globals header or insert reference packet replay into our host.

The new gate was run locally against the downloaded `39542227943` trace and
passed. Deliberately marking the parse partial, changing a descriptor name, or
changing the message hash each caused rejection. The gate itself is a new
post-processing step for future native observations; it was not a step in that
already-completed run. No unchanged native run was repeated merely to add this
evidence check.
