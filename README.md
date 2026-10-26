Atrium 0.5.51: LoopRD 0.5.0 generic anonymous hosted-catalog GET is source-enabled; live activation and 1.0.6 TaviX are operator-gated. See docs/P1_095_LOOPRD_ANONYMOUS_CATALOG_051.adoc.

NOTE: This release adds protected LoopRD GET /catalog/hosted-games. The generic LoopRD anonymous GET feature is **not yet available**, so do not connect Tavi or publish TaviX 1.0.6 until LoopRD integration has been reviewed. See docs/P1_094_LOOPRD_NATIVE_HOSTED_CATALOG.adoc and docs/LOOPRD_HANDOFF_ANONYMOUS_COMPONENT_HANDLER_2026-10-26.adoc. Historical notes below describe earlier releases.

= Atrium 0.5.51 — LoopRD-native catalog handler

The 0.5.48 build failed only because `tests/test_spec_validation.py` expected `0.5.47` while the LoopRD release was `0.5.48`. The assertion now derives its expected release from `package.json`, maintaining the version mismatch protection without static stale pins. Source is rebased onto exact 0.5.48 ZIP. See `docs/P1_093_SPEC_RELEASE_WINDOWS_REPAIR.adoc`. Live hosted catalog and TaviX 1.0.6 activation remain separate.

# Atrium 0.5.48 — hosted catalog activation and error visibility

Atrium 0.5.48 fixes the hidden failed fetch in Discover/My Games; empty public config means not connected, not no registered games. A new hosted TaviX 1.0.6 is only built after a live verified anonymous HTTPS catalog preflight. The already-published 1.0.5 with an example hostname is immutable and is NOT overwritten. See `docs/P1_092_HOSTED_CATALOG_INSPECTION_REPAIR.adoc`.


Repairs the 0.5.46 Windows `npm test` failure with isolated TaviX contract fixtures and correct archived/current immutable release verification. No live Life activation is claimed. See `docs/P1_091_TAVIX_STAGING_WINDOWS_REPAIR.adoc`.

# Atrium 0.5.45 — required Windows TaviX post-build staging

Atrium's ZipRunner recipes run `npm run build`, `npm run verify`, then `node tools/post_build_tavix.mjs`. The post-build script builds the Tavi extension and stages it into the sibling **tavix** repository. For a Windows checkout at `C:\Users\dorbi\source\atrium`, it automatically sets `TAVIX_REPOSITORY_DIR=C:\Users\dorbi\source\tavix` and `TAVIX_STAGE_REQUIRED=1`. A missing checkout, invalid package or immutable-release collision fails the Windows build rather than skipping distribution silently. A separately configured TAVIX_REPOSITORY_DIR is respected.

Linux/CI builds without TaviX are still supported; `TAVIX_STAGE_REQUIRED=1` requires staging on any OS. This is *staging only*: review/push the separate **tavix** Git repository to publish; Atrium does not push or update installed Tavi clients. The compiled Atrium TaviX extension remains **1.0.4** with unchanged browser UI. See `docs/P1_088_REQUIRED_WINDOWS_TAVIX_POSTBUILD.adoc`.

# Atrium 0.5.43 — trusted Social/Life contract consumers (source integration)

This candidate adds `src/trusted_multiplayer_contracts.py`: host-injected, strictly validated response consumers for Social's original challenge status/current accepted friendship and Life's authoritative create/match attestation/join/seat/resume/status operations. It composes the existing server-owned `HostlessLobbyRuntime`, SQLite `HostlessLobbyStore` and `SocialChallengeBridge`; no user-operated game host is required. It does not authenticate users itself or execute Life rules.

**Coordination status:** Service response field shapes are *proposals* for the separate Tavi and Life sessions. The reviewed Social lookup and Life public game service are not yet provided here. This ZIP installs no public Atrium endpoint, no new game credentials, no new guest-facing lobby controls, and no production DB migration. TaviX 1.0.4 compiled assets remain identical to 0.5.42. Live two-account/60-hour offline resume remains pending. See `docs/P1_087_SOCIAL_LIFE_CONTRACT_CONSUMPTION.adoc` and `docs/QA_0_5_43.txt`.

# Atrium 0.5.42 — verified Tavi challenge correlation (source only)

