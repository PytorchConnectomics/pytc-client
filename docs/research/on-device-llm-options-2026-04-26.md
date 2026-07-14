# On-Device LLM Options - 2026-04-26

Purpose: keep the PyTC Client assistant local-first while improving workflow
reasoning beyond the old `llama3.2:1b` default.

## Current Implementation Decision

- Immediate default: `llama3.1:8b`, because it is already installed on this
  development machine and is a major quality jump over the 1B default.
- Embeddings remain `nomic-embed-text:latest`.
- Rebuild the FAISS index after editing `server_api/chatbot/file_summaries/`.

## Models To Evaluate Next

| Model | Why It Matters | Tradeoff | Status |
| --- | --- | --- | --- |
| `qwen3:4b` | Ollama lists it at 2.5GB with a 256K context window; useful candidate for fast local workflow chat. | Needs local pull and behavioral testing. | Evaluate |
| `qwen3:8b` | Larger Qwen3 local text model, 5.2GB and 40K context. | More memory/latency than 4B. | Evaluate |
| `gemma3:4b` | Ollama lists Gemma 3 as multimodal with 128K context; 4B is 3.3GB. | Multimodal support is not yet integrated into PyTC Client. | Evaluate |
| `phi4-mini` | Ollama describes it as memory/compute constrained and latency-bound, with 128K context. | Requires Ollama 0.5.13+ and should be tested for UI-agent instruction following. | Evaluate |
| llama.cpp / GGUF | Strong fallback runtime path; official repo supports Metal for Apple Silicon. | More integration work than Ollama. | Future runtime option |

## Product Takeaway

Model choice is not enough. The bad interaction came from letting general RAG
answer workflow/meta questions. The robust fix is layered:

- deterministic workflow router for run/proofread/train/compare/status intents;
- direct guards for gibberish and meta questions such as "did you run?";
- documentation that says low-level YAML/stride/blending is advanced-only;
- stronger local model for the remaining general assistant path.

## Sources

- Ollama Qwen3 model library: https://ollama.com/library/qwen3
- Ollama Gemma 3 model library: https://ollama.com/library/gemma3
- Ollama Phi-4 Mini model library: https://ollama.com/library/phi4-mini
- llama.cpp supported backends: https://github.com/ggml-org/llama.cpp
