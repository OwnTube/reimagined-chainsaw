# Pinned Studio Windows probes

Experimental tests for Roblox Studio 0.743.0.7431133. This is not a completed RCCService replacement. No game hosting or client joining is implemented.

The Windows workflow downloads vendor packages directly from Roblox, verifies the pinned manifests and executable hash, builds the upstream Luau compiler smoke test, and attempts Studio API dumping and viewport capture. Native Studio behavior is unverified until the workflow produces valid output. Permission or sign-in requirements may cause a recorded failure.

Only test source and configuration are committed. Roblox executables, proprietary decompiler output, account credentials, and cookies are not included. Upstream pattern-data and Luau licenses are included.

The workflow runs on pushes to rcc2026-ci and can be manually dispatched. Results and failures are retained as a CI artifact for seven days.
