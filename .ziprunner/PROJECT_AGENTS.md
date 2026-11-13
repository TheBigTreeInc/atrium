# Atrium — project-scoped agent context (proposal, 2026-11-12)

Project key: `atrium` · Canonical UUID: **unverified** · Owner: Atrium source project · Git: `https://github.com/TheBigTreeInc/atrium` · branch: `main` (observed). Source candidate: **0.5.84** based on Library 0.5.83; production and operator acceptance are separate.

## Bootstrap
Read `/ECOSYSTEM.md`, `/registry/INDEX.md`, `/registry/catalog.json`, applicable `/schematics/_defaults/` and this project's exact versioned `PROJECT.md`/`memory.json`; check status and source hashes. In the actual repository read `AGENTS.md`, `INSTRUCT.md`, `DESIGN.adoc`, `PROJECT_PLAN.adoc`, `ENGINEERING_STANDARD.adoc`, `CODING.md`, `TESTING.md`, `project.zr`, Workboard and QA. If a reference is absent or proposal-only, mark it unverified; do not fill gaps by guessing.

## Ownership
Atrium owns game presentation/catalog projection, matchmaking/lobbies, game coordination and its own schemas, tests, spec and application code. Tavi owns users/friends/invitations/host capabilities; TaviX owns packages, approval, installs/launch; Tavi Assets owns asset catalogs, grants/entitlements; game services (including Life) own authoritative seats, moves, sessions and persistent rules state. LoopRD provides portable services; do not hardcode deployment endpoints in `atriumd.yaml` or replace individual game authority.

## Non-negotiable rules
No second Atrium package installer, unapproved catalog trust, forged Social identity, ungated service routing, speculative runtime activation, unapproved Game/Assets privileges or new public endpoints in a documentation-only pass. Keep 1.0.4 official extension immutable. Preserve protected files (`.git`, `.env`, keys, operator configs, DB, uploads, logs, build outputs, runtime and private state). Never delete/overwrite Library history without byte verification and explicit approval.

## Build and handoff
Run focused source tests first; then `python tools/check_specs.py`, `python -m unittest discover -s tests -v`, `npm test`, `npm run build`, `npm run verify`, `python tools/checkers_group_qa.py`, `python tools/package_zip.py` (plus repository's additional generated-spec and actual pinned-validator checks). Tests run in a managed Python environment on Windows. Inspect source manifest, verification plan and `.ziprunner-workboard-update.json`; evidence must distinguish locally passed tests, Windows run, operator acceptance and release. Source Git checkout remains authoritative. No automatic commit, push, stage, publish, deploy or tag.

## Continuation priority
1. Verify this 0.5.84 source candidate in Windows ZipRunner against a complete source checkout; reconcile exact Git revision and Library records.
2. Connect approved Social + Life authorities and prove two authenticated Tavi clients join/resume/finish a match; keep room admission game-authoritative.
3. Operator-approve an exact TaviX index before populating Discover; separately approve Tavi/Assets capability grants.
4. Request central registry catalog publication from its steward; publish own mirrors only with hash-proven source.

## Market Grove v0.5.84 owner boundary
Atrium owns the independent `market-grove` LoopRD child, player order book, reference import, simulated traders and practice accounting. No Tavi Gold is created or transferred. Social/Tavi Wallet must separately authorize service-only earnable Gold reservation, release, seller credit and reconciliation. Preserve historic 0.5.83 registry-memory provenance. TaviX is unchanged.
