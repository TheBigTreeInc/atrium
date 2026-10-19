= Atrium 0.5.22 — corrected ZipRunner source candidate

0.5.19 failed Windows Python CI integration test because `.github/workflows/verify.yml` named the 0.5.18 artifact. Fixed workflow validation and upload references to 0.5.22, bumped source version declarations and added regression assertions. No change to Life game authority, Tavi or DAPI. See `docs/P1_070_WORKFLOW_VERSION_REPAIR.adoc`. Operator should apply this ZIP without deleting local state and check exact installed bytes; no push or deployment authorized.

= Atrium v0.5.18 CI smoke repair handoff

A source-only CI repair for run 39173201839 isolates disposable v1/v2 DAPI smoke phases into separate rate-limit sessions sharing one persisted DB; production limits remain unchanged. The latest 37-ticket local operator snapshot is preserved as `docs/ZIPRUNNER_LOCAL_WORKBOARD_37_20261019.json`. See `docs/P1_068_CI_SMOKE_ISOLATION.adoc`. No automatic Git push, deployment, game publication, DAPI sender activation or operator acceptance.

# Atrium v0.5.18 — Trusted discovery v2 handoff

Deliver a **complete, flat-root source** ZIP to existing ZipRunner project `atrium`. Keep the historical workboard IDs/statuses and operator decisions. New source-candidate task: `ATR-108-TRUSTED-V2-RECEIVER`. Updated `looprd.yaml` release 0.5.18, additive database schema 6; backup existing v5 database and rehearse migration before any real activation. v2 DAPI service handshake/endpoints: `/registry/discovery/v2/capabilities` (GET), `/observations` (POST) with `apps:discover` service identity bound once to trusted deployment, plus apps:approve `manage`, apps:read `catalog`. v1 API remains unchanged. See `docs/P1_067_TRUSTED_DISCOVERY_V2.adoc` and fixture examples. Run source tests, official pinned ZipRunner 2.3 validator, pinned DAPI receiver/handler smoke and exact-commit GitHub CI; separately test the **actual Looprd 0.2.0 sender** in staging. No source ZIP authorizes Pi deployment, API secrets from logs, Git push, auto publication, database deletion or operator Work board approval.

# Atrium 0.5.16 — DAPI discovery receiver ZipRunner handoff

Atrium now accepts operator-bound DAPI `atriumd/v1` observations using a dedicated `apps:discover` service key with exact deployment/component/source identity; v5 additive SQL, strict Git/content provenance, ordered idempotent receipts, withdrawn/outage preservation, metadata-only operator review and trusted operator-only launch origin diagnostics. **Nothing discovered becomes automatically published.** DAPI pinned revision `dc79897a54f69141ce300bbdadd3bdd6bd996d14` provides **observe-only** discovery, not a sender. Real auto delivery requires an additional DAPI-side implementation and acceptance. No game or Social credential lives in the web frontend or sidecar. See `docs/P1_066_DAPI_DISCOVERY_RECEIVER.adoc` and fixtures `examples/discovery/`.

No Git push, release or production migrations/deployments are performed by this ZIP.

# Atrium 0.5.15 — ZipRunner handoff

Project key: `atrium` · Base: `0.5.14` · Source update only, no auto-push/deploy.

New bounded Work board source candidate `ATR-110-LOBBY-PREVIEW`: Atrium multiplayer lobby UI and transport-injected mock Life API, typed create/invite/join/list/resume, simulated 60h or unlimited turn policy, adapter/protocol negative tests and Pages-safe static build. The default public catalog remains empty, but the explicitly labelled Multiplayer Lab is visible. No user identity, persisted match state, public Life `/play` activation, Social event or DAPI migration is claimed. Python adapter was extended to the same proposed envelope, and Life's **internal-only** capability shape remains rejected as a public service.

The prior Checkers and publisher/gateway review candidates, operator acceptance criteria, deferred work and the remaining Life/Looprd discovery priorities are preserved. All source `done_work` records denote delivered candidate code, **not** accepted operator Done. The latest local operator Work board remains authoritative.

Source check evidence is `evidence/P1_065_LOCAL_CHECKS.txt`; documentation is `docs/P1_065_MULTIPLAYER_LOBBY_PREVIEW.adoc`. Rebuild and validate the exact `atrium-0.5.16-ziprunner.zip` with pinned upstream CI after an explicitly authorized push. The operator independently verifies installed-ZIP SHA, browser UI on real Pages, manual publication controls, and whether the work is accepted. No release is requested.

---

# Atrium 0.5.14 — ZipRunner handoff

Project key: `atrium` · Base: `0.5.13` · Source update (no automatic deployment).

Bounded task: `ATR-106-CHECKERS-PREVIEW`, first-party standalone local Checkers gameplay, operator-gated manual Pages publication and improved storefront. The default catalog remains empty until `publish_checkers_demo=true` on an explicitly dispatched `Publish reviewed Atrium Pages` workflow, with `catalog_url` empty. Life remains a coming-soon non-playable item; no Looprd/Tavi/Social integration or registry auto-approval was added.

Implemented source is **review candidate only**. Do not mark Done without operator acceptance. Preserve all existing Work board statuses and all remaining IDs. No source push, Git tag, release, hosted gateway deployment or Pages publication was performed.

Local checks: 192 Python tests under an offline system-package compatibility path; 18 Node tests; clean npm build and verification; opt-in Checkers asset created and SHA256 verified. Isolated `.venv` creation was blocked by unavailable pip index in this container; official Windows/Linux CI and target ZipRunner will run with their own dependency sources. Chromium headless smoke timed out in this container; real browser acceptance is pending. See `evidence/P1_064_LOCAL_CHECKS.txt`.

Next: operator installs this ZIP, verifies exact-commit CI, manually dispatches Pages `publish_checkers_demo=true` after approval, tests actual Play and opt-out rollback. The eventual Life path is `ATR-108-LOOPRD-DISCOVERY`; `ATR-107-AUTH`, `ATR-104-LIVE` and prior publisher-proof operator checks remain separate.
