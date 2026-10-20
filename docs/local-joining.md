# Native 2013 local hosting and joining

The current probe hosts in the pinned November 2013 Studio and joins using
the separately pinned **RobloxPlayerBeta.exe**. The earlier two-Studio test
below is retained as a control, not presented as standalone Player evidence.
This does not build The Funnel Method's 2016 patches
or assume that their December 2013L protocol target matches this build.

## Actual standalone Player checkpoint — 2026-10-20

[Run 39424173794](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39424173794),
source `df9766ab74d017c56e9b626f47f77aa972612b5c`, reports true for native
hosting, standalone Player admission, bidirectional replication, and character
movement on both peers. The client receives an independent random server
token, observes the server beacon move, and replies through RemoteEvent.
Both processes' native local-RCC flags are 1 and their handshake-value hashes
match. The probe reads only those pinned fields from its own child processes;
it exports neither raw handshake values nor process memory.

The important distinction is the native `DebugLocalRccServerConnection`
setting **on both peers plus numeric `127.0.0.1` in PlayerConnect**. Literal
`localhost` follows another native branch and left Player on its normal
handshake value despite the flag. It failed with native rejection 24. The
numeric branch selects the engine's own local-RCC handshake. Neither a
protocol-check instruction patch nor disabled network-version/security flags
is used in the working profile.

The disposable Player is configured for `rcc13.test`, mapped to loopback on
the test runner, and a newly generated RSA public key. `local_player.py`
requires the exact original SHA-256 and makes 21 equal-length edits entirely
within `.rdata`; it refuses executable sections and unknown builds. The local
backend signs owned bootstrap source using the corresponding in-memory key.
Native execution of the random bootstrap marker proves that the Player accepts
these signatures. Studio retains its original executable digest. No modified
executables or private keys enter the source tree or evidence artifacts.

```text
python -m pip install Pillow cryptography
python hosting2013/windows_join_probe.py --studio rcc2013/vendor/studio/RobloxStudioBeta.exe --player rcc2013/vendor/player/RobloxPlayerBeta.exe --player-profile local-signed --host-profile local-player --output hosting2013/player-output --timeout 60
```

This profile changes the hosts file only in the disposable Windows runner and
binds its backend on loopback port 80. The workflow temporarily stops a running
default IIS listener, then restores it. Cleanup removes the exact owned hosts
entry and runtime deployments. The source is a bounded development probe,
not an installer or a persistent publicly accessible game service.

### Archived interface checkpoint — 2026-10-20

[Run 39427990205](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39427990205),
source `a864aa917b962ebdf0cda30f60892a47f242a49c`, reports true for both the
network/character checks and `core_gui_validated`. The native Player contains
`GameMainMenu`, `ChatFrame`, `PlayerListScreen`, and `CurrentLoadout` together.
Its actual window capture was visually inspected. This proves that the
archived scripts build their interface; it does not prove every control,
chat delivery, inventory action, or texture works.

`core_assets.json` pins 19 archived scripts/libraries, URLs, modification
metadata, and SHA-256. Archive timestamps do not prove a precise live rollout.
The default `--core-loader compat` embeds those verified runtime sources in
the signed local bootstrap, supplies isolated script environments and the
four original LoadLibrary modules, and starts their native Lua threads.
The original archived sources construct the GUI; the repository contains
orchestration, not copies of those sources. Sources and runtime deployments
remain outside uploaded evidence and are deleted during cleanup.

The experimental `--core-loader native` route fetches child CoreScript URLs,
but their execution has not been established. The successful compatibility
loader is distinct from that unresolved LinkedSource path. Lua 5.1 execution
must stay outside a `pcall` boundary so the original scripts can yield.

`core_images.json` pins 22 decoded public PNG assets. Fifteen requested image
IDs were unavailable and are recorded explicitly. Bundled textures remain
local references; missing network assets are not silently replaced. Full
visual fidelity is therefore unverified. Guest chat permissions and inventory
behavior remain separate checks from the existence of their containers.

### Keyboard and inventory checkpoint — 2026-10-20

[Run 39430884973](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39430884973),
source `91f2a648f9496e04ae9c4309f34862509c152732`, passed the mandatory
standalone Player test with **all network, character movement, archived GUI,
and keyboard-movement fields true**. A bounded OS scancode D press reached
the native legacy Mouse.KeyDown callback. Client and Studio independently
observed more than two studs of horizontal character movement after that
input. The input observer does not move the character; native
HumanoidController handles the key. Automatic MoveTo had already been stopped.
A click inside the owned game window and a two-second acquisition interval
precede the key; foreground PID ownership is checked before delivery.

The older UserInputService observer incorrectly assumed a modern KeyCode enum;
this build logs numeric key code 100 for D. The working observer uses its
legacy key string API. Windows accepts both key-down and key-up, and the
Player shares the active console session. Earlier failed input probes are not
a successful keyboard result and are superseded by this native checkpoint.

