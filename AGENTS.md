# Active prototype

This branch continues the May 5 app baseline (`c151bf9571a0bfba924df9195dad470839e26b1e`).
Read `docs/agent-reset-handoff.md` and `docs/agent-team-model-layer.md` first.

The current direction is a project manager coordinating data, annotation and model
specialists using scoped project context, read-only inspection tools, persisted
results and existing app action controls. The later DSL/DAG integration was retired
from this implementation direction. Do not restore it as a requirement without a
new user request.

Use the NucMM image/label crop as the demo test bed. Distinguish published reference
labels, saved edits, engineering smoke runs and scientific validation. The two-step
CPU preset does not demonstrate useful model quality. Generated model summaries
can overstate tool evidence; task completion is not biological validation.

Keep datasets, local databases, environments, model weights, logs and recordings
out of commits. Seed an empty demo database before opening the app. The seed script
retains any existing guest workflow; it is not a reset or a migration utility.

The launcher binds to localhost and the app has a shared guest fallback. A local
working demo is not a public deployment. Check the intended host, access controls,
browser API origin and Neuroglancer URL routing before any hosted deployment.
