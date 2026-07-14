# TOCHI/HCI Prototype Takeaways

Purpose: keep implementation-facing notes from a quick TOCHI/HCI systems pass
while turning PyTC Client into a paper-defensible, human-controlled,
closed-loop biomedical segmentation prototype.

## Sources Read

- Dow et al., "Parallel Prototyping Leads to Better Design Results, More
  Divergence, and Increased Self-Efficacy", ACM TOCHI 17(4), 2010.
  <https://hci.stanford.edu/publications/2010/parallel-prototyping/ParallelPrototyping2010.pdf>
- Microsoft Research, "Guidelines for Human-AI Interaction" publication page:
  CHI 2019 guidelines and a TOCHI 2022 follow-up on early assessment.
  <https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/publications/>
- CHI 2025 Case Studies of HCI in Practice page, including recent examples of
  practice-facing case studies and pilot case-study framing.
  <https://chi2025.acm.org/for-authors/case-studies/>
- CHI 2026 Human-Agent Collaboration workshop call, especially mixed-initiative
  workflows, transparency, failure recovery, and shared accountability.
  <https://chi26workshop-human-agent-collaboration.hailab.io/>
- Adobe Research CHI 2025 summary on compositional structures for human-AI
  co-creation, emphasizing workflow-spanning prototypes, context, inspection,
  and control.
  <https://research.adobe.com/news/an-experimental-new-design-approach-for-human-ai-co-creation/>

## Implementation Takeaways

- A TOCHI-grade prototype should not only "do the task"; it should make the
  interaction logic inspectable. For this project, that means visible workflow
  state, artifacts, metrics, agent proposals, approvals, and exported evidence.
- Parallel-prototyping logic argues against a single opaque model result. The
  UI should support comparing baseline/candidate predictions and before/after
  metrics side by side, rather than only showing the latest output.
- Human-AI interaction guidelines push for calibrated expectations, visible
  uncertainty/failure, efficient correction, undo/dismissal, and clear handoff.
  For PyTC Client, the agent must show what it will do, what evidence it used,
  and whether it is blocked by missing files, long-running jobs, or failed
  metrics.
- Human-agent collaboration work stresses mutual awareness and shared
  accountability. The prototype should preserve an audit trail of agent plans,
  user approvals/rejections, runtime events, and artifact lineage.
- Recent workflow-spanning human-AI creation systems treat AI as embedded in
  multiple structures, not as a chat box bolted onto one screen. Here, the
  assistant should connect setup, visualization, inference, proofreading,
  retraining, evaluation, and evidence export through the workflow substrate.
- Case-study-facing HCI work needs evidence that is reproducible and
  inspectable. Participant UI should stay focused on the biomedical workflow;
  researcher case-study gates should remain in docs/tests/export bundles.

## Prototype Implications

- Keep the `Closed-loop Evidence` panel as the central participant-facing
  evidence surface. It should show baseline/candidate predictions, correction
  artifacts, reference labels, metric deltas, report paths, and bundle export
  status.
- Add explicit controls whenever auto-detection can silently fail. Dataset keys,
  crop windows, and channel selectors are necessary for HDF5/PyTC outputs.
- Treat long-running inference/training as accountable jobs, not transient UI
  state. The next hardening phase should add durable job records, cancellation,
  retry, and recovery.
- Make project setup boring. Suggested project mounting and auto-detected data
  roles reduce demo friction and prevent participants from spending study time
  debugging paths.
- Do not claim autonomous closed-loop improvement until the app can perform:
  baseline inference, proofreading export, retraining/fine-tuning, candidate
  inference, metric computation, and evidence bundle export using app-generated
  artifacts.

## Additions To Consider For The Paper

- Frame the system as a workflow evidence substrate plus bounded agentic
  control layer, not only as a GUI around PyTorch Connectomics.
- Include a figure that shows artifact lineage: source image/label, baseline
  prediction, correction set, retraining run, model version, candidate
  prediction, evaluation result, evidence bundle.
- Include a design rationale section grounded in human-AI interaction:
  calibrated autonomy, visible provenance, interruptible/approvable actions,
  and closed-loop comparison.
- If case studies are used, separate participant task flow from researcher
  readiness gates. The latter supports rigor but should not appear as
  participant-facing protocol UI.
