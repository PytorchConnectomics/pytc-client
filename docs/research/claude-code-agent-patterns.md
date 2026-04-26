# Claude Code Agent Pattern Pass

Date: 2026-04-25

This note records what is useful for PyTC Client from the Claude Code source
inspection plus a quick literature/blog/documentation pass. The goal is not to
clone a coding CLI. The goal is to borrow agent-system patterns that make the
assistant a real biomedical segmentation workflow orchestrator.

## Sources Reviewed

- Local source inspection of `https://github.com/tanbiralam/claude-code/tree/main/src`.
  Treat this repo as architectural inspiration only; do not copy large code or
  user-facing strings.
- Anthropic Claude Code overview: agentic tool can read, edit, run commands,
  integrate tools, use MCP, customize instructions, run subagents, schedule
  tasks, and work across surfaces.
- Anthropic best practices: verify work, explore before plan before execution,
  keep context small, use skills for reusable workflows, hooks for deterministic
  checks, subagents for investigation, and permission allowlists/sandboxing for
  safety.
- Claude Code permissions docs: tools are tiered by risk; read-only actions need
  no approval while shell/file-changing actions do, and modes such as `plan`,
  `auto`, and `dontAsk` define execution boundaries.
- Claude Code subagents docs and blog: use focused agents when a side task
  would flood the main conversation; restrict their tools; return summaries
  rather than raw logs; use hooks for lifecycle gates.
- Jason Liu context-engineering note: slash commands keep recurring workflows
  focused; subagents keep verbose side work out of the main context.
- Liu et al. 2026 arXiv tech report on Claude Code design space: the simple
  model-tool loop is only the center; the important system work lives in
  permissions, compaction, extensibility, subagents, isolation, and append-only
  session storage.

## Source-Level Patterns Worth Copying

1. Tool-first orchestration
   - Claude Code models actions as typed tools with input/output schemas,
     permission checks, concurrency rules, progress state, and result mapping.
   - PyTC equivalent: every app action from chat should be typed as a workflow
     action with risk metadata: navigation, form prefill, editor load, model
     run, training run, metric computation, export, retraining proposal.

2. Permission and risk are first-class data
   - Claude Code separates read-only tools from risky tools and routes each
     through a permission layer.
   - PyTC equivalent: show whether an agent action is `view only`, `opens
     editor`, `runs job`, `writes record`, or `exports`; never hide the approval
     boundary.

3. Slash commands are compact workflow entrypoints
   - Claude Code uses slash commands and skills for repeatable work.
   - PyTC equivalent: support `/status`, `/infer`, `/proofread`, `/train`,
     `/compare`, `/export`, and `/help` as deterministic workflow commands.

4. Task/checklist substrate beats free-form progress prose
   - Claude Code has task/todo tools and structured background task state.
   - PyTC equivalent: the workflow agent should expose a machine-readable loop
     checklist from readiness gates and record actions as workflow events.

5. Ask structured questions when intent is ambiguous
   - Claude Code has an `AskUserQuestion` tool with short labels and bounded
     options.
   - PyTC equivalent: vague prompts like "I wanna..." should offer 2-4 concrete
     app actions, not a lecture or hidden prompt scaffolding.

6. Context hygiene is a runtime feature, not just prompt discipline
   - Claude Code has compaction, tool-result budgeting, summaries, and
     subagents/forks to prevent context floods.
   - PyTC equivalent: agent responses stay short; heavy evidence stays in the
     evidence panel/bundle; raw paths and logs should be expandable details.

7. Verification gates matter
   - Claude Code’s verification-agent pattern is adversarial: run checks, do not
     merely read code.
   - PyTC equivalent: after model/proofread/train/evaluate steps, the app needs
     acceptance checks over artifacts, metrics, and workflow events.

## Immediate Prototype Changes From This Pass

- Add workflow-agent response metadata: `intent`, `permission_mode`, and
  structured `tasks`.
- Add action/command risk metadata: `read_only`, `prefills_form`,
  `loads_editor`, `runs_job`, `writes_workflow_record`, `exports_evidence`.
- Keep command pseudo-code collapsed behind a `Route` disclosure so biologists
  see the app action first, not implementation text.
- Add deterministic slash aliases in the server and UI logging path:
  `/status`, `/next`, `/help`, `/infer`, `/segment`, `/proofread`, `/train`,
  `/compare`, `/metrics`, `/export`.

## Next Agent-System Work

- Add a real workflow task table or durable job table for long-running
  inference/training instead of relying on transient runtime action state.
- Add explicit approval modes: `ask`, `auto_read_only`, `plan_only`, and
  `blocked`, mapped to the biomedical workflow rather than copied literally
  from coding.
- Add hooks/gates:
  - Before training: require corrected mask path and correction-set record.
  - Before evaluation: require baseline, candidate, and reference volumes.
  - Before claiming improvement: require metrics and artifact lineage.
  - Before export: verify bundle contains workflow events and key artifacts.
- Add focused biomedical subagents only when they become real:
  - `data-curator`: inspect mounted project and identify image/mask/checkpoint
    roles.
  - `model-runner`: prepare and launch inference/training jobs.
  - `proofreading-triage`: rank likely failure regions and produce review queue.
  - `evidence-auditor`: verify artifact lineage before paper figures/export.
- Add context compaction for the assistant drawer: summarize old chat turns and
  keep workflow state/event evidence as structured context.

## Design Constraint For PyTC

Claude Code’s user is a developer who can read commands. PyTC’s user is a
biologist or biomedical-image researcher trying to complete a segmentation
loop. Therefore the visible surface should say "Run model", "Proofread this
data", "Use edits for training", and "Compare results"; command-like details
belong behind a disclosure or in logs.

## References

- [Claude Code overview](https://code.claude.com/docs/en/overview)
- [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code skills/slash commands](https://code.claude.com/docs/en/slash-commands)
- [How and when to use subagents in Claude Code](https://claude.com/blog/subagents-in-claude-code)
- [Slash Commands vs Subagents](https://jxnl.co/writing/2025/08/29/context-engineering-slash-commands-subagents/)
- [Dive into Claude Code: The Design Space of Today's and Future AI Agent Systems](https://arxiv.org/abs/2604.14228)
