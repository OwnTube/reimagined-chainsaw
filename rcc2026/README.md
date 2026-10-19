# Pinned Studio Windows probes

Experimental tests for Roblox Studio 0.743.0.7431133. This is not a completed RCCService replacement. No game hosting or client joining is implemented.

The Windows workflow downloads vendor packages directly from Roblox, verifies the pinned manifests and executable hash, builds the upstream Luau compiler smoke test, and runs bounded native engine probes. Native API dumping is validated. Script execution, rendering, and game hosting are still experimental; the exact limitations and evidence are recorded below.

Only test source and configuration are committed. Roblox executables, proprietary decompiler output, account credentials, and cookies are not included. Upstream pattern-data and Luau licenses are included.

The workflow runs static/component checks on pushes to rcc2026-ci and can be manually dispatched. Native Studio execution requires an explicit manual input (`api`, `script`, `render`, or `server`) for a new hypothesis; static-only changes do not launch Studio. Results and failures are retained as a CI artifact for seven days.

## First Windows run: 2026-10-19

[Run 39178876195](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39178876195), commit `aa3e52d8d57e005d5424560bfd209f9e415bca80`, ran on `windows-2022`:

- Official pinned Studio assembly and identity verification passed.
- All six Python evidence-processing tests passed.
- Static executable inspection completed.
- The pinned Luau compiler/VM component built with MSVC and passed its CTest round-trip test.
- The native Studio API dump timed out after 120 seconds without an API JSON file.
- Native Studio RunScript timed out after 180 seconds without script output or a PNG.
- Both redirected Studio process logs were empty. The startup failure cause is unknown.

The API dump step uses `continue-on-error`, so its displayed step conclusion can be success even when its result JSON reports a timeout. The overall run failed at RunScript. No native engine render, game hosting, or client join has been validated. The compiler test uses the upstream standalone VM; it does not prove Roblox wire-bytecode compatibility.

The failure evidence is available in the run's `studio-743-windows-evidence` artifact until 2026-10-26. Desktop screenshots and additional native Studio logs were not collected in the first run.

The user subsequently approved collecting and publishing startup screenshots and Studio logs from the disposable Windows runner. The next probe captures the desktop, titles of windows owned by its Studio process, and the ten most recent native Studio logs before terminating a timed-out process. Desktop diagnostics are labeled separately and never count as engine-render evidence. No account sign-in is performed.

## Startup diagnosis: second Windows run

[Run 39179760987](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39179760987) captured the same modal error for API dumping and RunScript: "This application failed to start because no Qt platform plugin could be initialized." No native Studio log files were found in the normal log directory. Studio therefore failed before reaching either engine probe.

