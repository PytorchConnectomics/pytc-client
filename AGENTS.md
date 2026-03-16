# AGENTS.md

## Read This First

For deployment work, environment bring-up, or any PyTC runtime changes, read these files in order before editing code:

1. `docs/handoff/current-state.md`
2. `docs/handoff/architecture.md`
3. `docs/handoff/deployment-runbook.md`
4. `docs/handoff/known-issues.md`
5. `docs/handoff/validation.md`
6. `docs/handoff/env.md`

## Repo-Specific Guidance

- The app is a desktop-oriented Electron + React client with two Python services:
  - `server_api` on `:4242`
  - `server_pytc` on `:4243`
- A static data server runs on `:8000` for local samples and previews.
- The frontend defaults to `http://localhost:4242` via `client/.env`.
- `pytorch_connectomics` is consumed as an editable local dependency via `pyproject.toml`.
- Do not assume the local `pytorch_connectomics/` directory is tracked by git in this repo. On fresh machines, `scripts/setup_pytorch_connectomics.sh` is the source of truth for acquiring it.

## Current Integration State

- The current deployment-ready work lives on branch `fix/pytc-v2-runtime-and-schema`.
- The latest branch tip documented by the handoff pack is commit `0487b0a`.
- That branch contains two commits relative to `origin/main`:
  - `2ad52f8` `feat: stabilize PyTC v2 runtime and config flows`
  - `0487b0a` `chore: make local startup output more graceful`

## Scope Boundaries

Unless explicitly asked otherwise, keep these out of scope for deployment work:

- auth model redesign
- CORS/security hardening
- chatbot modernization
- broad UI redesign
- DB schema changes

## Practical Defaults

- For a first remote demo, prefer the simplest path that matches the user's environment:
  - full stack on a remote machine with a GUI session if Electron is required
  - backend services on a remote machine plus a locally run client if only runtime execution is needed
- Reuse the validation commands in `docs/handoff/validation.md` before calling a deployment change complete.
