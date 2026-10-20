# Native 2013 local hosting and joining

This research uses two separate, unmodified copies of the pinned November
2013 Studio deployment. It does not build The Funnel Method's 2016 patches
or assume that their December 2013L protocol target matches this build.

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

## Verified checkpoint — 2026-10-20

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

### Standalone Player remains blocked

In the same run, the separately pinned Player was tested with actual local
negotiation/join URLs and a runtime-only AppSettings BaseUrl override. Its
executable SHA-256 still matches the original pin. Its report has
`passed = false`, `standalone_player_join_validated = false`,
`join_script_requested = false`, and `backend_requests = []`.
Its own native log reports a trust-check failure for the local
`/Login/Negotiate.ashx` URL and `invalid request 5` while loading the local
`/game/studio.ashx` URL. The backend was not reached; this does not test the
Player's network protocol compatibility with the Studio host. A supported
standalone bootstrap/trust configuration is still missing. No account
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

The probe's `passed` field requires hosting and bidirectional replication;
character locomotion is reported separately. A screenshot alone never proves
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

The current evidence establishes Studio admission, world replication, a
complete application-event round trip, and character walking on both peers
in one run. The standalone Player remains blocked at bootstrap, as detailed
above; configuring its copied BaseUrl alone did not resolve native URL trust.

The standalone step is explicitly experimental and uses `continue-on-error`.
A successful overall workflow does not establish a successful Player join:
read `player-output/result.json`, especially `passed`,
`standalone_player_join_validated`, `join_script_requested`, and the requested
backend paths. The main two-Studio result is `output/result.json`.

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