The Atrium lobby host can now correlate **Tavi's existing game challenge** to a Life-confirmed persistent match, reusing Tavi friendships and inbox. `src/social_challenge_bridge.py` deliberately runs only behind an authenticated Social host and a Life-authoritative match/seat adapter. The exposed user experience still awaits the Social server-side original-challenge lookup, Life create/join/grant integration and live Tavi operator verification. No new public lobby endpoint, duplicate notification flow or game-specific LoopRD URL was added. Extension 1.0.4 remains byte-identical. See `docs/P1_086_SOCIAL_CHALLENGE_TO_LIFE_LOBBY.adoc`.

= Atrium 0.5.41 — hostless lobby authority adapter and outbox

0.5.41 adds an opt-in **unmounted** hostless lobby adapter (Social actor supplied by trusted LoopRD host, operator-trusted game binding, Life-scoped game grant callbacks) and an idempotent, server-persistent lobby lifecycle outbox. **No public handler or production authorization is enabled** pending joint Social/Life contract approval. See `docs/P1_085_HOSTLESS_AUTHORITY_ADAPTER.adoc`. TaviX compiled UI is unchanged at immutable **1.0.4**.

= Atrium 0.5.40 — TaviX Life launch and server-owned hostless lobby source

See `docs/P1_084_HOSTLESS_TAVIX_LIFE_HANDOFF.adoc`. This is a source candidate. Atrium only launches verified published games through a TaviX host that advertises the surface capability; older Tavi hosts offer explicit fallback, never automatic Chrome. A durable SQLite lobby source core is included but deliberately has **no unauthenticated LoopRD HTTP handler**; Life/Social audience-scoped seat grants, native embedding and deployment tests remain required. Extension 1.0.4 is a separate immutable TaviX release and will be staged only to an available sibling checkout, with no producer Git push.

= Atrium v0.5.39 — TaviX staging repair and generic game surfaces

Atrium 0.5.39 corrects 0.5.38 release identity drift across `package.json`, `looprd.yaml`, ZipRunner workboard, post-update stamp, verification plan, CI names, packaging and Python release tests. The TaviX extension changes from immutable version `1.0.2` to `1.0.3` to preserve already staged/published `1.0.2` bytes. The user-supplied TaviX 1.0.0 SDK drives host-owned navigation and `tavix.surface/v1` where advertised; Life keeps feature-gated `atrium.tavi-launch/v1` compatibility for clients without generic surfaces. See `docs/P1_084_TAVIX_STAGE_REPAIR.adoc`.

This is a versioned *source* build candidate, not proof that the 0.5.39 package ran on the operator Windows ZipRunner host, that TaviX 1.0.3 was published, that Life was live-discovered, or that a real Tavi client advertised generic surface support. The separate TaviX repository owns all published extension releases. No runtime data, secrets, operator keys, Git push or native Tavi rebuild is included. Existing workboard ticket statuses remain operator-owned.

= Atrium v0.5.37 — Material game store and LoopRD-authoritative publication

Atrium now presents a phone-first Material-inspired Discover / My Games / Lobbies / Activity experience. Active games from operator-trusted LoopRD deployments are published to the hosted-game catalog automatically after `atriumd/v1`, immutable Git revision, API-origin and HTTPS launch-origin validation. There is no second Life-specific approval document. Withdrawn or disabled deployments disappear automatically. Life remains game-owned for identity, sessions, state and multiplayer; Atrium only discovers and launches it. See `docs/P1_082_MATERIAL_STORE_AUTOPUBLISH.adoc`.

= Atrium v0.5.34 — Optional Looprd 0.3 generic registration reader

Games can include `TheBigTreeInc/atrium/.github/actions/register-game` in their successful Pages-deployment workflow. The action validates their portable metadata and sends a token-free `curl` to an operator-published public LoopRD registration endpoint. A *separate* `auth: public` LoopRD component (`modules/registration/looprd.yaml`) queues limited approved-source hints. Atrium independently verifies the exact successful GitHub Pages workflow and source SHA against its own trusted-source policy before committing Git-backed catalog entries to `main`. Registration is queued immediately; GitHub sync is scheduled every 15 minutes or operator-dispatched. No game-side Atrium repository permission or backend credential is required. The public endpoint cannot authorize a publisher, grant publication or call privileged Atrium APIs.

