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
