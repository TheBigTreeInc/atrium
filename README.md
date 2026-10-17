# Atrium — Games, apps and shared game services

> **P0 / v0.3.0 source candidate.** Looprd is a specification; DAPI is the runtime.
> Tavi remains a separate client of the Social/Atrium services.

**Git repository:** https://github.com/TheBigTreeInc/atrium (main was README-only
when this candidate was prepared). **ZipRunner project:** `atrium`.
**DAPI component:** `atrium` (`looprd.yaml`). The nested `modules/` YAML files
are included fragments: one database, one API prefix, one authentication scope.

The repository includes the previous source-only v0.2.0 prototype: operator-only
registry and Arcade resources, a stateless Checkers evaluator, Staff table policy,
portable AppHost stub, Yahoo game research catalog and tests. These are not a
fully running multiplayer platform; not a public app store and not Social SSO.

## One-time development prerequisite

Python 3.12+ and Node 22+ recommended. Install PyYAML for source tooling:

```sh
python -m pip install -r requirements-dev.txt
```

## Fast local verification

```sh
python tools/build_spec.py --check
python tools/check_specs.py
python -m unittest discover -s tests -v
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

This builds a deterministic `dist/atrium-0.3.0-ziprunner.zip` including mandatory
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
