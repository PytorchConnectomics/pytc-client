# Backlog Wave Orchestrator: Cloud Task Integration Protocol

## Purpose
This protocol defines how parallel cloud-task branches are integrated into `feat/backlog-batch-1` in controlled merge waves.

## Branch roles
- **Target integration branch:** `feat/backlog-batch-1`
- **Wave coordinator branch (this docs branch):** `agent/orchestrator-docs`
- **Contributor branches:** task branches opened by cloud agents (infra/backend/frontend)

## Merge wave order (required)
Use this fixed order to minimize cross-domain conflicts and keep root-cause analysis simple:

1. **Wave 1: Low-risk infrastructure changes first**
   - Examples: CI tweaks, tooling updates, non-functional config/docs.
   - Exclude backend behavior and UI-visible logic.
2. **Wave 2: Backend changes second**
   - API handlers, services, DB migrations, auth/business logic.
3. **Wave 3: Frontend changes last**
   - UI components, routes, state wiring, API consumption.

Do not start the next wave until the current wave passes all required verification commands.

## Conflict policy
When conflicts occur while merging a wave branch into `feat/backlog-batch-1`:

1. Stop and classify conflict type:
   - **Ownership conflict:** two branches changed same lines in same area.
   - **Contract conflict:** backend and frontend assumptions differ.
   - **Behavior conflict:** tests pass locally but behavior deviates.
2. Resolution priority:
   1. Preserve previously merged wave guarantees.
   2. Preserve explicit acceptance criteria from backlog task.
   3. Prefer smaller, reversible changes over broad rewrites.
3. Escalation rule:
   - If resolution requires changing behavior outside wave scope, pause merge and open a follow-up task branch.
4. Documentation rule:
   - Record the conflict and decision in the merge checklist before continuing.

## Rebase policy
Before merging any branch in a wave:

1. Rebase candidate branch onto latest `feat/backlog-batch-1`.
2. Resolve conflicts on the candidate branch (not directly on target).
3. Re-run the required verification commands.
4. Force-push only the candidate branch when needed (`--force-with-lease`).
5. Merge only after green checks.

If a branch cannot be cleanly rebased within 30 minutes, defer it to a follow-up wave.

## Required verification gate before each merge wave
Run these commands from repo root before wave start and after each merged PR in that wave:

```bash
git fetch --all --prune
git checkout feat/backlog-batch-1
git pull --ff-only
```

Then run the checklist commands from `docs/dev/merge-checklist.md` and require all pass criteria to be met.

## Operating cadence
- Merge one PR at a time within a wave.
- After each PR merge, rerun verification gate.
- If a gate fails, freeze wave, revert or patch forward, and resume only after all checks pass.
