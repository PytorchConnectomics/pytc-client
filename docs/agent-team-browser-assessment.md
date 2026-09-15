# Team scaffold: browser assessment

**Follow-up implemented:** see [manager integration](agent-team-scaffold.md#integration-verification).
The findings below preserve the pre-fix browser observations.

September 15, 2026. Tested by operating the running app at localhost:3001 with
computer use. This is an assessment, not a claim of completed multiagent reasoning.
No application code or label data was changed in this pass; checks and chat messages
were saved through the normal app UI.

## Overall assessment

The separate tool workers and persisted task view work for the supplied NucMM pair.
The manager does not yet own the conversational workflow. The clearest next work is
connecting chat, project selection and typed actions to the task layer before adding
more specialist roles.

## Examples exercised

| Example | Observed result | Assessment |
| --- | --- | --- |
| Data inspection selected from Team | One data task; image 64 × 96 × 96, uint8; labels uint16 with 23 nonzero IDs; matching geometry | Works on this TIFF pair |
| Expand data task context | Workflow 1, biological description and only image/label artifact references; concrete metadata/count evidence | Useful scoped context, although exposed as raw JSON |
| Model readiness selected from Team | Registered preset exists; no checkpoint/prediction registered; no compute launched | Truthful but shallow: file checks, not runtime readiness |
| Annotation review selected from Team | No saved correction artifact; proposes proofreading | Correct for the original NucMM workflow |
| Whole project selected from Team | Three specialist results and one deduplicated proofreading action plus View data | Fixed coordination scaffold works |
| Team View data → chat Run in app | Opens Visualize with populated paths, but displays “Select an image and click Visualize to get started” | Incomplete handoff: another manual Visualize click is needed |
| Manual Visualize click | Real Neuroglancer volume/labels loaded, with 720 nm scales | Underlying viewer works |
| Browse NucMM engineering check in Files, then run model check | Files breadcrumb shows engineering project; task still records workflow 1 and original `/uploads/NucMM/` paths | Project-context ambiguity; browsing a folder is not switching workflow |
| Type “Ask the data specialist to inspect the current project and report the image dimensions and number of label IDs.” | Chat replies with generic original-project status and a Show status action; no new specialist run appears | Natural-language delegation is not integrated |
| Reload and reopen Team | Same 10:22:20 whole-project result and five earlier checks remain | Persistence works |
| Expand Earlier checks | Saved timestamps/status and generic summaries appear, but historical task evidence cannot be reopened from this surface | Persistence is useful; history UI is incomplete |

## Highest-priority gaps

1. **One conversation owner.** Route specialist requests through the manager/task
   service. A normal request currently bypasses it. The Team panel is a separate
   control surface, rather than a trace of what the conversation is doing.
2. **Explicit active project.** Put the project name in the team header and provide
   a clear workflow-switch operation. Do not silently infer workflow changes from
   folder browsing, but do make the distinction visible. Otherwise correct results
   for one project appear incorrect for the folder the user is looking at.
3. **Executable handoffs.** Preserve the specialist's structured action intent
   through manager integration. The current round trip through a canned chat query
   adds clicks and, for View data, only navigates to a populated form.
4. **Meaningful readiness and history.** Separate “check completed” from “ready to
   train/run”; add the relevant input/config/worker checks. Let old checks reopen
   their scope, task results and evidence. The scope selector also resets to Whole
   project when the panel remounts while still displaying the latest narrower run.

## Boundaries of this assessment

The tested workers are explicitly tool-backed; no LLM agent was invoked. This pass
used the original NucMM pair read-only, did not train a model, save new mask edits,
exercise cancellation, or induce a worker/server failure. Browsing the engineering
folder did not actually switch the active workflow. Therefore this pass does not
validate stale-result handling after a genuine project-artifact mutation; that
remains covered by the previous automated tests, not new browser evidence here.
The Network Error messages visible in old chat history predate this assessment;
none of the requests made in this browser pass produced a new network error.