The verified deployment includes `Qt5/platforms/qwindows.dll`, but the assembler did not configure Qt's plugin search path. The fix generates `qt.conf` with `Plugins=Qt5`, sets per-process Qt plugin paths to the bundled directory, and enables Qt plugin diagnostics. This follows [Qt's deployment configuration](https://doc.qt.io/qt-6/qt-conf.html). The third native run below validates the fix. It does not change the Studio executable or its verified assets.

## Native engine progress: third Windows run

[Run 39180408120](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39180408120) confirms the Qt startup fix: `--fullApi` exited with code zero and produced a valid JSON API dump containing **943 classes**. The RunScript attempt reached Studio's login screen and timed out there. Its native logs record Direct3D 11 initialization using Microsoft Basic Render Driver. That establishes graphics initialization, not a successful viewport render.

Push runs now test a separate, bounded `StartServer` launch against an owned, generated local `.rbxlx` place. Its script emits a random marker with server/runtime checks. The probe also checks whether that same Studio process binds the requested UDP port. This is an experiment to determine whether local test-server startup can run without an account; it does not modify authentication. Player compatibility, successful client joining, and rendering remain unvalidated even if these checks pass. The known login-blocked RunScript attempt is retained for manual dispatch rather than repeated on every push.

## Local-server result and next investigation

[Run 39180943668](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39180943668) again validated native API dumping (943 classes, exit zero). The local-server attempt reached the login screen and emitted no server-script marker. Crucially, its native log also reported **`Invalid Launch Intent! Too many arguments provided`** before recording the intent as `StartServer`. This is not a clean test of whether a correctly formed server launch requires authentication.

Next, inspect this exact build's launch-intent parser and reconcile the combination of `StartServer`, `localPlaceFile`, and the legacy test-server flags. Do not repeat the same invalid command. Only launch a new native test when its arguments follow a concrete new hypothesis. The UDP check was not reached, so the recorded `null` UDP field means untested, not evidence that no socket existed. Rendering, server hosting, and client joining remain unvalidated.

The generated place is independently owned test source. A `.gitignore` excludes downloaded Studio/Luau packages, build outputs, runtime evidence, and Python caches from source commits.

## Launch-intent investigation: first continuation

Read-only analysis of the exact verified build identifies an unconsumed-argument check before value validation. The build's server launch builder emits `localProjectFile`, place/universe/creator metadata, port, and test-player count; `localPlaceFile` appears in the file-editing branch instead. This suggests the earlier command mixed intent-specific options. It is a hypothesis until native validation, not a claim that a `.rbxlx` is a supported project-file format.

The next probe follows that server argument set, removes the old `Console` and `instanceId` additions, and uses zero place/universe/creator metadata with the owned local fixture. It also records process-attributed startup observations: argument rejection, value rejection, the observed server intent, and an unauthenticated login dialog. Another session's API/editor logs cannot establish these facts for the server process. Three new evidence-boundary tests cover those distinctions; all nine Python tests pass locally.

Private decompiler output was used only for analysis and is not committed. Only the probe implementation and summarized observations are published; do not assume transient analysis files survive between work sessions.

## Accepted server intent and current blocker

[Run 39184899151](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39184899151) accepted the revised `StartServer` argument set: the process-attributed log records the server intent with neither argument rejection nor value rejection. Native API dumping again succeeded (943 classes). The owned game script did not run, and the desktop capture shows Studio's newer Quick Sign-In page. Therefore the launch-argument failure is resolved, but this unmodified launch still stops at sign-in. No place-format support, server socket, rendering, or client join has been validated.

The newer login page lacks the older `show login dialog` message. Diagnostics now recognize both surfaces, tested against the captured native logs as well as synthetic boundary cases. Collected text logs redact known authentication fields and URL queries; desktop capture is omitted when the owned process's log identifies an unauthenticated sign-in surface, which can display a live challenge.

The next read-only experiment compares six upstream offline URL-adapter signatures against the exact pinned image. This checks whether those historical patterns can even locate candidates for a local adapter; it does not install hooks, change URL routing, disable authentication, or establish function signatures. Pattern attribution is pinned to the same noobwarrior revision and covered by its included license.

The workflow also invokes the requested REA tool (`rea-agents` pinned to 6.7.0) to record independent PE resource identities, ranges, and hashes. This metadata-only operation does not need a native provider or execute Studio. Its file budget explicitly accommodates the 225 MB executable. The step is bounded and non-blocking so a package/provider failure cannot hide the other test evidence.

At this checkpoint, normal pushes ran static/component/API checks. The known sign-in-blocked server command became opt-in via the manual `server` input rather than repeated on every push. RunScript remained opt-in through manual dispatch. The later chained-unwind checkpoint makes all native execution explicit (see the current workflow description above). A clean static-only CI run is not evidence of server hosting.

## Measured offline-adapter compatibility

[Run 39198802392](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39198802392) passed on Windows: twelve Python tests, both static inventories, the pinned compiler/VM round-trip, native API dumping (943 classes), and independent REA PE-resource inspection. REA and the inventory reported the same expected executable SHA-256. Server and RunScript were deliberately skipped in this run.

| Historical pattern label | Variant 1 hits | Variant 2 hits | Distinct candidate RVAs |
| --- | ---: | ---: | --- |
| `offline.fromComponents` | 0 | 0 | none |
| `offline.trustCheck` | 0 | 0 | none |
| `offline.httpReqNotTrusted` | 1 | 1 | `0x04ddd610` |

The last row is one shared byte-pattern candidate, not two functions and not a validated hook target. These results show why the historical adapter cannot simply be enabled unchanged. Fresh analysis must locate the missing URL-construction and trust-check paths and verify the remaining candidate's identity and ABI before any local adapter is implemented. No hooks or authentication changes were applied.

The durable [summary](evidence/offline-adapter-743-summary.json) contains only artifact identities, candidate locations, and limitations. Raw decompiler output and vendor executables are not included.

Three final capture-boundary tests were added after this Windows run, covering omission before QR generation, Quick Sign-In metadata, and preservation of non-authentication error capture. All fifteen tests pass locally. The final capture-omission refinement has not been rerun against a live sign-in surface; its predicates were replayed against the saved native logs. No identical blocked server launch was repeated.

## Adapter reference analysis

`inspect_adapter_references.py` refuses any executable other than the exact pinned SHA-256. It inventories selected RIP-relative references to four error/log anchors, then direct calls/jumps to their containing unwind ranges and the historical candidate. Each reported reference is checked against a linear instruction decode from its unwind-range start. Four synthetic tests cover signed displacements, truncated operands, and an opcode embedded inside another instruction's immediate. All nineteen Python tests pass locally.

The first local analysis of the verified image found five matching literals, nine instruction-boundary-verified anchor references, and fourteen incoming branch candidates (thirteen boundary-verified; one lacks an unwind range). In particular, the range beginning at `0x04e07b20` references the HTTP request untrusted-error literal and contains a verified direct call to historical candidate `0x04ddd610`. This supports investigating their relationship; it does **not** establish the candidate's identity, complete function extent, calling convention, or suitability for a hook. Four other verified direct calls also target that candidate.

The scanner publishes only locations, literal hashes, and boundary metadata, not instruction bytes or decompiled code. Selected encodings and ASCII anchors are not exhaustive; indirect references are omitted, unwind entries can be fragments, and linear instruction boundaries do not prove reachability. Windows CI now reproduces this inventory. No routing, authentication, or vendor code is modified. Rendering, server hosting, and joining remain unvalidated.

[Windows run 39204315465](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39204315465), source commit `3b682ae0c96390f7beb30c2c078e55b9fb68633b`, passed on 2026-10-19. Its reference report is structurally identical to the local report, preserved in [adapter-references-743.json](evidence/adapter-references-743.json). All nineteen Python tests, REA resource inspection, the compiler/VM check, and native API dumping passed; the API process exited zero with 943 classes. Server and RunScript were intentionally skipped. This is a reproducible static relationship, not engine execution of the candidate or an authentication workaround.

Next analysis should follow the verified call at `0x04e07db9` from the HTTP-error-containing range to `0x04ddd610`, including its outgoing helper at `0x040b1f60` and control flow beyond its short unwind fragment. The other trust-error references in the report are additional investigation locations, not validated trust-check entry points. Establish actual semantics and argument layouts before considering any local-only URL adapter; do not turn these metadata candidates directly into hooks.

## Chained-unwind recovery

`inspect_unwind_groups.py` follows [Microsoft's documented chained-unwind format](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64). It validates the executable hash, resolves primary runtime-function records, groups their explicitly linked secondary fragments, and records selected control-flow locations without emitting code bytes. Selected groups fail closed for malformed trailers, unsupported versions/flags, absent chain records, cycles, and excessive nesting; unsupported or unresolved entries elsewhere are counted in the report. Eight new synthetic tests cover metadata and low-byte observations; all twenty-seven Python tests pass locally.

The exact image contains 411,984 exception-table entries. The first local scan resolved every chain using V1 metadata, with no unsupported entries. The earlier 33-byte candidate range is the primary entry of **five linked fragments totaling 342 bytes** (95 linearly decoded instructions). Its helper at `0x040b1f60` has four linked fragments totaling 164 bytes (47 instructions). This extends analysis beyond the prologue using explicit metadata rather than adjacent-byte guesses; it is not proof of a complete function extent.

The candidate's linked fragment at `0x04ddd73d` references a service-uninitialized error naming `HttpRbxApiService::isHttpCallAllowedToUrl`. This is static evidence connecting the candidate to HTTP URL permission/service initialization, **not proof that it controls Studio sign-in**. Modifying this candidate would not by itself establish accountless startup, rendering, or hosting. Its argument layouts and return semantics remain unvalidated; no hook was installed.

The report distinguishes direct and unresolved indirect edges, verifies internal direct-branch targets against decoded instruction boundaries, and records the error literal's hash rather than its plaintext. Chained membership and linear decoding do not prove reachability, branch feasibility, or complete function identity; exception-handler paths are not followed. Windows CI now reproduces the new analysis with a two-minute limit, without rerunning the unchanged login-blocked server command.

[Run 39209935842](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39209935842), commit `cf270952a50b73b3858f351462abe3d717f57b45`, passed on Windows on 2026-10-19: twenty-five tests, initial unwind-group analysis, REA metadata inspection, compiler/VM round-trip, and native API dumping (exit zero, 943 classes). Subsequent return-byte checks below are a new static hypothesis. Future push runs no longer launch even the already-validated API dump: each native mode requires its own explicit manual input. Requesting API dumping alone no longer also launches the known sign-in-blocked RunScript mode.

### Historical return-type mismatch

The two decoded normal return sequences have nearby explicit assignments of `AL=0` and `AL=1`. All five previously identified, boundary-verified direct callers immediately consume `AL`: four test that byte, and one zero-extends it. The [historical adapter source](https://github.com/noobwarrior-org/noobwarrior/blob/6f999f739b5e11febd270420657f4334979a54aa/Hook/LocalRcc/LocalRcc.cpp) instead declares `not_trusted_fn` as returning `char*` and returns a pointer to a status string from its hook. That pointer-return assumption is inconsistent with the low-byte result use observed in this build. Reusing the old hook would make a caller's result depend on pointer bits, not the pointed-to string.

These observations support a Boolean-like low-byte result, not a complete recovered C++ signature or proof of runtime branch outcomes. The scanner emits only assignment locations/constants and consumer classifications; it does not print the decoded instruction stream. The durable [unwind and result-use report](evidence/unwind-groups-743.json) preserves the exact artifact identity and limitations. No historical hook has been applied.

[Run 39210549660](https://github.com/vibecodeforever/reimagined-chainsaw/actions/runs/39210549660), commit `a21dcb2e78effbb1967650fa98456a9cb20643e1`, passed twenty-seven Windows tests, all static inventories, and the compiler/VM round-trip. Its unwind/result-use JSON is structurally identical to the preserved local report. All three native Studio steps were skipped as intended. **REA timed out after two minutes and produced an empty file**, despite the overall run being green because that step is non-blocking. REA evidence was not validated in this run; do not infer it from the job conclusion.

`record_rea_resources.py` now gives REA a bounded 210-second startup/operation budget inside a four-minute step. It always records `rea-status.json`, and writes resource evidence only after checking a valid JSON result, the exact resource-inspection operation, expected executable digest, and resource-list shape. Empty, error, wrong-operation, and wrong-digest output cannot count as success. This wrapper passed locally against the exact executable; all twenty-nine Python tests pass locally. The non-blocking CI step can still leave a green job on failure, so its explicit `validated` field is authoritative. Native Studio execution remains opt-in.
