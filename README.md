# Atrium — Games, apps and shared game services

> **P1 / v0.4.6 source candidate.** Looprd is a specification; DAPI is the runtime.
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

This builds a deterministic `dist/atrium-0.4.6-ziprunner.zip` including mandatory
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
