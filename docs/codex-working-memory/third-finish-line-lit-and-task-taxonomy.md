# Third Finish-Line Heuristic: Literature-Informed Task Taxonomy

Last updated: 2026-06-04

This note captures the third finish-line pass for the Yixiao / TapeReader XRI
case-study prototype. It combines a lightweight literature scan with a local
app-readiness sweep, then maps the remaining work into parallel implementation
tracks.

## Recent Literature Signals To Incorporate

The newest useful thread is not "make the chatbot smarter." It is: make the
human and agent maintain explicit common ground while working through bounded
workflow actions.

Relevant recent signals:

- **Human-AI common ground:** recent HCI/human-factors work emphasizes that
  collaborative agents need shared goals, relevant context, breakdown detection,
  and repair. Product implication: project facts should be visible,
  confirmable, and correctable, not hidden inside chat state.
- **Interaction / process / infrastructure framing:** recent human-agent
  collaboration framing separates conversational interaction, durable process,
  and infrastructure. Product implication: chat should be a surface over project
  memory, action cards, and the evidence ledger, not the source of truth.
- **Visual analytics agents:** recent VIS/VA work on multimodal agents and
  visual-analytics workflows suggests agents need to interact with and reason
  over coordinated views, not just answer from text. Product implication:
  browser-level workflow tests and visible workflow-state surfaces are part of
  the technical contribution, not polish.
- **Formal workflow representation:** emerging workflow-language work for visual
  analytics reinforces that reusable workflow state should be explicit.
  Product implication: our export bundle and readiness gates should encode
  enough structure to compare, replay, and audit runs.
- **Agent safety indices / deployed agent audits:** current agent-system audits
  repeatedly track approval requirements, auditability, and capability
  disclosure. Product implication: every mutating/expensive action needs a
  policy reason, stale-context status, and approval trail.

### Source Anchors From This Pass

These are not exhaustive paper citations. They are the specific recent sources
that motivated this pass and should be folded into the manuscript/background
review if they remain relevant after a deeper bibliography check.

| Source                                                                                                                                                                                                                                                  | Why It Matters For seg.bio                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Chen et al., **ThinkFlow / From Conversation to Human-AI Common Ground** (CHI 2026, Adobe Research), https://research.adobe.com/publication/from-conversation-to-human-ai-common-ground-extracting-cognitive-workflows-for-reuse-in-sense-making-tasks/ | Argues that conversational AI needs dynamic common ground and reusable workflow schemas rather than only preferences or rigid workflows. This supports explicit project facts and reusable case-study workflow state.     |
| Dhanoa et al., **Agentic Visualization** (arXiv/IEEE CG&A 2025), https://arxiv.org/abs/2505.19101                                                                                                                                                       | Extracts agent role, communication, coordination, progress-indicator, and provenance-log patterns for visualization systems. This supports specialist workflow agents, operation traces, and evidence logs.               |
| Chen et al., **InterChat** (arXiv 2025), https://arxiv.org/abs/2503.04110                                                                                                                                                                               | Shows that natural language alone is imprecise for visual analytics and should be paired with direct manipulation/contextual interaction linking. This supports editable proposal fields and visible app-state grounding. |
| Sharma et al., **Feedback by Design** (arXiv 2026), https://arxiv.org/abs/2602.01405                                                                                                                                                                    | Identifies Common Ground, Verifiability, Communication, and Informativeness as feedback barriers. This supports fact cards, source-backed traces, and clear correction affordances.                                       |
| Gomez et al., **Human-AI collaboration is not very collaborative yet** (Frontiers in Computer Science, 2025), https://www.frontiersin.org/articles/10.3389/fcomp.2024.1521066/full                                                                      | Provides a vocabulary for different human-AI interaction patterns and reinforces that timing/sequence of AI suggestions matters. This supports action-card lifecycle and approval timing as design claims.                |

## Local Readiness Sweep: Remaining Gaps

