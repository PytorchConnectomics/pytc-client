# Multi-agent chatbot system for PyTorch Connectomics.

# Architecture:
# - Supervisor Agent: Routes tasks to appropriate sub-agents
# - Training Agent: Handles config selection and training command generation
# - Inference Agent: Handles checkpoint listing and inference command generation
# - RAG: Documentation search via FAISS vector store

import os
from pathlib import Path

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain.agents import create_agent
from server_api.utils.utils import process_path
from server_api.chatbot.update_faiss import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_EMBED_MODEL,
    ensure_faiss_index,
)
from server_api.chatbot.tools import (
    list_training_configs,
    read_config,
    list_checkpoints,
)

DEFAULT_OLLAMA_MODEL = "llama3.1:8b"

AGENT_RESPONSE_STYLE = """
RESPONSE STYLE FOR BIOLOGISTS:
- Default to 3 bullets or fewer. Maximum 90 words unless the user asks for detail.
- Put the recommended next action first.
- Use short labels like `Do this`, `Why`, and `Watch out`.
- Avoid long background explanations, exhaustive lists, and implementation details.
- Do not mention internal tools, agents, RAG, prompts, APIs, or code unless explicitly asked.
- If a command is requested, provide one command plus at most one sentence of context.
- If uncertainty matters, state the missing input in one sentence and stop.
"""


def _format_admin_llm_error(error: Exception) -> str:
    return (
        "The AI assistant could not connect to its configured language model. "
        "Please contact your system administrator with this error: "
        f"{str(error).strip() or error.__class__.__name__}"
    )


def _compact_agent_response(response: str, *, max_words: int = 120) -> str:
    text = str(response or "").strip()
    if not text:
        return text

    lines = [line.rstrip() for line in text.splitlines()]
    content_lines = [line for line in lines if line.strip()]
    words = text.split()
    if len(words) <= max_words and len(content_lines) <= 8:
        return text
    if "```" in text and len(words) <= (max_words * 2) and len(content_lines) <= 8:
        return text

    kept = []
    word_count = 0
    for line in content_lines:
        line_words = line.split()
        if word_count + len(line_words) > max_words:
            break
        kept.append(line)
        word_count += len(line_words)
        if len(kept) >= 6:
            break
    compacted = "\n".join(kept).strip()
    if not compacted:
        compacted = " ".join(words[:max_words]).strip()
    return f"{compacted}\n\nAsk for details if you want the full version."


_PROMPT_LEAK_MARKERS = [
    "you are the **supervisor agent**",
    "you are the supervisor agent",
    "response style for biologists",
    "routing — decide which tool",
    "routing - decide which tool",
    "critical rules:",
    "sub-agents:",
    "tools:",
    "search_documentation:",
    "delegate_to_training_agent",
    "delegate_to_inference_agent",
    "system_prompt",
    "internal tools",
]


def _looks_like_prompt_leak(response: str) -> bool:
    text = str(response or "").lower()
    return any(marker in text for marker in _PROMPT_LEAK_MARKERS)


def _sanitize_agent_response(response: str) -> str:
    text = str(response or "").strip()
    if not text:
        return text
    if not _looks_like_prompt_leak(text):
        return text
    return (
        "Hi. I can help with the PyTC workflow.\n"
        "Do this: tell me whether you want to run the model, proofread masks, "
        "use saved edits for training, or compare results.\n"
        "Watch out: I will ask before running long jobs or changing artifacts."
    )


def _resolve_ollama_settings():
    return (
        os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_OLLAMA_EMBED_MODEL),
    )


