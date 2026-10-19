# Reference study

## Xitter

Sources inspected:

- https://github.com/Xittered/xitter/blob/main/README.md
- https://github.com/Xittered/xitter/blob/main/scripts/fetch-client.ts
- https://github.com/Xittered/xitter/blob/main/src/server.ts
- https://github.com/Xittered/xitter/blob/main/compose.yaml

The README describes a pinned official X client served against a Postgres-backed API. `fetch-client.ts` extracts initial state, runtime, entry scripts, and feature switches. It can fetch a guest TweetDeck page or use a separately supplied local capture. `server.ts` serves cached/patched assets, routes native client calls, limits bodies, restricts outgoing client connections with CSP, and retains unknown-call counts for debugging. Client files are excluded from source distribution. The design lesson is that matching a client requires both bootstrap state and API responses, not simply redirecting a hostname.

## Meowcord

Sources inspected:

- https://github.com/meowcorded/meowcord/blob/main/README.md
- https://github.com/meowcorded/meowcord/blob/main/package.json
- https://github.com/meowcorded/meowcord/blob/main/scripts/client.js
- https://github.com/meowcorded/meowcord/blob/main/src/api/Server.ts

The README describes a patched official Discord web client with Equicord and a self-hosted backend inherited from Spacebar. The client capture script recursively discovers static assets and module chunks, patches runtime URLs, and records missing files. The API mounts versioned routes with auth, limits, and structured failures. Its inherited API/entity implementation and gateway are substantial: reusing its architectural idea is much less work than matching its accumulated feature coverage.

## Applying that pattern to YouTube

Observed directly from the downloaded signed-out desktop page:

- `ytInitialData` bootstraps the home renderer tree.
- `ytcfg` includes environment/client configuration and player asset locations.
- Assets include `/s/desktop/<build>/`, `/s/player/<build>/`, and newer `/s/_/ytmainappweb/_/js/` and `/ss/` bundles. Restricting discovery to filenames ending in `.js` misses the main application.
- The initial capture missed the modern main bundle. Capture rules were corrected; the second pin obtained 23 files with no reported failures, including the roughly 10.9 MB main JavaScript bundle and 3.2 MB main stylesheet.

The first compatibility implementation constructs renderer trees for home/search/next and a progressive local stream in `player`. Those are independently authored candidate contracts. HTTP tests validate their local consistency; they do **not** establish compatibility with every current official renderer. Browser evidence is the next required source of truth.

## REA

Source: https://github.com/morluto/rea/blob/main/README.md and package.json (version 6.7.0).

The supported one-off CLI invocation is:

```sh
npx --yes --package=rea-agents@6.7.0 rea analyze-javascript-application /absolute/path/to/data/client/assets --json
```

This does not modify agent configuration. It was attempted against the local captured assets. REA reached JavaScript artifact discovery, then failed because this container's procps process inspection cannot resolve itself. This is an environment blocker, not evidence of an analysis finding. A CI step repeats it on a standard Ubuntu runner.

No upstream implementation code was copied into this project. The independent interface is a working path for exercising local accounts/videos while compatibility investigation proceeds.
