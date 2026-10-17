# Agent entry point for atrium

Read in this order before changing code:

1. `INSTRUCT.md` — product intent and non-negotiable behavior.
2. `DESIGN.adoc` — architecture, data boundaries, and update flow.
3. `PROJECT_PLAN.adoc` — accepted milestones, current scope, and risks.
4. `ENGINEERING_STANDARD.adoc` — size, design, dependency, and regression rules.
5. `CODING.md` — implementation and LLM/agent guardrails.
6. `TESTING.md` — focused, full-suite, package, and regression validation.
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

Machine-readable thresholds live in `ziprunner.quality.json`.
