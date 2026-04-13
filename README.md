# PyTC Client

A desktop client that interacts with the `pytorch_connectomics` library for connectomics workflows.

This file only contains instructions on running the application. For a high-level description of the project structure, see `project-structure.md`.

## Set-up

Install `uv` and `node`:

```
brew install uv node                    # macOS / Linux
winget install Astral.uv OpenJS.NodeJS  # Windows
```

Install dependencies:

```
scripts/bootstrap.sh      # macOS / Linux
scripts\bootstrap.ps1     # Windows
```

Re-run the relevant bootstrap script when you need to update dependencies.

## Run the app

```
scripts/start.sh          # macOS / Linux
scripts\start.ps1         # Windows
```

Optional runtime environment variables:

```
PYTC_AUTH_SECRET=replace-me
PYTC_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,null
PYTC_NEUROGLANCER_PUBLIC_BASE=http://localhost:4244
```

## Chatbot Docs Index

The chatbot's FAISS index is generated locally from the markdown files in
`server_api/chatbot/file_summaries/` and should not be committed to git.

When you update those markdown docs, rebuild the generated index with:

```
uv run python server_api/chatbot/update_faiss.py
```

You can override the embeddings endpoint if needed:

```
OLLAMA_BASE_URL=http://cscigpu08.bc.edu:4443 uv run python server_api/chatbot/update_faiss.py
```

If restarting after a crash or interrupted session, kill any lingering processes first:

```
lsof -ti:8000 | xargs kill -9   # macOS / Linux
```

## Before pushing changes

Format most code with `prettier`:

```
npm install
npx prettier --write .
```

Format python code with `black`:

```
uv run black .
```

Format shell scripts with `shfmt` (macOS / Linux):

```
brew install shfmt
shfmt -w .
```
