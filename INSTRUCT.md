# atrium — product instructions

## Purpose
Describe the product goal, users, data boundaries, and first useful build target.

## Product shape
This project is a service / app. Keep it easy to run locally, safe to update through ZipRunner, and clear enough for an agent or developer to continue without guessing.

## Working context
Read this file first. Agents should then read `AGENTS.md`, `DESIGN.adoc`, `ENGINEERING_STANDARD.adoc`, `CODING.md`, and `TESTING.md` before changing code. Keep build/release behavior visible and gated where risk exists.

## Operator and managed lifecycle
The human operator decides whether a completed feature works as designed. ZipRunner owns normal managed transitions from To do through In progress and Manager/QA assessment. Only Manager/QA-approved completed work enters operator Review. Review must include concise observable checks and expected results. Passing every check may mark the item Done; failed checks or changed direction return the exact task to bounded development automatically. The operator must not manually drag managed work through lifecycle states.

## Data and runtime safety
Do not overwrite or publish local user data, secrets, runtime state, generated build output, caches, uploads, package stores, logs, databases, or private server state. Default protected patterns include:

```text
.git/**
.env
.env.*
*.pem
*.key
*.pfx
*.crt
private/**
**/private/**
server-state/**
**/server-state/**
runtime/**
**/runtime/**
data/**
**/data/**
storage/**
**/storage/**
uploads/**
**/uploads/**
packages/**
**/packages/**
public-index/**
**/public-index/**
logs/**
**/logs/**
chrome-profile/**
target/**
**/target/**
node_modules/**
dist/**
build/**
```

## Release expectation
Local build/test should prove the source is not obviously broken. Source publish should push source only. CI should build containers/software where possible. Remote deploy/restart steps should be manual/gated.

## Source ZIP workboard update (mandatory)
Every source ZIP returned for any ZipRunner project must include a root-level
`.ziprunner-workboard-update.json` with schema `ziprunner.workboard-update.v1`,
matching `project`, `version`, summary, one or more implemented items
(`id`, `title`, `summary`, `operator_checks`) and an explicit `remaining` array.
This is candidate implementation evidence; never mark a task Done yourself.
RoboScope unified `.patch`/`.diff` files are not source ZIPs and use a separate contract.

## ZipRunner handoff response protocol
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

For non-source attachments, use `artifact_type: zr_manifest`, `documentation`, `log`, or `context`. Never put credentials, tokens, private keys, or private local paths in the handoff block.

## API and integration notes
If this project exposes an API, maintain openapi.yaml/openapi.yml and inspect it before changing endpoints or clients. Keep `openapi.yaml` or `openapi.yml` updated when endpoints are added or changed.
