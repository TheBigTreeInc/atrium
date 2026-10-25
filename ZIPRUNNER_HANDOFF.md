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
