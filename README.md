= Atrium v0.5.14 — First playable Checkers preview and clearer storefront

Operator-gated Pages staging only. See docs/P1_064_FIRST_PLAYABLE_GAME.adoc.

After local review and exact-commit GitHub CI, manually run **Publish reviewed Atrium Pages** with `publish_checkers_demo=true` and leave `catalog_url` blank to publish a standalone Checkers local-play preview. The default catalog remains empty. To roll back, dispatch with `publish_checkers_demo=false`. A configured live gateway cannot be overridden by this preview.

Quick local browser smoke: `npm test && npm run build && npm run verify`, then `ATRIUM_PUBLISH_CHECKERS_DEMO=true npm run stage:checkers && npm run verify`. Open the generated `dist/games/checkers/<SHA256>/index.html` to play; this does not publish to GitHub or the Atrium registry. This standalone game does not have Looprd multiplayer or Social login.


= Atrium v0.5.13 — Anonymous live reviewed catalog delivery

Previous passes added operator-scoped publisher HTTPS domain proof (v0.5.12) and an operator-hosted anonymous live catalog gateway (v0.5.13). Both still require separate real HTTPS/operator acceptance. No publisher self-service, developer identity, automatic Looprd game registration or automatic game approval is enabled.

## Atrium v0.5.11 — Windows ZipRunner build repair

This patch fixes the missing httpx import during test discovery and CP1252 decoding failures in AsciiDoc source tests. No gameplay or registry behavior changed.

## Atrium v0.5.11 — Reviewed discovery candidate intake (first runtime pass)

A new operator-scoped `POST/GET /registry/discovery/candidates` stores validated
`atriumd/v1` metadata as a **pending candidate**, never as a published game.
An operator/deployer can submit it after a game Looprd component has activated
using `tools/announce_atriumd.py`; it reads a private API key from a local file
and takes the deployment ID plus immutable source revision as parameters.

**No automatic source reconciliation hook is installed in DAPI yet.** The remote
component remains authoritative for identity, sessions, multiplayer, and game state.
Atrium's SQLite schema advances additively from v2 to v3; back up the current
Atrium DB before live activation. Existing approved releases remain intact.
See `docs/P1_054_DISCOVERY_INTAKE.adoc`.

## Atrium 0.5.11 — portable `atriumd.yaml` discovery sidecar

This pass ships a strict parser and example for an optional `atriumd.yaml` sibling to portable `looprd.yaml`. Looprd source-loader integration and actual automatic Atrium registration require separate backend implementation and are not active yet. See `docs/ATRIUMD_SIDECAR.adoc`.

# Atrium — Games, apps and shared game services

> **P1 / v0.5.11 source candidate.** Looprd is a specification; DAPI is the runtime.
> Tavi remains a separate client of the Social/Atrium services.

**Git repository:** https://github.com/TheBigTreeInc/atrium (the v0.3.0 foundation was imported to main before this pass). **ZipRunner project:** `atrium`.
**DAPI component:** `atrium` (`looprd.yaml`). The nested `modules/` YAML files
are included fragments: one database, one API prefix, one authentication scope.

The repository preserves the earlier source-only prototype: operator-only
registry and Arcade resources, a stateless Checkers evaluator, Staff table policy,
portable AppHost stub, Yahoo game research catalog and tests. These are not a
fully running multiplayer platform; not a public app store and not Social SSO.

## One-time development prerequisite

Python 3.12+ and Node 22+ recommended. Set up a project-local Python environment for source tooling (also performed automatically by ZipRunner):

```sh
python tools/setup_build_env.py
```

## Fast local verification

```sh
python tools/run_python_checks.py
npm test
npm run build
npm run verify
```

`python tools/build_spec.py` regenerates checked-in YAML when canonical Checkers
source changes. This must be reviewed and committed as a normal source change.

## Source ZIP for ZipRunner

```sh
python tools/package_zip.py
```

This builds a deterministic `dist/atrium-0.5.11-ziprunner.zip` including mandatory
`.ziprunner-workboard-update.json`, producer manifest, verified-plan format and
optional hashed `ziprunner.looprd.json`. ZipRunner is the authority that actually
imports the ZIP and records observed build/test status.

## Pinned integration and CI

`.github/workflows/verify.yml` checks out DAPI and ZipRunner-spec at pinned
commits listed in `docs/UPSTREAM_LOCK.json`, runs the official DAPI semantic
validator and a **disposable** DAPI startup/guest-auth smoke, then uses the
published ZipRunner validation CLI on the produced source ZIP. These upstream
checks cannot be claimed passed until the workflow has actually run.

No secrets or operator keys are in this repo. `examples/sources.*.yaml` are only
proposals and must be reviewed before adding to the real DAPI sources list.
Never grant a browser the DAPI management key or an operator database API key.