The current prototype is much stronger than the earlier branch, but the gaps
that still matter for a strong first case study are:

1. **Common-ground UI is still implicit.**
   The agent can inspect project context, but the user does not yet have a
   compact "these are the facts we are both using" panel that is easy to
   confirm, edit, and reference during the study.

2. **Agent operations are not fully visible as a workflow trace.**
   We have proposal cards and some traces, but the user should be able to see a
   concise sequence: inspected facts -> proposed action -> approval decision ->
   execution -> project-memory update.

3. **Action policy and freshness are still partly convention-based.**
   The backend has strong proposal behavior, but it should expose machine-
   checkable reasons when an action is blocked, stale, or approval-required.

4. **Evidence export is useful but not yet a strict contract.**
   Current exports include richer provenance, but response models are still too
   generic and proposal-to-approval linkage is inferred from payloads.

5. **Browser-level workflow certification is not yet part of the standard gate.**
   The Playwright harness exists, but dependency/install flow and CI/operator
   instructions need to be robust enough that a case-study facilitator can run
   it.

6. **Real closed-loop claim remains gated.**
   The rehearsal path is strong, but the paper must not imply training,
   inference, and evaluation performance until a real app-launched run is
   recorded and exported.

7. **Deployment observability needs one more hardening pass.**
   The new demo manager works. The remaining gap is making runtime configuration
   and health warnings clear enough that a non-original developer can triage the
   demo quickly.

## Task Taxonomy For Parallel Work

| Track                                  | Goal                                                                                 | Primary Write Scope                                                                                                                          | Done When                                                                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Common-ground project facts         | Turn project context into a visible, editable, confirmable shared-state object.      | `client/src/views/FilesManager.js`, `client/src/contexts/WorkflowContext.js`, project-memory backend/tests if needed, docs.                  | Yixiao fact cards show modality, target, voxel size, volume split, training policy; edits persist and are visible to the agent/readiness gate.              |
| B. Agent operation trace               | Make the chat/timeline show concise operational traces without raw hidden reasoning. | `client/src/components/Chatbot.js`, `client/src/components/chat/*`, `client/src/components/WorkflowTimeline.js`, CSS/tests.                  | A user can expand a proposal/result to see inspected facts, policy decision, action status, and affected artifacts.                                         |
| C. Backend action policy and freshness | Expose stricter action readiness, stale-context blockers, and approval reasons.      | `server_api/workflows/router.py`, `service.py`, workflow tests, route docs.                                                                  | Action responses include `freshness`, `policy_decision`, `blocking_reasons`, and tests cover stale/missing context.                                         |
| D. Evidence contract and export schema | Make paper-grade evidence bundles more contract-like.                                | `server_api/workflows/bundle_export.py`, `evidence_export.py`, response models/tests/docs.                                                   | Export response has typed fields for proposal/approval/action/run/progress links; withheld-copy policy remains enforced.                                    |
| E. Browser certification and demo QA   | Make the browser smoke runnable and part of the operator gate.                       | `scripts/browser_yixiao_case_study_smoke.py`, `tests/test_browser_yixiao_case_study_smoke.py`, package/dev dependency docs, manual demo doc. | One documented command either runs Playwright or gives a deterministic skip with install instructions; smoke checks cover progress, chat, proposal editing. |
| F. Runtime/deploy observability        | Clarify demo health, runtime config, and log checks.                                 | `scripts/manage_demo_instance.py`, `scripts/inspect_demo_instance.py`, docs/tests.                                                           | Inspector reports configured ports/public bases clearly and avoids false failures during expected load; restart/status docs are complete.                   |

## Claim Boundary After This Pass

If these tracks pass, the Yixiao case study can claim:

- visible shared project understanding,
- approval-gated mixed-initiative workflow coordination,
- durable project-state updates,
- exportable provenance for the coordination loop,
- repeatable demo health/browser readiness checks.

It still cannot claim model improvement until a real training -> inference ->
evaluation run is completed and entered into the evidence ledger.
