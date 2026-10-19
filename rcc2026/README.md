# Pinned Studio Windows probes

Experimental tests for Roblox Studio 0.743.0.7431133. This is not a completed RCCService replacement. No game hosting or client joining is implemented.

The Windows workflow downloads vendor packages directly from Roblox, verifies the pinned manifests and executable hash, builds the upstream Luau compiler smoke test, and attempts Studio API dumping and viewport capture. Native Studio behavior is unverified until the workflow produces valid output. Permission or sign-in requirements may cause a recorded failure.

Only test source and configuration are committed. Roblox executables, proprietary decompiler output, account credentials, and cookies are not included. Upstream pattern-data and Luau licenses are included.

The workflow runs on pushes to rcc2026-ci and can be manually dispatched. Results and failures are retained as a CI artifact for seven days.

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
