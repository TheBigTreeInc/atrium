# Agent entry point for atrium

Read in this order before changing code:

1. `INSTRUCT.md` — product intent and non-negotiable behavior (authoritative source checkout; may not be present in older delivery ZIPs).
2. `DESIGN.adoc` — architecture, data boundaries, and update flow.
3. `PROJECT_PLAN.adoc` — accepted milestones, current scope, and risks.
4. `ENGINEERING_STANDARD.adoc` — size, design, dependency, and regression rules (source checkout).
5. `CODING.md` — implementation and LLM/agent guardrails (source checkout).
6. `TESTING.md` — focused, full-suite, package, and regression validation (source checkout).
7. `project.zr` — ZipRunner overlay/build/start/release behavior.

## Working contract
- Use the current source tree as the source of truth.
- Keep each change bounded to the accepted task. For a generated engineering pass, honor its review-versus-extraction stage.
- Preserve behavior and local configuration unless replacement is explicit.
- Add a regression test for every defect.
- Do not grow files already above the configured limit without extracting a coherent responsibility.
- Update design, schemas, and docs when their contract changes.
- Automated work requires a covered design boundary with exact references and no unresolved decision gaps.
- A missing decision blocks only the affected card; do not halt unrelated covered work or choose a default silently.
- Run focused tests first and the full suite before producing an artifact.
- Manager/QA may technically approve a completed candidate for operator testing, but only the operator may mark it Done after observable checks pass.
- Failed operator checks return the exact managed task to bounded development; do not require manual board-state movement.
- Never apply, promote, publish, push, tag, or release without explicit authority.

Machine-readable thresholds live in `ziprunner.quality.json` in the authoritative Git checkout.

## Project-owned knowledge and external contracts (0.5.84 source continuation)
- Read the proposed global Library `/ECOSYSTEM.md` and project-scoped `/registry/projects/atrium/PROJECT_AGENTS.md` when available; source checkout and approved contracts take precedence over unverified mirrors.
- Maintain Atrium's curated `registry/project-memory.json`; do not use raw transcripts, private endpoints, account information or secrets.
- `.ziprunner/PROJECT_AGENTS.md` is a **proposed** source-owned profile for future model bootstrap. It does not supersede this file, authorize automatic source changes, or establish a canonical UUID.
- Tavi owns identity, contacts, app installation and host grants. TaviX owns package metadata/trust. Tavi Assets owns `.tavia` grants and asset lifecycle. Atrium owns game discovery presentation, lobbies and matchmaking coordination. Game authorities own moves, seats and state. Never bypass the owning component.
- Preserve the immutable Atrium TaviX 1.0.4 build and do not advertise unmounted Life authority or Windows operator acceptance as complete.
- Project-specific Library documents and schematic mirrors are derived records; shared `/registry/catalog.json`, `/registry/INDEX.md` and `/schematics/_defaults/` are externally stewarded and require separate approval to publish.
- Before future development, confirm latest main revision/branch, source version, Workboard status and applicable schema profile. This ZIP builds on Library 0.5.83 source candidate, not an independently verified complete current Git checkout. Market Grove Wallet settlement is a separately owned Social service gate.
