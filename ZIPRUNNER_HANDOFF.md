# Atrium 0.5.14 — ZipRunner handoff

Project key: `atrium` · Base: `0.5.13` · Source update (no automatic deployment).

Bounded task: `ATR-106-CHECKERS-PREVIEW`, first-party standalone local Checkers gameplay, operator-gated manual Pages publication and improved storefront. The default catalog remains empty until `publish_checkers_demo=true` on an explicitly dispatched `Publish reviewed Atrium Pages` workflow, with `catalog_url` empty. Life remains a coming-soon non-playable item; no Looprd/Tavi/Social integration or registry auto-approval was added.

Implemented source is **review candidate only**. Do not mark Done without operator acceptance. Preserve all existing Work board statuses and all remaining IDs. No source push, Git tag, release, hosted gateway deployment or Pages publication was performed.

Local checks: 192 Python tests under an offline system-package compatibility path; 18 Node tests; clean npm build and verification; opt-in Checkers asset created and SHA256 verified. Isolated `.venv` creation was blocked by unavailable pip index in this container; official Windows/Linux CI and target ZipRunner will run with their own dependency sources. Chromium headless smoke timed out in this container; real browser acceptance is pending. See `evidence/P1_064_LOCAL_CHECKS.txt`.

Next: operator installs this ZIP, verifies exact-commit CI, manually dispatches Pages `publish_checkers_demo=true` after approval, tests actual Play and opt-out rollback. The eventual Life path is `ATR-108-LOOPRD-DISCOVERY`; `ATR-107-AUTH`, `ATR-104-LIVE` and prior publisher-proof operator checks remain separate.
