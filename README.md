# RCC2013

Experimental renderer work using archived November 2013 Roblox Player and Studio.

The complete deployments are downloaded directly from the user's supplied Roblonium archive, with pinned ZIP and executable SHA-256 digests in [packages.json](rcc2013/packages.json). The Studio PE reports version **2013.11.25.2**, a 2013-11-26 build timestamp, and x86 architecture; Player reports **0.130.0.40915**, also x86. These are archive-supplied files; their hashes identify the tested bytes, not independently verified vendor provenance.

Only our source and configuration are published here. The 2026 project remains preserved on its separate `rcc2026-ci` branch. No rendering or RCC compatibility has been validated yet for this new target.

## First native hypothesis

This Studio image contains the `-ide`, `-fileLocation`, and `-script` arguments and ships plain Lua built-in plugins. The first bounded Windows test opens an owned empty place and adds one independently owned plugin. That plugin creates a floor and red/green/blue blocks, positions the camera, and prints a random marker after its scene setup succeeds. Its source uses 2013-era Lua and engine APIs.

The probe captures the desktop, owned process window metadata, and redacted native logs. A desktop screenshot alone is not classified as a validated engine render. The executable is not patched. The next implementation step depends on actual scene/script evidence from this run.

## References

- [Daniel-176's reverse-engineering wiki](https://github.com/Daniel-176/Roblox-Reverse-Engineering-Wiki), inspected revision `a7a6802ed56263dfb8c97e199b2c65bce1db33a6`.
- [Roblonium archive](https://archive.roblonium.com/Client/Windows/TODO/ROBLOX%20clients/), providing both complete deployment ZIPs.
- [REA](https://github.com/morluto/rea), used locally as `rea-agents@6.7.0` for independent read-only PE resource inspection. It identified the Studio image as x86 and matched the executable digest above. No engine code was executed by that inspection.
