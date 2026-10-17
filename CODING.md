# Coding defaults for atrium

## Required reading
Read `INSTRUCT.md`, `AGENTS.md`, `DESIGN.adoc`, `ENGINEERING_STANDARD.adoc`, `CODING.md`, and `TESTING.md` before implementation.

## Change discipline
- Prefer small, reviewable patches with one clear purpose.
- Preserve existing behavior unless accepted scope explicitly replaces it.
- Do not combine a broad refactor with a feature unless required for safety.
- Add or identify characterization tests before changing legacy behavior.
- Make safety behavior visible in the UI/logs instead of silently assuming.

## File and function size
- Target at most 400 lines per authored source file; 500 lines is a hard review threshold.
- Existing oversized files are debt, not permission to grow. Use a no-growth ratchet.
- Target at most 40 lines per function and review functions over 80 lines.
- Split by cohesive domain responsibility and avoid dumping-ground modules.
- Use clear names and docstrings for non-trivial workflows and state transitions.

## Regression protection
- Every bug fix must add a regression test that fails before the fix and passes after it.
- New behavior requires focused tests for acceptance criteria and important failures.
- Run the smallest relevant test first, then the full suite before packaging.
- Validate archive integrity and a fresh extracted copy before handoff.
- Do not weaken a test merely to make a change pass.

## APIs, persistence, and design
- Keep OpenAPI/public schemas synchronized with routes and DTOs.
- Version durable state and migration formats; preserve user data.
- Update `DESIGN.adoc` for material architecture changes.
- Test every automated action against the authored design authority and cite the governing section.
- Never invent a missing decision. Stop only the affected scope, record the decision gap, and continue independent covered work.
- Record decisions with context, alternatives, consequences, migration, and rollback.

## Dependencies and generated files
- Prefer the standard library or existing dependencies.
- New dependencies need a concrete reason, maintenance impact, and simple setup.
- Do not commit generated artifacts, runtime data, secrets, databases, logs, or build output.

## LLM/agent guardrails
- Do not rewrite unrelated areas or invent environment values.
- State assumptions and verify them in code or tests.
- Prefer deterministic scripts and visible status over background magic.
- Apply safe, bounded, verifiable repairs automatically and report what changed.
- Stop for review when repair is ambiguous, destructive, security-sensitive, or unverifiable.

## ZipRunner-ready answer format
```text
ZIPRUNNER_HANDOFF v1
project: atrium
artifact_type: source_zip
version: <version-or-build-id>
filename: <exact-download-filename.zip>
action: download_to_inbox
notes: short human-readable summary
END_ZIPRUNNER_HANDOFF
```