Architecture: `docs/ARCHITECTURE.adoc` · P0: `docs/P0_DELIVERY.adoc` · Full
roadmap: `docs/ROADMAP.adoc` · Task ID continuity: `docs/TASK_ID_COMPATIBILITY.adoc`.

## P1 Registry — v0.4.0

This update adds operator-only publisher attestation, validated manifest submission,
immutable approved release history, version monotonicity, disabling and a read-only
**authenticated** catalog at `/looprd/atrium/v1/registry/catalog`. Its generated
registry handler source comes from `src/catalog.py` and `src/registry_runtime.py`.
The event log uses DAPI's durable transactional events; the database schema
advances from 1 to 2 by adding three tables. No anonymous catalog, independently
authenticated developer submission, verified asset-byte retrieval, Social SSO or
Tavi dynamic injection is claimed in this first controlled stage.

Review `DESIGN.adoc`, `PROJECT_PLAN.adoc`, `docs/P1_REGISTRY.adoc`,
`openapi.yaml` and `schemas/atrium-app-v1.schema.json` before activation.
**Back up an existing Atrium database and rehearse the migration.**

## v0.4.1 public registry snapshot

See `docs/P1_PUBLIC_CATALOG.adoc` for offline asset-byte verification, read-only SQLite snapshot export and operator-controlled static publication. The authenticated DAPI API is not anonymous. Publisher identity is still operator-attested; remote domain ownership verification remains pending.

## v0.4.2 Windows ZipRunner build repair

After a reported 0.4.1 build failure caused by missing `sqlalchemy` in host Python 3.13, the trusted build recipe now creates a protected `.venv` and runs all Python source checks inside it. Node remains independent. See `docs/P1_BUILD_REPAIR.adoc`. No change to DAPI schema v2 or registry API behavior.

## v0.4.3 — correct the legacy ZipRunner project recipe

The target Windows run of v0.4.2 showed `[build-env] Reusing verified isolated .venv`
inside unit tests, but the actual **configured build** still ran the old
`python -m unittest discover -s tests -v` with the unprepared system Python.
The packaged `atrium.zr` had stale `build_commands` even though `project.zr`
was correct. v0.4.3 synchronizes both recipe formats and tests their parity.

**ZipRunner can retain an older trusted project registration independently of
source overlays.** Review/refresh the configured project's build command list:

```text
python tools/setup_build_env.py
python tools/run_python_checks.py
npm test
npm run build
npm run verify
```

If ZipRunner still runs bare `python -m unittest ...` after importing this ZIP,
re-import `atrium.zr` as the project recipe or update the project's configured
build list. Source ZIP metadata cannot safely override an operator-approved
project configuration. Do not bypass failing SQLAlchemy tests or install globally.
See `docs/P1_BUILD_REPAIR.adoc`.

## v0.4.4 — versioned import and registered-recipe handoff

The 0.4.3 target Windows run still used *cached* build commands in the saved
ZipRunner project configuration, not the synchronized source recipes. This
version increments all package/release metadata and includes precise one-time
operator instructions in `docs/P1_044_IMPORT.adoc`. Before importing, refresh
**the active configured project** using `atrium.zr` or the build-command editor.
If the new log still executes direct `python -m unittest ...`, stop retrying
packages: this cannot be fixed by changing source-only metadata. No DAPI schema
or registry API behavior changes in v0.4.4.

## v0.4.6 — corrected independently importable `.zr`

The standalone `atrium.zr` now uses the actual published `ziprunner.zr/v1`
recipe schema (including `schema`, `match`, `build` and `start`), not the
previous legacy aliases `build_commands` and `match_patterns`. It is byte-for-byte
identical to `project.zr`. Import **atrium.zr into the existing ZipRunner atrium
registration first**, inspect and approve active build commands, then import
`atrium-0.4.6-ziprunner.zip`. See `docs/P1_045_ZR_IMPORT.adoc`.
No DB migration; the application registry is unchanged in this repair.

## v0.4.6 — verified legacy registered build compatibility

ZipRunner may still run a pre-registered command `python -m unittest discover -s tests -v`
in system Python even after a new `project.zr` is overlaid. This version includes
a **test-only**, Python-ABI-checked dependency bridge in `tests/_test_dependencies.py`.
It bootstraps the protected project `.venv` if it does not exist, then reuses
its packages for *all* real registry tests, without skipping tests or installing
globally. If Python versions differ it fails clearly. Initial setup requires
pip access to PyPI or a configured approved package index. The preferred trusted build remains
`python tools/setup_build_env.py` followed by `python tools/run_python_checks.py`.
The registry/API and database schema v2 are unchanged.

## v0.4.7 — Windows regression compatibility

