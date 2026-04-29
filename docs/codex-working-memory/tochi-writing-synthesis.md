# TOCHI Writing Synthesis (2026-04-13)

Corpus reviewed from local PDFs:
- `3769675.pdf`
- `3771924.pdf`
- `3770583.pdf`
- `3762808.pdf`
- `3778354.pdf`
- `3771935.pdf`
- `3769680.pdf`
- `3772068.pdf`
- `3777906.pdf`

## Recurrent Writing Patterns

1. Open with scoped problem framing plus concrete context; avoid broad generic motivation.
2. State explicit research/design questions early (often in intro or method framing).
3. Present contributions as a short, concrete list with specific artifacts or outcomes.
4. Use a clear traceability chain from observations to design goals/requirements/tasks.
5. Keep related work sectioned by conceptual overlap and end with a precise gap statement.
6. In discussion, separate:
   - what findings imply for design/interaction,
   - methodological/validity limits,
   - future work.
7. Calibrate claims carefully; avoid implying completed evaluation when reporting design/prototype work.
8. Tie evaluation sections to explicit questions and measurable evidence sources.

## Actions Applied To Manuscript

File: `/Users/adamg/seg.bio/_toCHI__Human_Agent_collaboration_for_biomed_image_segmentation/sample-manuscript.tex`

- Added formative questions (`FQ1`, `FQ2`) in Section 3.
- Added a new Goal→Requirement→Task traceability table (`tab:grt-traceability`).
- Reframed Section 4 architecture with explicit layered model (`L1` state, `L2` mediation, `L3` controlled execution).
- Renamed feature subsection to emphasize design realization.
- Replaced placeholder Evaluation bullets with a structured protocol:
  - evaluation questions (`EQ1`--`EQ3`),
  - planned study phases,
  - metrics and evidence,
  - analysis plan.
- Recompiled PDF after text edits.

## Internal Implementation Reality (Not For Manuscript Text)

Implemented in project codebase (current evidence in tests/logs):
- Workflow state/event backbone and APIs.
- Proofreading/inference/workflow event integration.
- Approval-gated proposal flow.
- Chat timeline/state grounding.
- LLM configuration hardening + backend observability improvements.

Design ideation / planned extensions:
- Failure hotspot prioritization.
- Correction impact preview.
- Project-level autonomous run manager.
- Versioned experiment bundles.
- External CAVE-compatible integration flow.
- Autonomous plan simulation UI.