This release is a source/ZipRunner candidate, **not a live public endpoint**. Before use, operator must install the separate LoopRD component, review trusted sources, configure HTTPS and `ATRIUM_PUBLIC_REGISTRATION_ENDPOINT`, dispatch the Pages discovery config, and separately verify exact-commit CI, source artifacts, operator approvals and game/Tavi runtime. See `docs/P1_078_PUBLIC_LOOPRD_REGISTRATION.adoc`. The previously exported 40-ticket operator board is preserved as `docs/ZIPRUNNER_LOCAL_WORKBOARD_40_20261020.json` and remains authoritative; no status is silently promoted. The Tavi extension remains 1.0.2 because its shipped files did not change.

= Atrium 0.5.21 — Windows ZipRunner CI artifact version repair

This source-only pass repairs the hard-coded 0.5.18 CI artifact paths that caused the 0.5.19 Windows build regression; see `docs/P1_070_WORKFLOW_VERSION_REPAIR.adoc`. Hosted Life 0.5.19 adapter remains review-gated. No live Life match, publication or operator acceptance is claimed.

= Atrium v0.5.18 — DAPI smoke CI test isolation

A source-only CI repair for run 39173201839 isolates disposable v1/v2 DAPI smoke phases into separate rate-limit sessions sharing one persisted DB; production limits remain unchanged. The latest 37-ticket local operator snapshot is preserved as `docs/ZIPRUNNER_LOCAL_WORKBOARD_37_20261019.json`. See `docs/P1_068_CI_SMOKE_ISOLATION.adoc`. No automatic Git push, deployment, game publication, DAPI sender activation or operator acceptance.

= Atrium v0.5.18 — Looprd 0.2.0 trusted discovery v2 receiver

Source candidate for `atrium.discovery-observation/v2`: one operator-bound Looprd deployment identity and one `apps:discover` service key may automatically register **reviewed game metadata** from its trusted `atriumd/v1` sources. New games do not need per-game registration; Git/local/HTTPS source updates, replay, delayed acknowledgements, confirmed removal and multiple deployments are handled durably by additive schema v6. Legacy per-game review (v1) remains separately available. No immutable AppRelease, public browser executable, Social game grant, DAPI sender deployment, Git push or Pages publication is created by metadata discovery. See `docs/P1_067_TRUSTED_DISCOVERY_V2.adoc` and the preserved upstream trust contract.

Looprd 0.2.0 sender is required for actual automatic delivery; older pinned DAPI `dc79897a...` remains the source CI baseline but does not certify an online 0.2.0 sender. Back up and rehearse the Atrium database v5→v6 migration. Before enabling production delivery, perform authenticated real-sender acceptance and exact installed ZIP/CI checks. The 36-ticket local operator Work board snapshot is preserved under `docs/ZIPRUNNER_LOCAL_WORKBOARD_36_20261018.json`; source candidate work is not operator-verified Done.

== Local verification

[source,shell]
----
python tools/run_python_checks.py
npm test
npm run build
npm run verify
python tools/package_zip.py
----

= Atrium v0.5.16 — Authenticated DAPI discovery registration receiver

Atrium now accepts operator-bound DAPI `atriumd/v1` observations using a dedicated `apps:discover` service key with exact deployment/component/source identity; v5 additive SQL, strict Git/content provenance, ordered idempotent receipts, withdrawn/outage preservation, metadata-only operator review and trusted operator-only launch origin diagnostics. **Nothing discovered becomes automatically published.** DAPI pinned revision `dc79897a54f69141ce300bbdadd3bdd6bd996d14` provides **observe-only** discovery, not a sender. Real auto delivery requires an additional DAPI-side implementation and acceptance. No game or Social credential lives in the web frontend or sidecar. See `docs/P1_066_DAPI_DISCOVERY_RECEIVER.adoc` and fixtures `examples/discovery/`.

No Git push, release or production migrations/deployments are performed by this ZIP.

= Atrium v0.5.15 — Life multiplayer lobby sandbox (Atrium-only)

The public static storefront now includes a clearly labelled *Multiplayer Lab* panel even with an empty catalog. Explore simulated Life private matches: create with 60-hour or unlimited turn deadline, invite, join, continue and swap Alice/Bob turns in a memory-only mock. No production Life server, Social identity, game rules or notifications are connected. The existing Checkers publication and verified catalog gateway remain operator-controlled.

