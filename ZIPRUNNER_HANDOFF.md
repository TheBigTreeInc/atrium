# Atrium 0.5.74 — post-update stamp version repair

Fixes ZipRunner failure on 0.5.72 caused by a stale 0.5.71 post-update stamp. Adds packaging preflight and regression. See `docs/P1_117_POST_UPDATE_STAMP_REPAIR_073.adoc`.

# Atrium 0.5.74 — CI schema and WindowsPath symlink regression repair

GitHub 42377997643 revealed strict pinned done_work evidence validation and WindowsPath-specific symlink mock behavior; 0.5.74 repairs both without changing the game runtime. The 0.5.70 Windows/CI acceptance is NOT passed. See `docs/P1_115_GITHUB_CI_REPAIR_071.adoc`.

Windows ZipRunner 2026-11-07 failed on `test_offline_game` requiring Windows symlink creation (WinError 1314) and an exact string assertion of a Unix-style Python interpreter path. The tests now preserve fail-closed security validation without elevated Windows privileges and compare normalized native paths. No production game logic, TaviX package install mechanism, existing C4 components or operator approval gates changed. Retains the full independent Klondike/TaviX converter work from 0.5.69. See `docs/P1_114_WINDOWS_TEST_PORTABILITY_070.adoc`.

# Atrium 0.5.69 source handoff — external Klondike developer preview

The independent Klondike 0.1.0 build passed 52 game tests and 47 distribution checks. Atrium fixed .sha256/SVG candidate intake and added `tools/offline_tavix.py` to generate a deterministic *unprivileged* local `.tavix` test app from a verified candidate. No game source is included, and no install, Atrium Installed Games, save persistence, approval, production CI or release is claimed. See `docs/P1_113_KLONDIKE_EXTERNAL_GAME_QA_069.adoc`.

# Atrium 0.5.68 — external offline game candidate intake (source-only)

See `docs/OFFLINE_GAME_HANDOFF.adoc`. The package verifies independent builds but does not install or play them in Tavi. No Solitaire game is included.

# Atrium 0.5.67 — Windows Checkers QA Python isolation repair

