# ZIPRUNNER_HANDOFF v1

project: atrium
artifact_type: source_zip
version: 0.4.7
filename: atrium-0.4.7-ziprunner.zip
action: download_to_inbox
notes: Repair two Windows-only regression test failures caused by POSIX mock path expectations; retain working SQLAlchemy setup and registry tests. No migration.

END_ZIPRUNNER_HANDOFF

## Operator checks

* Import the 0.4.7 ZIP into existing ZipRunner project `atrium`.
* The same registered build recipe should now complete Python testing, including the real SQLAlchemy registry tests.
* Confirm no `assert_called_once_with('/fake-test-venv')` or `assert_called_once_with('/created-test-venv')` mismatch.
* Ensure npm tests/build/verification pass, then verify stable latest moved to 0.4.7.
* No database migration, Looprd deployment, Git push, or trusted recipe overwrite is requested.