TRAINING_AGENT_PROMPT = f"""You are a **Training Agent** for PyTorch Connectomics.

{AGENT_RESPONSE_STYLE}

RULES:
1. Only report values that your tools return. Do NOT invent config names, paths, or settings.
2. Never tell the user to write a YAML from scratch. Always start from an existing config.
3. If the task is unsupported, say so. PyTC only does segmentation.
4. Be concise. State the facts and stop. Generate a CLI command only if the user explicitly asks for one.

WORKFLOW: The available configs are provided in your task message. Pick the best match, then:
1. Call read_config on the chosen config path to see its YAML overrides.
2. For common parameters (learning rate, batch size, iterations, optimizer, checkpoint interval), ALWAYS use the keys listed below. DO NOT search for these.
3. For specialized parameters (augmentation settings, loss functions, architecture details), call search_documentation.
4. Build the command with overrides using the SECTION.KEY=value format.

IMPORTANT: YAML configs only show overrides — many valid keys exist in the defaults but are not shown in read_config output.

Common override keys (ALWAYS use these exact keys, never search for alternatives):
- SOLVER.BASE_LR, SOLVER.SAMPLES_PER_BATCH, SOLVER.ITERATION_TOTAL
- SOLVER.ITERATION_SAVE (checkpoint save interval), SOLVER.ITERATION_STEP (LR decay steps)
- SOLVER.NAME (values: SGD, Adam, AdamW)
- SOLVER.LR_SCHEDULER_NAME (values: WarmupMultiStepLR, WarmupCosineLR)
- SOLVER.CLIP_GRADIENTS.ENABLED (True/False), SOLVER.CLIP_GRADIENTS.CLIP_VALUE
- MODEL.ARCHITECTURE, MODEL.BLOCK_TYPE, MODEL.FILTERS

NEVER invent keys like TRAIN.MAX_ITER, TRAINING.BATCH_SIZE, or CLI flags like --batch-size, --checkpoint-interval — these do not exist.

Command format, only when explicitly requested: `python scripts/main.py --config-file <path> [SECTION.KEY=value ...]`
Default app workflow: recommend agent-selected preset/defaults plus approval-gated training inside PyTC Client, not manual YAML tuning."""


INFERENCE_AGENT_PROMPT = f"""You are an **Inference Agent** for PyTorch Connectomics.

{AGENT_RESPONSE_STYLE}

RULES:
1. Only report values that your tools return. Do NOT invent checkpoint paths, config names, or settings.
2. Be concise. State the facts and stop. Generate a CLI command only if the user explicitly asks for one.

WORKFLOW:
1. If the user did NOT provide a checkpoint path, call list_checkpoints first to see available checkpoints.
2. If the user DID provide a checkpoint path (e.g., outputs/model/checkpoint.pth.tar), skip list_checkpoints.
3. Call read_config to see the INFERENCE section keys.
4. For specialized inference parameters, call search_documentation if needed.

Here is the correct override key mapping (use these exact keys):
- Output path → INFERENCE.OUTPUT_PATH
- TTA augmentation count → INFERENCE.AUG_NUM
- TTA mode → INFERENCE.AUG_MODE (values: mean, max)
- Blending → INFERENCE.BLENDING (values: gaussian, bump)
- Stride → INFERENCE.STRIDE
- Process volumes one at a time → INFERENCE.DO_SINGLY
- Batch size → INFERENCE.SAMPLES_PER_BATCH

Command format, only when explicitly requested: `python scripts/main.py --config-file <path> --inference --checkpoint <ckpt> [SECTION.KEY=value ...]`

IMPORTANT: Overrides use SECTION.KEY=value format (NO -- prefix). Example:
  ✅ CORRECT: INFERENCE.AUG_NUM=8
  ❌ WRONG: --inference.AUG_NUM=8

Default app workflow: recommend approval-gated inference inside PyTC Client, not manual stride/blending/chunking setup."""