GitHub Actions run [42307595956](https://github.com/TheBigTreeInc/atrium/actions/runs/42307595956) failed under Windows because standalone group QA inherited host Python without PyYAML. This repair runs the 47-case group under the verified project `.venv`, and uses the same dependency isolation for the generated-spec guard. Gameplay, the existing C4 architecture, and immutable TaviX remain unchanged. Independent Windows/operator and release approval are pending.

## Previous pass

# Atrium 0.5.66 — exact package Checkers group evidence

Expanded the packaged Checkers QA suite to seven required groups including all American Checkers rules, shared game engine and ownership boundary tests. Every group has a minimum and fail-closed verdict; missing, skipped or duplicate coverage cannot be claimed as passed. 0.5.65 exact CI was successful (https://github.com/TheBigTreeInc/atrium/actions/runs/42239065318). This version does not activate Social/LoopRD services, alter TaviX releases, or approve Windows/operator release. The established C4 model is unchanged because this pass only extends tests. See docs/P1_110_CHECKERS_EXACT_PACKAGE_RULE_BOUNDARY_QA_066.adoc.

# Atrium 0.5.65 — C4 Level 3 architecture baseline (source-only)

Added `architecture/c4/workspace.dsl` and `architecture/c4/README.adoc` at the ZIP root. The Structurizr DSL identifies current Atrium LoopRD, static web, TaviX, optional operator gateway, Market Grove and source-only Checkers responsibilities, with Level 1/2 context and Level 3 component views. Two dynamic views describe conditional discovery and source-only Checkers. There is **no claimed live deployment diagram**. Source-backed regression checks guard stable identifiers, evidence paths and package inclusion; the official Structurizr CLI is not available in this build environment and its parser validation remains unverified. No TaviX release, public gateway, game activation, identity credentials, operator configuration, Git push or release approval is changed. See `architecture/c4/README.adoc`.

# Atrium 0.5.64 — Material 3-inspired UI source candidate

Based on 0.5.63. Adds semantic Material-inspired light/dark CSS, local vector navigation, genuine source filters and retryable catalog diagnostics, and a single internal tab row when embedded in an operator-reviewed future hosted TaviX. The existing published TaviX 1.0.4 is byte-locked; no games, real Social service endpoints, launch URLs, or release approvals are fabricated or deployed. Fresh native Windows ZipRunner, CI and human operator acceptance remain independent. See `docs/P1_108_MATERIAL3_ATRIUM_064.adoc`.

# Atrium 0.5.63 — source repair and Tavi catalog diagnostics

The 0.5.62 Windows ZipRunner build failed (`WinError 32`) because the Social admission restart test closed an obsolete bound SQLite connection but left the reopened match DB in use. The test now closes the latest connection at teardown and verifies the DB can be removed. The future *reviewed* hosted TaviX UI has mobile light/dark polish, better catalog connectivity messaging, and Atrium navigation moved to top tabs, avoiding Tavi's second bottom bar. **Historical TaviX 1.0.4 is immutable and unchanged.** Empty offline catalog files are not proof that trusted games are absent upstream; real hosted LoopRD 0.5.0 gateway and verified registration must be activated by the operator before games appear. This source ZIP changes no URL, private config, operator approval, release or hosted registry.

See `docs/P1_107_CATALOG_MOBILE_AND_WINDOWS_063.adoc`.

# Atrium 0.5.62 — Social accepted challenge source admission (operator-gated)

0.5.62 source-only adapter: server-provided original accepted Tavi Social challenge, live accepted contacts and server-side authenticated session authorize two seats in the existing Checkers match authority. Typed denials propagate correctly. No actual Social service verifier, public LoopRD route or Tavi client is deployed; none of the previously authorized release/Workboard gates are altered. CI/installed Windows/real two-account QA remain independent. See docs/P1_106_CHECKERS_SOCIAL_ACCEPTANCE_062.adoc.

# Atrium 0.5.61 source-only Checkers hosted player

Built on exact 0.5.60 CI success: https://github.com/TheBigTreeInc/atrium/actions/runs/42037625554. Adds `web/games/checkers-remote.html`, its secure same-origin entry and five browser tests plus two generic/Tavi rule-ownership checks. The hosted player is not registered in a public catalog or activated in LoopRD and contains no guest or Social credentials. 0.5.61 exact CI, native Windows/operator acceptance, Social accepted-lobby admission and the real Tavi/browser match remain open. See `docs/P1_105_CHECKERS_HOSTED_PLAYER_061.adoc`.

# Atrium 0.5.60 remote Checkers client and board (source-only)

Builds on 0.5.59 exact successful CI run 42029745669. Adds server-authoritative remote match client and shared, rules-free board surface with retry-safe revisions. No live Social login, LoopRD route activation, Tavi/browser match or operator approval. Workboard operator decisions unchanged.

# Atrium 0.5.59 ZipRunner passed-evidence contract repair (not a release)

0.5.58 exact GitHub push `0baf1f230bafa7259ea2b2f1b2cf8239f79e1bfc` CI run 42023076428 failed the official pinned package validator at `validation.checks[23] passed requires evidence_ref`; Windows CI passed. This package includes the original bounded 0.5.58 local QA summary and adds package-time checks and negative source regressions. It preserves all fixture-only Checkers behavior. No active Social/LoopRD game API, real Tavi/browser match, Windows operator acceptance or release authorization.

# Atrium 0.5.58 verification-plan stage schema repair (not a release)

The official pinned ZipRunner validator rejected 0.5.57 exact GitHub commit `b4cd64a04ebaef41934d702b7f82fae5d011384f` at `$.checks[84].stage: test` (run 41986602716). Windows CI passed and Linux source/DAPI tests passed; the Linux package validation failed. This package uses the supported `unit` stage and preflights all check fields/stages before writing the ZIP, with regression tests. Source-only Checkers fixture tests unchanged (24 groups), no real Social/LoopRD handler or Tavi-to-browser acceptance. Fresh 0.5.58 CI, installed Windows operator QA, and release authorization pending.

# Atrium 0.5.57 CI package-schema repair (not a release)

0.5.56 exact GitHub push `aba619b3d27db1243e98344f0caf6f4ae4d46f18` failed Linux source ZIP validation at `$.update: unsupported field version` (run 41919291687). Windows CI succeeded. The pinned official schema allows `version` only under `project`, not `update`. The new candidate drops the invalid field, guards it with Python tests, and otherwise keeps Checkers functionality unchanged (24 group QA cases). 0.5.57 exact-commit CI, Windows post-update checks, operator acceptance and release are unverified.

# Atrium 0.5.56 source candidate (not a release)

Built on 0.5.55 exact-commit successful CI (https://github.com/TheBigTreeInc/atrium/actions/runs/41914857759). Adds `src/checkers_trusted_routes.py` (host-only strict operations), test-only `tests/support/checkers_trusted_http.py` and six network tests. The route is **not** registered with LoopRD, and fixture tokens do not provide real Social authentication. Independent operator acceptance and 0.5.56 CI remain pending. See docs/P1_100_CHECKERS_TRUSTED_TRANSPORT_056.adoc.

Atrium 0.5.55: trusted-host Checkers boundary and 18 source/exact-ZIP QA groups. Requires real Social service attestation and LoopRD activation separately. Baseline 0.5.54 CI passed at https://github.com/TheBigTreeInc/atrium/actions/runs/41887702820. No operator acceptance, release or live Tavi-to-browser match.

Atrium 0.5.54: server-owned turn-scoped legal actions and a complete 53-move two-fixture-client Checkers match via disposable HTTP in exact-ZIP QA. 0.5.53 GitHub push 2c418195942eeb5d4cdee724aaed8b7cdea43fa7 passed on Linux/Windows in run 41869522063. 0.5.54 CI, installed Windows, operator and release gates remain open. No production multiplayer endpoints or real Tavi-to-browser match. See docs/P1_098_CHECKERS_M1_FULL_NETWORK_GAME_054.adoc.

Atrium 0.5.53: Durable module-owned Checkers match core and stricter simulated network exact-ZIP QA; 0.5.52 exact GitHub Actions run 41856240674 succeeded on Linux/Windows. 0.5.53 target Windows operator and CI acceptance remain unverified. No Social/Tavi public host activated. See docs/P1_097_CHECKERS_SOURCE_MATCH_AUTHORITY_053.adoc.

Atrium 0.5.52: Exact-archive disposable Checkers multiplayer group QA source; v0.5.51 exact GitHub Actions run 40370535025 succeeded, but v0.5.52 CI/Windows ZipRunner and operator acceptance remain unverified. See docs/P1_096_CHECKERS_EXACT_PACKAGE_GROUP_QA.adoc.

Atrium 0.5.51: LoopRD 0.5.0 generic anonymous hosted-catalog GET is source-enabled; live activation and 1.0.6 TaviX are operator-gated. See docs/P1_095_LOOPRD_ANONYMOUS_CATALOG_051.adoc.

NOTE: This release adds protected LoopRD GET /catalog/hosted-games. The generic LoopRD anonymous GET feature is **not yet available**, so do not connect Tavi or publish TaviX 1.0.6 until LoopRD integration has been reviewed. See docs/P1_094_LOOPRD_NATIVE_HOSTED_CATALOG.adoc and docs/LOOPRD_HANDOFF_ANONYMOUS_COMPONENT_HANDLER_2026-10-26.adoc. Historical notes below describe earlier releases.

= Atrium 0.5.51 — LoopRD-native catalog source handoff

Source-only repair from exact 0.5.48 ZIP; `tests/test_spec_validation.py` no longer hardcodes prior 0.5.47 release, checking `package.json` instead. Version metadata and LoopRD SHA are synchronized. No private config, runtime state, generated outputs, or existing immutable TaviX 1.0.4/1.0.5 changes are included. Re-run Windows Python/Node and staging checks. Full details: `docs/P1_093_SPEC_RELEASE_WINDOWS_REPAIR.adoc`. This ZIP does not activate any remote hosted catalog.

# Atrium 0.5.48 — hosted catalog configuration and diagnostic repair

Current repair: Tavi Windows inspection confirmed official Atrium TaviX 1.0.5 reads an invalid reserved placeholder hostname and fetch failures were erased by a zero-games message. 0.5.48 surfaces hosted transport/configuration problems in both views, prevents reserved or unreachable URLs from entering the new immutable 1.0.6 release, and preflights anonymous HTTPS, JSON schema, CORS, no-store and at least one active trusted launch-mapped game before staging. Default build copies the checksum-pinned historical 1.0.4 payload (not a regenerated shared UI); it does NOT fix the installed 1.0.5 until a real operator gateway is published and 1.0.6 is released through TaviX. No endpoint, service, credentials, launch mapping or deployment was modified by the source package. See `docs/P1_092_HOSTED_CATALOG_INSPECTION_REPAIR.adoc`.


The 0.5.46 Windows ZipRunner log showed 337/337 Python tests and 61/62 Node tests. The final TaviX contract test staged 1.0.5 followed by offline 1.0.4 against the **real** sibling TaviX checkout because Windows staging is mandatory. `TAVIX_STAGE_INCOMPLETE` incorrectly required the historical 1.0.4 to still be the current repository-index entry.

In 0.5.47, all staging tests use a temporary fake TaviX repository; source staging distinguishes `TAVIX_STAGE_READY` for current and `TAVIX_STAGE_ARCHIVED` for correctly archived historical release. A later current catalog entry may not be silently downgraded; a stale index for newer requested release still fails closed. The default extension remains 1.0.4 and hosted 1.0.5 remains operator-gated. Build in ZipRunner and separately review any real TaviX Git changes; do not auto-push, invent URLs, or include local secrets. See `docs/P1_091_TAVIX_STAGING_WINDOWS_REPAIR.adoc`.

---

# Atrium 0.5.45 — mandatory Windows TaviX post-build

**Change:** `project.zr` and `atrium.zr` retain a single build/verify step and run `node tools/post_build_tavix.mjs` after it. On Windows this resolves `../tavix` from the Atrium source checkout and forces `TAVIX_STAGE_REQUIRED=1`; it launches `build_tavi_extension.mjs` then `stage_tavix.mjs` with the same environment. No silent `TAVIX_STAGE_SKIPPED` is acceptable on Windows. Verify the staged immutable extension `1.0.4` in `C:\Users\dorbi\source\tavix`, and review/push the **tavix** project separately. Do not manually re-run staging on every build; ZipRunner owns this post-build step.

**Acceptance:** Source Node and Python release tests, Windows ZipRunner installed build with sibling checkout, second byte-identical build no-op, missing checkout must fail, malformed/collision must fail without mutation; no automatic Git publication. Linux CI may skip optional staging.

= Atrium 0.5.43 — Social and Life service adapter handoff

*Input*: operator baseline Atrium 0.5.42; 0.5.43 is an additive source-only version, preserving the persistent SQLite lobby, Social challenge correlation and TaviX `tavix.surface/v1` publisher integration. New `src/trusted_multiplayer_contracts.py` validates only trusted, host-provided `challenge.status`, `contact.status`, Life `create`, match attestation, `join`, seat verification, `resume` and terminal `status` replies. Service transports and Life/Social user verification must come from the owning deployments, not browser request JSON.

*Activation warning*: No public Atrium route is enabled and no real Social or Life backend operation is claimed. Social/LoopRD must first provide server-only verified original-challenge lookup and contact status; Life must finalize match-attestation and challenge-bound seat admission with actual grants. Existing TaviX 1.0.4 compiled payload is byte-identical. Do not publish duplicate immutable bytes or auto-push.

*Verification*: `python -m unittest tests.test_trusted_multiplayer_contracts tests.test_social_challenge_bridge tests.test_lobby_runtime tests.test_hostless_lobby tests.test_lobby_outbox -v`, `npm test`, `npm run build`, `npm run verify`, `node tools/build_tavi_extension.mjs`, `python tools/package_zip.py`. ZipRunner must perform its normal isolated Python and Windows tests. The live TaviX host, two independent Tavi contacts, permissioned LoopRD and Life grant create/join/resume, separate restarts, native Back/Home and turn alert delivery remain operator acceptance requirements. No workboard status is promoted from source-test success.

*Precise Social/Life contract request*: `docs/P1_087_SOCIAL_LIFE_CONTRACT_CONSUMPTION.adoc`. Keep local `.env`, existing SQLite, generated `dist`, repo Git, keys and all private runtime state protected by `project.zr`.

= Atrium 0.5.42 — existing Tavi invitation to durable Life match (source-only)

*Source baseline*: 0.5.41 exact ZIP, not a remote Git state override. Adds `src/social_challenge_bridge.py`, 0.5.41 runtime/store extensions, `tests/test_social_challenge_bridge.py`, and `docs/P1_086_SOCIAL_CHALLENGE_TO_LIFE_LOBBY.adoc`. The new internal `new_game` call requests an idempotent Life-created match and only marks the Atrium lobby ready after Life verification. The Social game_challenge_send original numeric ID can be bound once to the ready lobby. Social acceptance requires a trusted server-side challenge lookup, then Life-owned seat admission and re-verification before the friend resumes. This is *not* a new client-facing /play or LoopRD API. No private social grants, session tokens or participant credentials are stored in the package. The database linkage is additive and not installed automatically. TaviX extension 1.0.4 compiled output is unchanged, with no new immutable TaviX version. No Git push, production migration, user acceptance or end-to-end two-account verification performed. Preserve local configs, generated dist and 52 existing workboard IDs/states. Full cross-project prerequisites and acceptance in `docs/P1_086_SOCIAL_CHALLENGE_TO_LIFE_LOBBY.adoc`.

= Atrium 0.5.41 — operator handoff

Source ZIP based on verified 0.5.40 artifact SHA-256 `a8c88e39e117a88c5debff1da67e002bfb8ef21aa4275254452369a0bf285691`. New file `src/lobby_runtime.py`, expanded `src/hostless_lobby.py`, tests and `docs/P1_085_HOSTLESS_AUTHORITY_ADAPTER.adoc`. This source builds a *non-public* bridge requiring injected, externally verified Social actor and Life authority; pending host contract makes production route/seat grants unavailable. Durable local outbox has no sender. No production SQLite upgrade, live identity authority, Git push, website publication or automated operator approval. TaviX manifest version remains **1.0.4**; unchanged UI bytes should re-stage idempotently when the sibling checkout exists. Follow the workboard/verification plan gates and preserve local config/state.

= Atrium 0.5.40 — operator handoff

Source package based on 0.5.39 (SHA-256 d689ae3f5fe6fb342d0468a773eb8ca0607c1d620636c8bf24b15ada664cfce6), with the 2026-10-25 hostless Tavi/Life/TaviX cross-session handoff. TaviX 1.0.4 is an immutable update; 1.0.2/1.0.3 bytes stay untouched. Source implements reviewed game surface launch and opt-in legacy/browser fallback; the server-owned SQLite lobby core is **not publicly routed or activated** until exact Social/Life authorization is agreed. No automatic commit, push, GitHub Pages release, private state, or runtime migrations. M1 and M2 await physical/native and two-account backend acceptance; see `docs/P1_084_HOSTLESS_TAVIX_LIFE_HANDOFF.adoc`.

# Atrium 0.5.39 — Repair handoff (2026-10-25)

**Input:** uploaded `atrium-0.5.38-ziprunner(1).zip`. Build failure diagnosis is source-derived, not a claimed reproduction of ZipRunner's private Windows traceback; the local ZipRunner report did not include the failing command.

**Source fixes:** correct stale 0.5.37 version pins across LoopRD, zip/test/workboard, verification plan and GitHub Actions. Restore consistency between manifest `done_work`/`todo_work` and the verification-plan tasks for `ATR-TAVIX-PUBLISH-038` (the source implementation remains operator-unverified). Increment TaviX extension version from 1.0.2 to immutable 1.0.3 because the TaviX repository already holds 1.0.2. Integrate the user-provided TaviX 1.0.0 SDK as the only browser host transport; generic game surfaces are feature-gated and Life's legacy match launch remains supported. Maintain the Material storefront, automatic operator-trusted LoopRD game publication, existing source and protected local state.

**Checks:** `npm test`, `npm run build`, `npm run verify`, `node tools/build_tavi_extension.mjs`, optional TaviX stage and `python tools/package_zip.py`; Python focused tests and LoopRD/discovery tests. Exact installed ZIP/Windows Python/.venv, post-update SHA, GitHub Actions for the *new* commit, live TaviX repository staging and Life client acceptance remain operator checks. The sandbox cannot install private isolated Python requirements due to DNS restrictions; do not report canonical `tools/run_python_checks.py` success here.

**Import instructions:** import only `atrium-0.5.39-ziprunner.zip`, not the earlier 0.5.37 preview or 0.5.38 ZIP. Once ZipRunner validates installation, inspect staged TaviX `extensions/inc.thebigtree.tavi.atrium/1.0.3/` and its repository index in your separate local Tavix project. Do not overwrite 1.0.2, do not auto-push, and verify actual Life auto-discovery + Tavi surface broker availability separately.

---

# Atrium 0.5.37 — Material game store + LoopRD-authoritative game publication

This source pass uses Atrium 0.5.36 as the baseline and changes the player-facing product from a technical catalog into a phone-first game app store / lobby. The primary views are Discover, My Games, Lobbies and Activity, with Material-inspired surfaces, large touch targets, safe-area-aware bottom navigation and a persistent Back to Atrium path while a game is open.

The publication model is also changed to match LoopRD ownership: an **active operator-trusted LoopRD deployment is already approved by the operator**. `tools/live_hosted_games.py` therefore emits active, valid `atriumd/v1` hosted games directly from `AtriumTrustedDeployment` + `AtriumTrustedInstance`; there is no second Life-specific approval JSON. Disabled/withdrawn games disappear automatically. Unsafe HTTPS/API bindings, mismatched identity, malformed entrypoints and non-immutable public source revisions fail closed. Life is handled by the same generic path as future games; it still owns identity, sessions, match seats and game state.

Local verification in this workspace:

* 29 focused Python release/publication/spec tests passed.
* 43 existing Node tests passed before the storefront regression was added; rerun `npm test` for the final package.
* `npm run build` and `npm run verify` passed.
* Full `python tools/run_python_checks.py` could not be completed because this sandbox has no package-index network access and the isolated `.venv` could not install pinned PyYAML. A direct system-Python discovery run progressed through the suite without a source failure before the execution timeout. ZipRunner must rerun the normal isolated post-update checks against the exact packaged bytes.

## Life acceptance

Life will appear automatically once its active trusted LoopRD deployment delivers the existing `examples/life.atriumd.yaml` contract and the deployment binds `game-web` to its reviewed HTTPS Pages origin. No Atrium-side per-game approval action is required. The static source does not hardcode a deployment URL because LoopRD remains portable.

Operator acceptance: install exact 0.5.37 ZIP; activate/observe Life; verify it appears in Discover/My Games; launch on phone/Tavi; withdraw/disable it and verify removal; restore it and verify return. Physical phone and live LoopRD activation are not claimed by this source package.


Atrium 0.5.39 TaviX distribution: the ZipRunner recipe builds its Tavi UI, then stages it into a sibling `tavix` checkout after verification. No Git push or hosted publication is performed. See `docs/P1_083_TAVIX_GIT_STAGING.adoc`.

## 0.5.45 — Corrected post-build dependency

The 0.5.44 operator snapshot showed configured_count=5 although both .zr files declared six build commands. The installed recipe may be cached. This release moves verified extension staging into the existing `npm run build` script itself, so no newly appended ZipRunner command is needed. Real staging into the sibling TaviX checkout is still pending Windows proof; `TAVIX_STAGE_READY` and release/index files must be inspected. Never claim a successful source build itself proves publication.
