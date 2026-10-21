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

## Original encoding and globals investigation

`server2013/protocol/DescriptorWriter.hpp` adds a portable original C++ bit
writer and Huffman encoder for the four descriptor dictionaries. It consumes
ID/name fields, validates dense IDs without collapsing repeated names, and
generates dictionary bits independently. It does not load or replay captured
packets. The tiny `descriptor_writer_probe.cpp` is an offline test executable,
not a replacement host or an engine runtime. The public RakNet frequency table
retains its BSD attribution and notices. The shipped EXEs are unchanged.

On Linux, GCC C++17 compilation with warnings treated as errors passed. Encoding
the decoded reference fields in their observed order produced 319,267 bits /
39,909 padded bytes; the independent Python decoder recovered all four tables
and exact field boundaries. Hash was
`d6ee3d0df270316e36ac68fa5b7d5175d740f9dc090766a2f4a5230a6c57b409`.
This is a field round trip until compared against the actual wire prefix hash.
The Windows observation workflow now compiles this C++ encoder with MSVC and
requires its generated prefix hash to match the fresh native reference's masked
dictionary prefix. No native engine packet body is exported.

The same new observation tests `0x81` globals with one/two header bits, bounded
cached scope strings (literal flag in the cache byte's high bit), and 32-bit
raw little-endian indices. These framing hypotheses follow read-only exact-build
inspection; scopes are exported as hashes/lengths only. A complete candidate
must consume the RakNet frame's exact valid bit count. Three synthetic tests
cover literal/cache scopes, x86 byte order, sensitive-message exclusion and
truncation. Even a complete candidate does not identify which GUID belongs to
which service, and it does not implement globals in the native host.

Native [run 39547726331](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39547726331),
source `6358ec85c2c302ca58cc6ca5ce345c3bda228cab`, passed MSVC compilation,
all 18 Windows tests, native reference joining, the complete schema gate, and
the independent C++ wire-prefix hash comparison. The C++ output matches the
actual native dictionary prefix exactly: 319,267 bits, SHA-256
`d6ee3d0df270316e36ac68fa5b7d5175d740f9dc090766a2f4a5230a6c57b409`.
The first attempt, 39547581361, stopped before launching Roblox because cmd
received a forward-slash build-script path; the corrected run used a native
Windows path. No reference deployment was launched in that failed attempt.

The globals observation found one complete framing candidate: **two bits [1,0],
15 GUID references, a single literal 35-character scope in cache slot 1 followed
by cached references, and raw little-endian 32-bit indices**. It consumed all
1,035 valid bits in a 130-byte frame; the one-header-bit candidate failed. Scope
values remain absent from exported evidence. Service order is not identified
yet, and the two flag semantics are not claimed from framing alone.

The next probe adds original C++ encoding of this observed globals subset and
compares its masked valid bits directly with the owned wire message. Scope
plaintext exists only briefly in an isolated temporary codec input, is deleted
with that temporary directory and is not written into the trace/artifact. It
also asks both reference peers for each existing service's `GetDebugId(0)` and
correlates numeric indices to class names. The API call is guarded with pcall;
no security-level changes or memory writes are made if it is unavailable. A
class is identified only if host/client observations uniquely agree. These are
new hypotheses; the already verified dictionary format is only a regression
check in the combined bounded run.

Native [run 39548253205](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39548253205),
source `e2572d2edeb81bc5ffc692d022516683074a20db`, passed the generated C++
globals-to-wire comparison as well as the dictionary gate. The masked globals
message used 1,059 valid bits / 133 bytes in this run; scope compression size
can vary, so the 1,035-bit observation is not a fixed packet size. The parsed
flags/cache/index layout and 15-reference count were unchanged. Scope plaintext
was not exported. Twelve service classes uniquely agreed between host and Player.
The Player reported Teams, ReplicatedStorage and TestService for the three
remaining references, but those services were absent from the host's early
snapshot; they are not yet labeled independently verified. A later host snapshot
at player admission is the next timing hypothesis.

## Service-root order identified and native sender implementation

[Run 39548487540](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39548487540),
source `0f6e5a37d3f932dc1afd1543409044596cc3621c`, independently matched all
15 root indices to the same classes on host and Player after player admission.
The order is Lighting, SoundService, StarterPack, StarterGui, Workspace,
JointsService, Players, Teams, InsertService, Chat, FriendService,
MarketplaceService, BadgeService, ReplicatedStorage, TestService. The scope/ID
values are per-run; only this pinned build's service order is used by the sender.
Field evidence and provenance are in `globals-0.130.0.40915.json`.

The native `Host` now contains an original globals sender using the validated
C++ writer. It generates a fresh 35-character scope and 15 independent random
positive GUID indices inside RCCService.exe, sends the bit-accurate reliable
ordered `0x81` message, and reports only the class/index bindings. The client
bootstrap knows neither the expected indices nor an expected world/token; it
simply queries existing native service objects with GetDebugId(0). The Windows
harness compares all 15 observed indices to the C++ server's runtime output.
That native integration is a new hypothesis until its native workflow passes.

The checkpoint now requires both transport acceptance and all server-generated
globals observed in Player object data. It is **not an owned world proof**: no
`0x82` dictionary is sent by the host yet, no `0x83` instance/property replication
exists, and no Lua simulation or locomotion is implemented. `game_join_validated`
remains false. The binary publisher refuses publication without the new globals
proof and includes the public RakNet data's BSD license/patent notices.

## Native application globals proof and published binaries

[Native run 39548968777](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39548968777),
source `3fe4a2d6dd7e743449af8f43ead6c1bdfd9d7566`, passed the updated native
application checkpoint. All **15 fresh random indices generated only inside
RCCService.exe were observed on the matching built-in service objects in the
real 2013 Player**. The client source contained no expected indices or server
world/token. Studio absence was checked before and after; UDP belonged to the
native service. This verifies the original `0x81` sender and service GUID binding.
It does not verify new world instances, a local Player character, Lua simulation,
movement or a playable game. The game's `passed`/`game_join_validated` fields
remain false; only the explicitly named application checkpoint is true.

The same job passed all four packaged custom render types and published both
owned EXEs plus runtime/RakNet notices in binary commit `de4a530`. Authoritative
manifest: `server2013/bin/build.json`. The service is 361,984 bytes, SHA-256
`00bfd0f1473d8e527efbc51fdb9b08cdb6572d605d9c732c0f90c7b46ea09d94`;
the worker is 27,980,982 bytes, SHA-256
`938a810336a7d9d4051975740e1f2959829e8f7fc37fa5653fc021d4fd7836d3`.
A continuous 13.5-second, 162-frame 1024x768/12 FPS silent recording validated,
SHA-256 `9b2df58e06dd195737e2cb2a2ee82cd0c2eba57e9c351db2c75b6228c26c852a`.
It records this globals checkpoint, not a playable join. Compact source/run
evidence is retained in `server2013/protocol/native-globals-checkpoint.json`.
The concurrent reference regression run 39548968678 also passed.

Next: send the already independently validated original `0x82` dictionaries from
the native host, adding bounded outgoing fragmentation/reliable queuing; then
implement exact `0x83` instance/property serialization for a server-owned world
and StringValue token. Require the server-only token in actual Player scene data
and bidirectional updates before changing `game_join_validated`. No dictionary
replay or locally fabricated client world should be used as evidence.

## Original descriptor delivery implementation (2026-10-21)

The native host now queues an original `0x82` after its `0x81`. Build-time
`generate_descriptor_header.py` embeds the measured API ID/name fields into the
EXE; no captured packet or runtime JSON dependency is included. IDs remain
unchanged even when names repeat. Our canonical entry order is ID order, so its
message hash differs from the reference's enumeration order. The three explicit
owned settings are `false`; their lengths/hashes match the reference observation.

The complete original message is 40,010 bytes / 320,080 bits, SHA-256
`7f12d60aa1491cefdd0dba70884f71daa9de4a8553072b519fdaa7166c72676b`.
An independent Python decoder checks every ID/name, configuration field and
consumption boundary against the measured fixture. This is field equivalence,
not a replay or a claim that the Player applied the schema.

`ReliableSender.hpp` handles negotiated MTUs 576..1492, ordered reliable
fragmentation, shared message order/split IDs, distinct reliable indices and
partial final bytes. The queue caps resident wire bytes at 1 MiB, active messages
at 128 and in-flight datagrams at 64. ACKs free window slots; unacknowledged
packets retry unchanged every 500 ms with at most eight retries. This remains a
bounded loopback research transport, without full congestion control or reconnect.
Offline tests recover 20 size/MTU/partial-bit combinations in reversed fragment
order and exercise lost packets, retry expiry, duplicate ACKs and queue limits.

The new native hypothesis requires both the existing 15-object GUID proof and
ACKs for every original schema fragment. Reports explicitly separate
`schema_transport_delivery_validated` from `schema_application_validated=false`.
ACKs alone cannot prove engine dictionary application, owned world replication,
character control or playable joining. Native run
[39553448548](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39553448548)
passed this new hypothesis on source `67cca6289b3647344c98137a658bdfcaf57593a9`.
Every schema fragment was ACKed and all 15 native service GUIDs matched. All four
packaged render types passed. Binary commit `3774160` published the tested
service (500,736 bytes, SHA-256
`563fa4e677a895014a991c7133a7ad43da223ce8c6ed772e9585b3fdc11c4102`) and worker
(27,980,410 bytes, SHA-256
`8b8cdd7460d490d9714f0f08409955f3f9aa64f8cbfaf3c6faff97f2ea742401`).
A continuous 14.5-second recording validated. Compact evidence is retained in
`server2013/protocol/native-schema-checkpoint.json`.

For a source build, run the descriptor generator before compiling the native
service (the native workflow contains the complete MSVC/icon build commands):

```text
python server2013/protocol/generate_descriptor_header.py --output server2013/build/DescriptorData.generated.hpp
```

Next: exact `0x83` new-instance/property encoding and a server-only StringValue
nonce observed in native Player scene data, then bidirectional updates. Do not
inject expected server data into the client bootstrap.


## First original property replication hypothesis

Read-only analysis of the exact pinned Player indicates compact replication item
IDs: 1..3 use two bits; other IDs use a zero two-bit prefix and four-bit value.
ID 3 selects property changes, followed by a GUID, a ten-bit property dictionary
index and a control bit. The truncated integer follows raw x86 byte order, so
`Instance:Name` ID 404 uses the low byte then two high bits. The string value uses
a per-property cached literal with the already validated Huffman string format.
A six-bit zero terminates the replication-item stream. These are protocol field
hypotheses; no proprietary disassembly or engine implementation is published.

The new original `serviceName` encoder targets only the existing TestService and
uses a fresh 128-bit server-generated random nonce as its name. Client source
only queries native service names; it contains neither the nonce nor a setter.
The new native gate must observe the exact server value in TestService.Name.
This tests the GUID + property-ID + string route through the delivered schema.
It is not the planned StringValue/new-instance world proof and cannot change
`world_replication_implemented` or `game_join_validated`. Native run
[39554013396](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39554013396),
source `6a9997b09fcec52cf7e5f98680f4b7c60dfa4110`, passed: the exact server-only
nonce was observed through the native TestService.Name property. All globals,
schema ACKs, renderer jobs and continuous recording checks also passed. The
workflow published both tested owned executables in `cc2ffbc`; their sizes and
hashes are retained in `native-property-checkpoint.json` and the bundle manifest.
This validates the compact item/GUID/truncated property ID/cache-string route for
one existing service property. It does not validate every property type, new
instances, simulation or playable joining.


## Bounded StringValue reflection observation

The next read-only diagnostic targets only the exact pinned Player's static
StringValue ClassDescriptor and its bounded property vector. It exports API
property names, flags and boolean-type identity, with at most 32 KiB of reads;
it performs no scan, writes, injection or raw-memory export. The separate
reflection workflow reuses the already tested owned EXE without rebuilding it.
The purpose is to resolve new-instance property ordering before implementing
an original StringValue creation message. This observation is research only and
cannot count as a replicated world.

The reflection read succeeded in run 39554682970, reading only 620 bytes. That
job failed later because the reused harness's screenshot cleanup lacked Pillow;
run 39554828808 added that dependency and passed both reflection and the existing
property checkpoint, without rebuilding the binaries. Sanitized field evidence
is retained in `server2013/protocol/stringvalue-reflection.json`.

Replicated fields in class reflection order are Archivable (boolean), Name
(string), RobloxLocked (boolean), Value (string). The exact reader consumes its
string-like group first (Name, Value), then ordinary types (Archivable,
RobloxLocked), then a separate parent GUID. The original new-instance encoder
uses ID2 (two bits), cached scope/index, raw x86 nine-bit class ID250, one lifetime
flag (meaning unclaimed), the four fields with the proper default/cache framing,
parent GUID and six-bit terminator. Name cache slot2 follows the earlier service
name in slot1; the StringValue.Value cache starts at slot1.

The new native hypothesis requires a fresh server-created StringValue named
RccServerToken under native Workspace. Its 128-bit nonce and GUID index are
created only by the C++ server. Client Lua only finds the existing object and
logs its actual class/name/value/GetDebugId(0); it never constructs that object,
sets its value or receives expected values in bootstrap source. Publication
requires all those observed fields to match server evidence. A successful
single-instance proof still leaves geometry, character admission, simulation,
bidirectional updates and full game joining unimplemented.

Native run
[39555242394](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39555242394),
source `e57a9176e8986527078369d6721c72ba3efd7b00`, passed this exact new-instance
proof. Native Player found Workspace.RccServerToken as a StringValue, observed
the exact server-only nonce and matched its GetDebugId(0) to the original
server-generated GUID index. Parent, class, name, value and GUID were required;
missing or corrupted observations fail the gate. All 15 service identities,
schema ACKs, TestService.Name, same-process UDP ownership, all four render jobs
and continuous recording also passed. Studio was absent.

Binary commit `5be1102` published the tested owned service (509,440 bytes,
SHA-256 `f981dbae8bbf625f7da1610ac4af73c4e1af7b6704b1c9b2ef672301309c560f`)
and worker (27,979,568 bytes, SHA-256
`8d697fe92a92dcaadeb663ff104fa1c49d5dcf282cc7d0d191a98b92952b37c4`).
The continuous recording is 14.5 seconds / 174 frames, SHA-256
`507ec3680741dc3700595bf748f3fbd5f4e8477f08ca8be19a62d625b3e8b254`.
This remains an invisible StringValue/object-data milestone, not a playable-game
video. Compact evidence: `server2013/protocol/native-instance-checkpoint.json`.
The parallel reference schema regression run 39555242331 passed.

The manifest now records `new_instance_replication_validated=true` separately
from `playable_world_validated=false`, `world_replication_implemented=false` and
`game_join_validated=false`. The native publication gate requires the original
new-instance proof in addition to every preceding checkpoint. The sender is
currently a bounded one-shot fixture, not a general world serializer: its Name
and Value cache slot assignments depend on the documented message sequence.

Next: server updates of the owned StringValue, a client-derived acknowledgement
returned through actual Roblox replication, and native server decoding of that
return; then owned geometry and character control. Do not use HTTP/log output
alone as proof of a bidirectional Roblox property update. Incoming application
messages currently remain metadata; no client-to-server property decoder exists.
Exact-build read-only leads indicate compact ID5/6 ping items contain one bit,
a 64-bit integer and a 32-bit integer. Client property writer emits a control bit
before the value; later-client assumptions about extra version fields must be
verified for this build. Retain actual incoming frame bit lengths and per-direction
scope/property caches before implementing a general decoder.
