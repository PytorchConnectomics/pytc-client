# Known Issues

This file lists issues observed during the PyTC v2 stabilization pass that are not yet fixed in the current branch.

## High Priority

### Image and label selectors still accept directories

Files:

- `client/src/components/InputSelector.js`
- `client/src/components/YamlFileUploader.js`
- `client/src/utils.js`

Impact:

- users can select a directory for image or label instead of a concrete file
- the UI can then display a plausible-looking dataset summary while the effective image or label name is wrong
- this is a real source of confusion during training and inference setup

Recommendation:

- change image and label selectors to file-only mode
- validate file selection before mutating YAML

### Stop behavior is broader than ideal

File:

- `server_pytc/services/model.py`

Impact:

- `stop_training()` and `stop_inference()` terminate the tracked process and then also kill processes by substring match
- on a machine doing other PyTC work, that can terminate unrelated local jobs
- forced shutdown often ends with exit code `-9`

Recommendation:

- narrow stop behavior to the tracked child process tree only
- avoid broad process-name matching where possible

## Medium Priority

### PyTC can still surface interactive prompts on bad configs

Files:

- `server_pytc/services/model.py`
- `pytorch_connectomics/connectomics/utils/errors.py`

Impact:

- PyTC contains an interactive `Continue anyway? [y/N]:` path on config issues
- the new runtime log panel makes this visible, but the app still does not proactively harden against it

Recommendation:

- force a deterministic non-interactive stdin mode for subprocesses or add stricter preflight validation before launch

### Effective dataset summary is advisory, not authoritative

File:

- `client/src/components/YamlFileUploader.js`

Impact:

- the "Effective dataset paths" card is derived from current context state
- it is useful, but it is not a direct rendering of the final exact YAML payload that gets posted

Recommendation:

- either compute the card from the fully prepared launch payload or label it more explicitly as a derived preview

## Lower Priority / Non-Blocking for Demo

### Electron security warnings are still present in dev

Impact:

- developer console shows Electron security warnings in the current development flow
- this does not block a demo, but it is not a hardened production posture

### Existing frontend lint warnings remain

Impact:

- `npm --prefix client run build` passes, but with pre-existing ESLint warnings in unrelated files
- these are not introduced by the stabilization branch and are not current demo blockers