The native LocalBackpack and HumanoidController were present. Correcting the
compatibility loader's script object names to the archived scripts' expected
`CoreScripts/BackpackScripts/...` names unblocked their dependencies. The
actual Player capture now shows the owned tool's first hotbar slot. Tool
equipping and inventory-window interaction are still untested. Local guest
chat mode is configured to TextAndMenu; sending/receiving chat is untested.

CI requires standalone network/character evidence and all four native GUI
containers. `--test-input` additionally requires keyboard-driven movement on
both peers. The report keeps `network_test_passed`, `core_gui_validated`, and
`keyboard_movement_validated` separate; a screenshot alone proves none of them.

Multiple players, external connections, accounts, persistence, chat delivery,
and arbitrary uploaded places remain unverified.

### Research tools

REA 6.7.0's built-in PE resource parser independently identified both pinned
x86 binaries and their hashes. Its native-provider search was blocked by this
Linux environment's process-ownership inspection (`ps` failed); no ownership
guard was bypassed. Read-only PE data inspection and disassembly were used
locally to identify the specific native flag and address branches. Engine
disassembly/decompiled code is not published.

On native Windows with a visible desktop, after restoring `rcc2013/vendor`:

```text
python -m pip install Pillow
python hosting2013/windows_join_probe.py --studio rcc2013/vendor/studio/RobloxStudioBeta.exe
```

The bounded probe creates a small owned scene on the host, launches a second
Studio process with an empty place, and connects it to `localhost`. It uses
the exact build's older `-ide`, `-testMode`, `-fileLocation`, and `-script`
launch options. The literal hostname matters in this engine: its local-test
path is distinct from connecting to a numeric IP address.
The server references its locally bundled character model. Runtime copies,
including all proprietary engine assets, stay outside the evidence directory
and are removed after the experiment. Only owned scripts, reports, redacted
logs, and diagnostic screenshots are uploaded.

## Historical two-Studio control — 2026-10-20

[Native run 39348329677](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39348329677),
source `b09758b8aab8bb4145a5805459fef70072a32007`, passed both Windows control
tests and the mandatory two-Studio join probe. In the same execution, all of
`server_hosting_validated`, `client_join_validated`,
`replicated_movement_validated`, and
`client_character_movement_validated` are **true**.

The host PID was 2552, the separate client PID 1640, and the verified UDP port
54194. The host admitted local test player -1; the client accepted the
connection and received a random token that was absent from its source.
The client observed the host beacon at x=6 and x=-6, then the host received
its RemoteEvent reply carrying the correct token and observations. A client
Humanoid.MoveTo request moved the owned character, with x displacement past
2 observed on both peers. Neither process was patched.

The key compatibility fixes are `PlayerConnect`'s literal `localhost` test
path, explicit `ClientReplicator:RequestCharacter()`, the 2013 MoveTo method's
required second Part argument, and `Players.CharacterAutoLoads = false` to
retain the owned character during the handshake. Native events are retained
cumulatively across engine worker-thread log files.

Both peer viewports were captured and visually inspected. The client image
is 640 × 480, showing the character on the owned floor beside the red beacon.
Its PNG SHA-256 is
`b716b30ad809eed14b8c065455e505fa4f69445eea9c4552b703dbd082cdcb5d`.
The image comes from the joined game's native client viewport.
The bounded test terminates both peers afterward; it does not leave a public
server running. Keyboard input, multiple simultaneous players, external
connections, arbitrary uploaded places, and persistent account services have
not been validated by this test.

### Historical stock Player baseline: URL trust blocked startup

In the same run, the separately pinned Player was tested with actual local
negotiation/join URLs and a runtime-only AppSettings BaseUrl override. Its
executable SHA-256 still matches the original pin. Its report has
`passed = false`, `standalone_player_join_validated = false`,
`join_script_requested = false`, and `backend_requests = []`.
Its own native log reports a trust-check failure for the local
`/Login/Negotiate.ashx` URL and `invalid request 5` while loading the local
`/game/studio.ashx` URL. The backend was not reached; this does not test the
Player's network protocol compatibility with the Studio host. That historical baseline lacks the local bootstrap/trust configuration
used by the later successful standalone checkpoint above. No account
credentials or proprietary modified executables are requested or published.

## Experimental standalone command

An additional experimental mode launches the separately pinned standalone
Player against an owned HTTP endpoint bound to the loopback interface:

```text
python hosting2013/windows_join_probe.py --studio rcc2013/vendor/studio/RobloxStudioBeta.exe --player rcc2013/vendor/player/RobloxPlayerBeta.exe --output hosting2013/player-output --timeout 45
```

The backend serves the owned client bootstrap at `/game/join.ashx`, a minimal
local `/Login/Negotiate.ashx` response, and
records requested paths without headers or query values. Its script contains
no server challenge token. The stock Player is launched using the supplied
wiki's older `-t/-a/-j` profile, with actual loopback URLs instead of the wiki's
`-a 0` placeholder. Only the runtime copy's AppSettings BaseUrl is redirected
to that backend. Engine bytes and trust keys are unchanged; no Roblox account
credentials are supplied. This mode's result is independent
of the two-Studio test and must not be described as working without its own
native admission and replication evidence.