The 0.4.6 ZipRunner Windows build proved SQLAlchemy-dependent registry tests execute successfully, but two mocked test paths expected POSIX `/` separators while `pathlib.Path` correctly emitted Windows `\` separators. v0.4.7 normalizes those unittest expectations to native `str(Path(...))`, adds a host-path regression test, and preserves the working isolated dependency bootstrap. The registry API and data schema are unchanged.

## v0.4.8 — GitHub Actions portability and pinned DAPI build

The source checkout pins LF endings for Looprd YAML and other source formats in
`.gitattributes` (the component sidecar hashes exact raw YAML bytes). GitHub
Actions builds the **pinned DAPI** management-panel CSS using DAPI's own Node 24
Sass build (`npm ci --ignore-scripts && npm run build:ui`) *before* importing
`looprd.app` in the disposable smoke test. The CSS is a generated, ignored
_upstream artifact and **is not bundled in Atrium's source ZIP**.

New static regression checks enforce CSS prerequisite ordering, pinned DAPI
revision, source LF/hash stability, and v0.4.8 CI artifact identity. GitHub Actions
results still require a new CI run; this release is **not** a claim of deployed
DAPI compatibility. Database schema stays at v2.

## v0.4.9 — approved architecture: Pages, shared identity and game installations

This is a documentation-only candidate, NOT a login or installer release.
`docs/PLATFORM_ACCESS_AND_INSTALLATION.adoc` specifies:

* Atrium (GitHub Pages frontend + Looprd component) is the standalone game
  launcher and registry, with optional reviewed web/PWA/native installation.
* Users register once in Social; a reusable Social web-auth service will let
  them log into Atrium directly, while Tavi remains a chat client that can
  open Atrium without forwarding Social credentials into games.
* Games declare supported platforms and capabilities; a Windows-only game
  is never offered as installable on a phone. A local server is optional
  for a future Atrium desktop launcher, not mandatory for mobile devices.

User sessions, PWA installation, artifact delivery, GitHub Pages publication
and Social tickets are NOT implemented by this documentation pass. No DAPI
schema migration or new component is performed.

## v0.5.0 — Pages static storefront deployment

Run `npm test && npm run build && npm run verify`. The new GitHub Actions **Publish reviewed Atrium Pages** workflow requires explicit operator dispatch and Pages configuration. See `docs/P1_050_PAGES.adoc`. No Social sign-in, native installs, Pages auto-push or Looprd DB migration.

## v0.5.1 — Game registration specification (documentation only)

`docs/GAME_REGISTRATION_AND_HOST_SDK.adoc` defines what v0.5.0 can currently register, how its reviewed catalog reaches GitHub Pages, and the proposed v2 hosted-game/SDK/identity integration with The Life Loop. `examples/life.atrium-game-v2.example.json` is an unimplemented design fixture. Current registry, DAPI schema v2, Pages publication and gameplay code are unchanged.

## v0.5.11 — Looprd-native game discovery specification

`docs/LOOPRD_GAME_DISCOVERY.adoc` describes the game-owned `looprd.yaml` handler, trusted registration announcement, review gate, and optional direct verified Social identity. No game auto-discovery, submission endpoint, data migration, or live Life publication is implemented by this documentation-only pass.

## Multiplayer architecture v0.5.11

See `docs/CRITICAL_ARCHITECTURE_DIFFERENCES_MULTIPLAYER.adoc` for prioritized gaps and `src/game_play_contract.py` for the first strict game-info contract validator. The supplied cross-project architecture and acceptance documents are preserved under `docs/upstream-*`. No gameplay or agent endpoint is advertised as deployed.

## v0.5.11 validation gate

Only the ZipRunner interchange manifest todo-work schema has been repaired after the v0.5.9 exact-commit GitHub Actions failure. The Windows job passed; Linux ZIP contract validation did not. See `docs/P1_060_CI_MANIFEST_REPAIR.adoc`. Source-build success is not operator acceptance.

== Atrium v0.5.11 — CI verification-plan alignment

Adds missing verification criteria/checks for existing ATR-104-CI-TODO-CONTRACT-060 ticket and a task-mapping regression. The v0.5.10 push passed Windows and failed upstream verification-plan mapping. Operator acceptance and exact-commit v0.5.11 CI remain pending. Details in docs/P1_061_VERIFICATION_PLAN_ALIGNMENT.adoc.


== v0.5.13 automatic public catalog gateway (source candidate)

An operator-started loopback-only read-only gateway serves only the live, hash-verified, reviewed SQLite catalog through a separate controlled HTTPS reverse proxy. A manually configured GitHub Pages endpoint then refreshes public data without repository pushes. No privileged DAPI tokens or Social sign-in are exposed to browsers. Revoked applications are removed on refresh; failed catalog reads close open iframes. The gateway requires a real controlled host/proxy and operator acceptance; it does not autonomously deploy. See `docs/P1_063_LIVE_CATALOG.adoc`.