SUPERVISOR_PROMPT = f"""You are the **Supervisor Agent** for PyTorch Connectomics (PyTC Client).

{AGENT_RESPONSE_STYLE}

You help end users navigate and use the PyTC Client application.

ROUTING — decide which tool to use BEFORE calling anything:
- **UI, navigation, features, shortcuts, workflows, "how do I..." questions** → search_documentation
- **General PyTC questions** (what architectures are supported, what augmentations exist, what loss functions are available, etc.) → search_documentation
- **Generate a specific training/inference command** → delegate_to_training_agent or delegate_to_inference_agent
- **General/greeting/off-topic** → answer directly, no tool needed
- **Run/segment/proofread/train/compare/export workflow jobs** → answer briefly that the app can do this through approval-gated workflow actions. Do not provide low-level tuning advice by default.

CRITICAL RULES:
1. **ALWAYS search documentation first for UI questions.** If the user asks "how do I train", "what do I need to provide", "how do I start", "where do I configure", etc., use search_documentation to find the UI workflow in the docs. Do NOT delegate to sub-agents for these questions.
2. **Only delegate to sub-agents when the user explicitly asks you to generate a command.** Examples: "give me the training command for...", "write the inference command for...", "what's the CLI command to...". If they're asking HOW to use the UI, search the docs instead.
3. **For application questions, ground answers in retrieved documentation.** Call search_documentation and base your answer on the returned text. Do NOT invent features, shortcuts, buttons, or workflows.
4. **Do not fabricate specifics.** Never make up keyboard shortcuts, button labels, or step-by-step instructions unless they come from retrieved docs or a sub-agent response.
4a. **NEVER use command-line instructions for UI questions.** The PyTC Client is a desktop GUI application. If the user asks how to do something, explain the UI workflow (buttons, tabs, forms) from the documentation. Do NOT provide Python scripts, bash commands, or CLI examples unless the sub-agent explicitly generates them.
4b. **NEVER fabricate file paths or scripts.** Do NOT invent scripts like `scripts/evaluate.py`, `scripts/resume_training.py`, or any other files that don't exist. If evaluation requires Python code, show inline code using `connectomics.utils.evaluate`, not fake script paths.
4c. **Do not lead with low-level YAML parameters for biologists.** For ordinary training or inference requests, say the assistant should infer safe defaults from the current project and ask for approval before running. Mention stride, blending, chunking, GPUs, CPUs, or iterations only when asked to override or debug.
5. **Answer every part of the user's question.** If they ask about two things, address both.
6. **Use retrieved content even if wording differs.** If the documentation describes relevant features or workflows, use that information to answer the question. Don't claim something isn't documented just because it uses different terminology than the user's question.
7. **HARD LIMIT: You may call search_documentation at most 3 times yourself.** Sub-agents also have access to search_documentation. If the tool returns "Search limit reached", immediately stop and answer based on what you already have.

Sub-agents:
- **Training Agent**: Config selection, training job setup, hyperparameter overrides
- **Inference Agent**: Checkpoint management, inference/evaluation commands

Tools:
- search_documentation: Search PyTC docs for UI guides, feature explanations, training/inference config references, model architectures, augmentation options, and bundled configs.
- delegate_to_training_agent: Send training-related tasks to training agent (config selection, command generation, hyperparameter tuning)
- delegate_to_inference_agent: Send inference-related tasks to inference agent (checkpoint listing, inference commands, evaluation setup)"""