## Evidence requirements

The report separates these outcomes:

| Field | Required engine/OS observations |
| --- | --- |
| `server_hosting_validated` | Native server-ready marker and matching UDP port owned by that host PID |
| `client_join_validated` | Server PlayerAdded, client ConnectionAccepted, and receipt of a random server-only token |
| `replicated_movement_validated` | Client observes the host's beacon at two positions, then the host receives its RemoteEvent reply with the correct server token |
| `client_character_movement_validated` | A client Humanoid move request produces character displacement observed on both peers |
| `standalone_player_join_validated` | Reserved for a separate RobloxPlayerBeta experiment; the two-Studio test cannot establish it |

The current probe's `passed` field requires hosting, bidirectional replication,
and character locomotion. The configured Player also requires archived GUI
containers, and `--test-input` adds the separate keyboard-movement requirement. A screenshot alone never proves
a successful join. Both processes are terminated at the end of the test.
This is a local development experiment, not a public service or account backend.

## Initial launch findings

All experiments use Studio SHA-256
`f404880ab8b4c313b9b7a3c8c599afafcdbf4e8fe4ae22d9852954690364c311`.

| Run | Hypothesis | Observed result |
| --- | --- | --- |
| [39325233452](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39325233452) | Owned plugin can initialize the server directly | Native Lua failed before server startup; the engine returned an empty error string. No hosting or joining claim. |
| [39325497392](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39325497392) | Establish server role before server-only events and identify the failing stage | Failure isolated to `SetIsPlayerAuthenticationRequired(false)`; UDP startup was not reached. |
| [39325682033](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39325682033) | Use the build's native command-line script context | Bootstrap executed, but the same optional authentication-setting call failed. |
| [39325869121](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39325869121) | Treat the unsupported authentication setter as optional | Native server startup and same-PID UDP binding passed. Client Lua failed to parse because a broad placeholder replacement changed a log label. |
| [39346422671](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39346422671) | Fix placeholders and guard server-only challenge independence | Syntax/regression checks passed. Host startup and UDP binding passed. Client executed but PlayerConnect returned an empty error before acceptance. |
| [39346587016](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39346587016) | Enable the exact build's test-mode flag | Host startup and UDP binding passed; connecting to the numeric loopback IP still failed in PlayerConnect. |
| [39346770626](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39346770626) | Use the engine's explicit localhost path | Host admitted local player -1, client accepted the connection and received the server-only token. The movement callback then failed because this build requires Humanoid.MoveTo's second Part argument; the engine disconnected that callback. |
| [39347157773](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39347157773) | Supply MoveTo's required Part and capture the client first | Host and client both observed character movement beyond x=2. The client observed the beacon change from x=6 to x=-6. Admission and token replication passed, but the server's RemoteEvent reply marker was not observed; the strict probe remained failed. Both peer viewports were captured. |
| [39347579480](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39347579480) | Complete the character request and retain events across thread logs | Host emitted its startup marker, but PowerShell's UDP ownership query timed out after 15 seconds. The client phase was not reached, so this run does not test the new handshake. |
| [39347870867](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39347870867) | Direct native UDP ownership query, explicit character request, cumulative native events, and independent standalone probe | Both native control tests passed. Studio admission, token, beacon movement, and server receipt of the RemoteEvent reply passed. Default character loading replaced the owned model, so movement was not confirmed on both peers in this run. The separate Player probe did not fetch the local join script; its log reports a trust failure for the wiki's `0?suggest=0` negotiation URL. |
| [39348329677](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39348329677) | Preserve the owned character and configure a real local Player backend | All two-Studio join, replication, reply, and walking fields passed together. The separate Player remained blocked before any backend request, with native URL-trust errors. |

Those historical experiments established the two-Studio control. The stock
Player remained blocked at bootstrap; changing BaseUrl alone did not resolve
URL trust. The later locally configured Player checkpoint above supersedes
that limitation. The current workflow has a mandatory standalone Player step
and does not use `continue-on-error`. Read `player-output/result.json` for
the separate network, interface, and input outcomes.

UDP ownership is now queried directly through Windows GetExtendedUdpTable.
A Windows test binds a known Python UDP socket and requires the query to match
both its PID and port, rejecting PID zero and port zero. This guards the port
byte order and table parsing independently of Studio. The relevant native
structures are documented by
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/udpmib/ns-udpmib-mib_udprow_owner_pid).

The supplied wiki's [gameserver example](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki/blob/a7a6802ed56263dfb8c97e199b2c65bce1db33a6/Research/gameserver.txt)
uses NetworkServer.Start and RunService.Run. The exact pinned Studio executable
also contains NetworkClient.PlayerConnect, its five legacy argument names,
and `-testMode`. These observations support experiments; they do not by
themselves establish compatibility or successful execution.

REA `rea-agents@6.7.0 inspect-pe-resources` independently identified the downloaded
standalone Player as x86 and matched executable SHA-256
`30502f062f428d3d808e7119ddb991865c91eb4beeed9f2c6b983198c007ea41`.
That read-only resource inspection does not establish a Player connection.
