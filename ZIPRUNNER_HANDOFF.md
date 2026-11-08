# Atrium 0.5.82 — source-only registry and Assets consumer

Base: 0.5.81 repaired source. The 0.5.81 complete Python/Node/Checkers regression evidence is historical; run 0.5.82 itself before claiming QA.

* Offline TaviX approved-index projection; classification `game` only, hash-pin required, no installer, trust/auth or executable URLs. Build artifact `web/tavix-games.json` defaults to a healthy empty catalog pending approved source.
* Discover reads TaviX marketplace snapshot and only offers Play through Tavi's installed-game capability for exact installed versions; Tavi/X approval stays external.
* Byte-identical canonical Tavi Assets SDK 0.1.11 client and optional session-bound host adapter, no new user permissions or entitlement engine.
* Social 0.3.150 source routes checked as wire-compatible with 0.5.81. Life's authoritative seat/match APIs remain unmounted.
* All local private state and `ziprunner.config.json`, `.env`, database, secrets and generated outputs excluded by source packaging; no release/approval granted.

Read `docs/ATRIUM_TAVIX_MARKETPLACE_ASSETS_082.adoc` for operator tests and gating.