Implemented: transport-injected `src/multiplayer_lobby.mjs`, mock `src/mock_life_api.mjs`, UI `src/multiplayer_preview_ui.mjs`, parity Python lobby facade, negative contract tests and Pages-safe build. See `docs/P1_065_MULTIPLAYER_LOBBY_PREVIEW.adoc` for the explicit Life internal-to-public contract mismatch, security boundary and acceptance plan.

**No source push, hosted Pages change, database migration, Looprd component activation or player account was performed by this package.** Use your existing ZipRunner review/push flow, then run fresh exact-commit GitHub Actions and operator Pages checks.

== Local validation

[source,shell]
----
python tools/run_python_checks.py
npm test
npm run build
npm run verify
python tools/package_zip.py
----

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

### 0.5.29: Hosted Life catalog

The read-only reviewed hosted-game gateway and Tavi extension use the shared UI; see `docs/P1_075_LIFE_REVIEWED_HOSTED_PUBLICATION.adoc` for configuration and outstanding operator gates. Discovery does not grant public publication or Life player credentials.

## 0.5.32 Git-based hosted-game registration

See `docs/P1_077_GITHUB_GAME_REGISTRATION.adoc`; game-side action `TheBigTreeInc/atrium/.github/actions/register-game`, Atrium-owned scheduled reconciler `.github/workflows/receive-game.yml`, operator trust `registry/trusted-sources.json`. Registration requires explicitly enabled trust and does not certify live multiplayer.

== Looprd 0.3 generic service registration reader (source candidate)

An operator-installed `tools/pull_looprd_registrations.py` reads `registration.readers.v1` inventories and Atrium sidecars using separate private service credentials and forwards candidates to Atrium v2. It does not activate the Looprd 0.3 host or publish games; see `docs/P1_079_LOOPRD_03_GENERIC_READER.adoc`.

## Atrium 0.5.36 — nested Market Grove on LoopRD 0.4

**Updated deployment model:** Atrium's root `looprd.yaml` now owns the `subcomponents` declaration for `games/market-grove/looprd.yaml`. LoopRD 0.4+ exposes its independent API at `/looprd/atrium/market-grove/v1`, with its **own** authentication, database and jobs. The operator imports **one** Atrium parent source, not two flat sources. A trusted Atrium discovery reader consumes the child's `atriumd.yaml` and verified actual nested `apiPath`; candidate registration and public publication remain distinct. See `docs/P1_081_LOOPRD_04_SUBCOMPONENTS_MOBILE.adoc`.

The Atrium storefront and Market Grove practice-trading UI now include phone-first navigation, stackable holdings, safe-area spacing, larger touch targets and a clear Back-to-games path. Live LoopRD 0.4 host/device acceptance and Wallet Gold settlement are still pending.

## Market Grove (0.5.35 historical two-flat-source model)

Atrium includes the separately deployable fictional exchange under
`games/market-grove/`. Its generated `games/market-grove/looprd.yaml` declares the
optional LoopRD 0.3 `registrations: [{service: atrium, document: atriumd.yaml}]`
contract. The `market-grove` component has its *own* `auth: database`, market
SQLite state, scoped trade API and scheduled UTC auctions; no game trading
handler or database is merged into `atrium/looprd.yaml`.

A **disposable** combined source example is in
`examples/sources.with-market-grove.yaml` (one parent on 0.5.36); the actual operator source list is
not changed. `npm run build` packages a responsive practice-game operator preview
at `dist/games/market-grove/index.html`. The built public storefront catalog
still does **not** list or auto-publish this game. To discover it, use LoopRD
0.3 and configure the existing Atrium reader for the deployment with private
service-specific grants. See `docs/P1_080_MARKET_GROVE_LOOPRD_IMPORT.adoc`.

No Tavi Gold trading or Social account sign-in is wired into this source
candidate. Don't expose the practice-game operator key form as public login.


Atrium 0.5.38 TaviX distribution: the ZipRunner recipe builds its Tavi UI, then stages it into a sibling `tavix` checkout after verification. No Git push or hosted publication is performed. See `docs/P1_083_TAVIX_GIT_STAGING.adoc`.

## Windows TaviX staging (0.5.45)

`npm run build` now verifies its web output, builds extension `1.0.4`, and runs the sibling TaviX staging tool. This is intentionally anchored to npm build, because existing ZipRunner registrations can retain an older build command list. Operator Windows builds require staging; GitHub-hosted Windows CI without a sibling checkout may skip unless explicitly required. Failure to find the required checkout or its staged release/index fails npm build. Review and push the `tavix` project separately.