def build_chain():
    """Build the multi-agent system with supervisor, training, and inference agents."""
    ollama_base_url, ollama_model, ollama_embed_model = _resolve_ollama_settings()
    llm = ChatOllama(model=ollama_model, base_url=ollama_base_url, temperature=0)
    embeddings = OllamaEmbeddings(model=ollama_embed_model, base_url=ollama_base_url)
    faiss_path = process_path("server_api/chatbot/faiss_index")
    if ensure_faiss_index(
        model=ollama_embed_model,
        base_url=ollama_base_url,
    ):
        print(f"[SEARCH] Generated chatbot FAISS index at {faiss_path}")
    vectorstore = FAISS.load_local(
        faiss_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    # Load all docs from markdown files for reliable keyword search
    summaries_dir = Path(process_path("server_api/chatbot/file_summaries"))
    _all_docs = {}
    for md_file in summaries_dir.rglob("*.md"):
        _all_docs[md_file.name] = md_file.read_text(encoding="utf-8")
    print(
        f"[SEARCH] Loaded {len(_all_docs)} docs for keyword search: {list(_all_docs.keys())}"
    )

    # Call counter to prevent infinite search loops (reset before each user message)
    _search_call_count = [0]

    def reset_search_counter():
        _search_call_count[0] = 0

    @tool
    def search_documentation(query: str) -> str:
        """
        Search PyTC documentation for UI guides, feature descriptions, training/inference
        configuration references, model architectures, augmentation options, and bundled configs.

        Args:
            query: The user's question

        Returns:
            Relevant documentation content
        """
        _search_call_count[0] += 1
        print(
            f"[TOOL] search_documentation(query={query!r}) [call {_search_call_count[0]}]"
        )
        if _search_call_count[0] > 6:
            print("[TOOL] search limit reached (max 6 per question)")
            return "Search limit reached. Please answer based on the documentation already retrieved."

        # Primary: FAISS semantic search (chunked embeddings)
        docs = retriever.invoke(query)
        if docs:
            sources = [d.metadata.get("source", "?") for d in docs]
            print(f"[TOOL] RAG → {len(docs)} chunks: {sources}")
            return "\n\n".join([doc.page_content for doc in docs])

        # Fallback: keyword scoring against full docs
        print("[TOOL] RAG returned nothing, trying keyword fallback")
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        scored = []
        for filename, content in _all_docs.items():
            content_lower = content.lower()
            name_lower = filename.replace(".md", "").lower()
            word_hits = sum(1 for w in query_words if w in content_lower)
            name_hits = sum(3 for w in query_words if w in name_lower)
            score = word_hits + name_hits
            if score > 0:
                scored.append((score, filename, content))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            top = scored[:3]
            print(f"[TOOL] keyword fallback → {len(top)} docs: {[s[1] for s in top]}")
            return "\n\n".join([s[2] for s in top])

        print("[TOOL] search_documentation → no results")
        return "No relevant documentation found."

    training_agent = create_agent(
        model=llm,
        tools=[list_training_configs, read_config, search_documentation],
        system_prompt=TRAINING_AGENT_PROMPT,
    )

    inference_agent = create_agent(
        model=llm,
        tools=[list_checkpoints, read_config, search_documentation],
        system_prompt=INFERENCE_AGENT_PROMPT,
    )

    @tool
    def delegate_to_training_agent(task: str) -> str:
        """
        Delegate a training-related task to the Training Agent.
        Use this for: config selection, training setup, hyperparameter questions.

        Args:
            task: Description of what the training agent should do

        Returns:
            Response from the training agent
        """
        print(f"[TOOL] delegate_to_training_agent(task={task!r})")
        # Auto-inject available configs so the agent doesn't need to call list_training_configs
        configs = list_training_configs.invoke({})
        config_summary = "\n".join(
            f"- {c['name']} ({c['model']}) → {c['path']}"
            for c in configs
            if isinstance(c, dict) and "name" in c
        )
        enriched_task = (
            f"{task}\n\n"
            f"AVAILABLE CONFIGS (already fetched for you):\n{config_summary}\n\n"
            f"Pick the best match and call read_config on its path to see the exact YAML keys before generating the command."
        )
        result = training_agent.invoke(
            {"messages": [{"role": "user", "content": enriched_task}]}
        )
        messages = result.get("messages", [])
        response = (
            messages[-1].content if messages else "Training agent did not respond."
        )
        response = _compact_agent_response(response)
        print(f"[TOOL] training_agent responded ({len(response)} chars)")
        return response

    @tool
    def delegate_to_inference_agent(task: str) -> str:
        """
        Delegate an inference/evaluation task to the Inference Agent.
        Use this for: checkpoint listing, inference commands, evaluation setup.

        Args:
            task: Description of what the inference agent should do

        Returns:
            Response from the inference agent
        """
        print(f"[TOOL] delegate_to_inference_agent(task={task!r})")
        result = inference_agent.invoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        messages = result.get("messages", [])
        response = (
            messages[-1].content if messages else "Inference agent did not respond."
        )
        response = _compact_agent_response(response)
        print(f"[TOOL] inference_agent responded ({len(response)} chars)")
        return response

    supervisor_tools = [
        search_documentation,
        delegate_to_training_agent,
        delegate_to_inference_agent,
    ]

    supervisor = create_agent(
        model=llm,
        tools=supervisor_tools,
        system_prompt=SUPERVISOR_PROMPT,
    )

    return supervisor, reset_search_counter


# ---------------------------------------------------------------------------
# Helper chat: lightweight RAG-only agent for inline "?" help popovers.
# Has access to search_documentation only — cannot start training/inference.
# ---------------------------------------------------------------------------

HELPER_PROMPT = f"""You are a concise UI helper for PyTorch Connectomics (PyTC Client).

{AGENT_RESPONSE_STYLE}

You answer questions about a SPECIFIC field or setting the user is looking at.
You have access to the application documentation via the search_documentation tool.

RULES:
1. Lead with a concrete recommendation or explanation (3 short bullets or fewer).
2. Use plain, non-technical language — the user has no programming knowledge.
3. Describe things in terms of what users can see and click in the interface.
4. If you have enough context, recommend a specific value or action.
5. Do NOT mention API endpoints, code, environment variables, or internal implementation.
6. Do NOT paste documentation headings, excerpts, or "Relevant local docs" blocks.
7. You CANNOT start training or inference jobs. If the user asks, tell them to use the main AI Chat panel instead."""


def build_helper_chain():
    """
    Build a lightweight helper agent for inline field-level help.
    This agent has access to the same search_documentation tool as the main
    chatbot but has NO access to training/inference sub-agents.
    Returns ``(agent, reset_search_counter)`` — same interface as ``build_chain``.
    """
    ollama_base_url, ollama_model, ollama_embed_model = _resolve_ollama_settings()
    llm = ChatOllama(model=ollama_model, base_url=ollama_base_url, temperature=0)
    embeddings = OllamaEmbeddings(model=ollama_embed_model, base_url=ollama_base_url)
    faiss_path = process_path("server_api/chatbot/faiss_index")
    if ensure_faiss_index(
        model=ollama_embed_model,
        base_url=ollama_base_url,
    ):
        print(f"[SEARCH] Generated chatbot FAISS index at {faiss_path}")
    vectorstore = FAISS.load_local(
        faiss_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    # Keyword fallback docs (same pattern as main chatbot)
    summaries_dir = Path(process_path("server_api/chatbot/file_summaries"))
    _all_docs = {}
    for md_file in summaries_dir.rglob("*.md"):
        _all_docs[md_file.name] = md_file.read_text(encoding="utf-8")

    _search_call_count = [0]

    def reset_search_counter():
        _search_call_count[0] = 0

    @tool
    def search_documentation(query: str) -> str:
        """Search PyTC documentation for UI guides, field explanations, and feature descriptions.

        Args:
            query: The user's question

        Returns:
            Relevant documentation content
        """
        _search_call_count[0] += 1
        if _search_call_count[0] > 2:
            return (
                "Search limit reached. Answer with the documentation already retrieved."
            )

        docs = retriever.invoke(query)
        if docs:
            return "\n\n".join([doc.page_content for doc in docs])

        # Keyword fallback
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        scored = []
        for filename, content in _all_docs.items():
            content_lower = content.lower()
            name_lower = filename.replace(".md", "").lower()
            word_hits = sum(1 for w in query_words if w in content_lower)
            name_hits = sum(3 for w in query_words if w in name_lower)
            score = word_hits + name_hits
            if score > 0:
                scored.append((score, filename, content))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            return "\n\n".join([s[2] for s in scored[:3]])

        return "No relevant documentation found."

    helper_agent = create_agent(
        model=llm,
        tools=[search_documentation],
        system_prompt=HELPER_PROMPT,
    )

    return helper_agent, reset_search_counter
