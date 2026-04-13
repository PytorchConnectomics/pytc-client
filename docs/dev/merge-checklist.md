# Merge Checklist for `feat/backlog-batch-1`

Use this checklist for every merge wave (infra → backend → frontend).

## 1) Pre-wave sync (required)

```bash
git fetch --all --prune
git checkout feat/backlog-batch-1
git pull --ff-only
```

**Pass criteria**
- Local branch is up to date with remote.
- Working tree is clean (`git status` shows no pending changes).

**Fail criteria**
- Pull/rebase conflicts.
- Dirty working tree or detached HEAD.

## 2) Candidate branch rebase (required per PR)

```bash
git checkout <candidate-branch>
git rebase origin/feat/backlog-batch-1
```

**Pass criteria**
- Rebase completes with no unresolved conflicts.
- Branch pushed successfully if history changed (`git push --force-with-lease`).

**Fail criteria**
- Unresolved conflicts remain.
- Rebase exceeds timebox (30 minutes) without safe resolution.

## 3) Verification commands (required before merge and after each merged PR)

```bash
# Repository integrity
git status --short --branch

# Backend smoke checks (if backend touched)
python -m py_compile $(rg --files server_api server_pytc | rg '\\.py$')

# Frontend lint/build smoke checks (if frontend touched)
cd client && npm run -s lint && npm run -s build && cd -
```

**Pass criteria**
- `git status` shows expected branch and clean tree.
- Python compile check exits 0.
- Frontend lint and build exit 0 when frontend scope is part of wave.

**Fail criteria**
- Any command exits non-zero.
- New warnings/errors indicate regression risk.

## 4) Merge execution (one PR at a time)

```bash
git checkout feat/backlog-batch-1
git merge --no-ff <candidate-branch>
```

**Pass criteria**
- Merge commit created without unresolved conflicts.
- Post-merge verification commands all pass.

**Fail criteria**
- Merge conflicts unresolved.
- Post-merge checks fail.

## 5) Conflict log (required when applicable)
For each conflict, record:
- PR/branch name
- Files affected
- Conflict type (ownership/contract/behavior)
- Resolution chosen
- Follow-up action (if deferred)

## 6) Wave completion gate
Wave is complete only when:
- All PRs assigned to wave are merged or explicitly deferred.
- Verification commands pass after final merge.
- Conflict log is updated for any incidents.
