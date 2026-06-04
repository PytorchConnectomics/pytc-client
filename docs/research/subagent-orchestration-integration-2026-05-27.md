# Subagent Orchestration Integration - 2026-05-27

## Purpose

This note coordinates the parallel subagent pass for turning seg.bio into a paper-grade mixed-initiative workflow agent for the Yixiao/TapeReader XRI case study.

The integration rule is simple: subagent reports are advisory. The main implementation must converge on one shared orchestration layer where manual UI actions and assistant actions read and write the same project memory, volume state records, action proposals, policy gates, and evidence ledger.

## Active Subagents

| Lane | Agent | Scope | Expected Output |
| --- | --- | --- | --- |
| Backend State | Turing | Composite volume state and project memory backend | Schema/API transition plan, backcompat map, tests |
| App Agent Capability | Aristotle | Assistant intent routing, action proposals, response style | Capability matrix, routing gaps, trace/action changes |
| Action Policy | Volta | Action-card schema, risk tiers, approval gates | Strict action schema, policy table, approval tests |
| Trace/Evidence | Hume | Structured traces and provenance bundles | Trace schema, ledger/export improvements, tests |
| UI Workflow | Nietzsche | Onboarding, progress, assistant, action cards | UI streamlining plan for coherent manual-agent handoff |
| Yixiao Case Study | Dirac | First case-study readiness | Demo arc, negative tests, acceptance checklist |
| Reliability/QA | James | Prototype release gates | Regression, smoke, stale-state, refresh, failed-run checks |

Reliability/QA was queued after the first wave and wrote `docs/research/subagent-reliability-qa-2026-05-27.md`.

## Integration Acceptance Criteria

The next implementation pass should be considered successful only if all of these are true for the Yixiao case-study path:

1. The project state is represented by canonical records, not chat prose.
2. Volume readiness separates annotation maturity, workflow role, execution state, and region scope, even if legacy fields remain for UI compatibility.
3. The assistant answers from project memory and can name the evidence behind important claims.
4. Consequential assistant actions are typed action cards with inputs, target volumes, outputs, risk, approval policy, blockers, and expected state changes.
5. Manual UI actions and assistant actions produce the same state transitions and evidence events.
6. The assistant shows a structured trace, not raw chain-of-thought.
7. Promoting a draft mask changes project memory, progress, and future training proposals.
8. Evidence bundle export can reconstruct the inspect -> propose -> approve -> execute -> update story.
9. The Yixiao smoke harness verifies the happy path plus at least one state-transition roundtrip.
10. The public demo can be reset to the initial case-study state with one command.

## Candidate Implementation Order

1. Add composite-state helpers behind the existing volume-state API.
2. Add strict action-card construction helpers and normalize existing agent cards through them.
3. Add structured trace payload helpers and wire them to the most important Yixiao intents.
4. Add policy checks for training, inference, promotion, and evidence export.
5. Add Yixiao negative smoke checks once the state/action contracts are stable.
6. Tighten frontend rendering only after backend contracts stop moving.

## Non-Goals For This Pass

- Do not expose raw model chain-of-thought.
- Do not add arbitrary shell execution for the app agent.
- Do not claim TapeReader model-performance reproduction without a separate evaluation run.
- Do not replace the current UI wholesale; bridge the existing screens through a shared orchestration layer.
