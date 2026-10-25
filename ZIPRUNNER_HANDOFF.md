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
