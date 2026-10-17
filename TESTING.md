# Testing and regression rules for atrium

## Required sequence
1. Reproduce the defect or define the acceptance criterion.
2. Add or identify a focused regression test.
3. Run the smallest relevant test while iterating.
4. Run component/integration tests for affected boundaries.
5. Run the complete project suite before packaging.
6. Compile or lint the touched language where supported.
7. Open and validate the produced archive.
8. Extract it into a fresh temporary directory and repeat package-level checks.

## Bug fixes
A bug fix is incomplete without a regression test unless automation is impossible. Then record exact manual reproduction and verification steps.

## Refactoring
Add characterization tests before moving legacy behavior. Separate refactoring from feature work when practical.

## UI work
Test state transitions and commands, not only widget construction. Capture the relevant screen and list exact operator checks.

## Safety and persistence
Exercise invalid input, interrupted writes, restart recovery, duplicate delivery, and protected paths. Durable formats require migration/recovery tests.

## Packaging gate
A handoff package must compile, pass focused and full tests, exclude secrets and active local configuration, open as a readable archive, and pass validation from a fresh extraction.
