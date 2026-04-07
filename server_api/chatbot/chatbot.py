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
from server_api.chatbot.update_faiss import ensure_faiss_index
from server_api.chatbot.tools import (
    list_training_configs,
    read_config,
    list_checkpoints,
)

TRAINING_AGENT_PROMPT = """You are a **Training Agent** for PyTorch Connectomics.

You help users set up and configure training jobs for biomedical image segmentation.

CRITICAL RULES:
1. **Only report values that your tools return.** Do NOT invent hyperparameter values, config names, or file paths.
2. **Always use tools before answering.** Call list_training_configs or read_config first — never guess.
3. **Be concise.** Report the facts, generate the command, and stop.

Tools:
- list_training_configs: List available config files with descriptions
- read_config: Read a config file to see its hyperparameters

Workflow:
1. Use list_training_configs to find configs matching user's task
2. Use read_config to examine the config's current settings
3. Compare user requirements with config defaults
4. Generate the training command with appropriate overrides

Command Format:
```
python scripts/main.py --config <config_path> [OVERRIDES]
```

Overrides use YAML key paths appended to the command: SECTION.KEY=value
Example:
```
python scripts/main.py --config configs/Lucchi-Mitochondria.yaml SOLVER.BASE_LR=0.001 SOLVER.SAMPLES_PER_BATCH=16
```
Use read_config output to determine the correct key paths for any parameter.

Always generate commands for the user to run - never execute directly."""


INFERENCE_AGENT_PROMPT = """You are an **Inference Agent** for PyTorch Connectomics.

You help users run inference and evaluation with trained segmentation models.

CRITICAL RULES:
1. **Only report values that your tools return.** Do NOT invent checkpoint paths, config names, or settings.
2. **Always use tools before answering.** Call list_checkpoints or read_config first — never guess.
3. **Be concise.** Report the facts, generate the command, and stop.

Tools:
- list_checkpoints: Find available trained model checkpoints
- read_config: Read config to find default inference settings

Workflow:
1. Use list_checkpoints to find available models
2. Use read_config to check inference settings (INFERENCE section)
3. Generate the inference command

Command Format:
```
python scripts/main.py --config <config_path> --checkpoint <checkpoint_path> --inference [OVERRIDES]
```

Overrides use YAML key paths appended to the command: SECTION.KEY=value
Example:
```
python scripts/main.py --config configs/Lucchi-Mitochondria.yaml --checkpoint outputs/Lucchi/checkpoint_100000.pth --inference INFERENCE.OUTPUT_PATH=/path/to/output
```
Use read_config output to determine the correct key paths for any parameter.

Always generate commands for the user to run - never execute directly."""


SUPERVISOR_PROMPT = """You are the **Supervisor Agent** for PyTorch Connectomics (PyTC Client).

You help end users navigate and use the PyTC Client application.

ROUTING — decide which tool to use BEFORE calling anything:
- **UI, navigation, features, shortcuts, workflows, "how do I..." questions** → search_documentation
- **Generate a specific training/inference command** → delegate_to_training_agent or delegate_to_inference_agent
- **General/greeting/off-topic** → answer directly, no tool needed

CRITICAL RULES:
1. **ALWAYS search documentation first for UI questions.** If the user asks "how do I train", "what do I need to provide", "how do I start", "where do I configure", etc., use search_documentation to find the UI workflow in the docs. Do NOT delegate to sub-agents for these questions.
2. **Only delegate to sub-agents when the user explicitly asks you to generate a command.** Examples: "give me the training command for...", "write the inference command for...", "what's the CLI command to...". If they're asking HOW to use the UI, search the docs instead.
3. **For application questions, ground answers in retrieved documentation.** Call search_documentation and base your answer on the returned text. Do NOT invent features, shortcuts, buttons, or workflows.
4. **Do not fabricate specifics.** Never make up keyboard shortcuts, button labels, or step-by-step instructions unless they come from retrieved docs or a sub-agent response.
4a. **NEVER use command-line instructions for UI questions.** The PyTC Client is a desktop GUI application. If the user asks how to do something, explain the UI workflow (buttons, tabs, forms) from the documentation. Do NOT provide Python scripts, bash commands, or CLI examples unless the sub-agent explicitly generates them.
5. **Answer every part of the user's question.** If they ask about two things, address both.
6. **Use retrieved content even if wording differs.** If the documentation describes relevant features or workflows, use that information to answer the question. Don't claim something isn't documented just because it uses different terminology than the user's question.
7. **HARD LIMIT: You may call search_documentation EXACTLY 2 times per user question.** After the second call, you MUST answer with the information already retrieved. Do NOT attempt a third search. If the tool returns "Search limit reached", immediately stop and answer based on what you already have.

Sub-agents:
- **Training Agent**: Config selection, training job setup, hyperparameter overrides
- **Inference Agent**: Checkpoint management, inference/evaluation commands

Tools:
- search_documentation: Search PyTC docs for UI guides and feature explanations. Use ONLY for questions about the application interface, pages, buttons, or workflows.
- delegate_to_training_agent: Send training-related tasks to training agent
- delegate_to_inference_agent: Send inference-related tasks to inference agent"""


def build_chain():
    """Build the multi-agent system with supervisor, training, and inference agents."""
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://cscigpu08.bc.edu:4443")
    ollama_model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    ollama_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
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

    training_agent = create_agent(
        model=llm,
        tools=[list_training_configs, read_config],
        system_prompt=TRAINING_AGENT_PROMPT,
    )

    inference_agent = create_agent(
        model=llm,
        tools=[list_checkpoints, read_config],
        system_prompt=INFERENCE_AGENT_PROMPT,
    )

    @tool
    def search_documentation(query: str) -> str:
        """
        Search PyTC documentation for how-to guides, UI explanations, and feature descriptions.
        Use this for questions about the application interface or general usage.

        Args:
            query: The user's question

        Returns:
            Relevant documentation content
        """
        _search_call_count[0] += 1
        print(
            f"[TOOL] search_documentation(query={query!r}) [call {_search_call_count[0]}]"
        )
        if _search_call_count[0] > 2:
            print("[TOOL] search limit reached (max 2 per question)")
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
        result = training_agent.invoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        messages = result.get("messages", [])
        response = (
            messages[-1].content if messages else "Training agent did not respond."
        )
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

HELPER_PROMPT = """You are a concise UI helper for PyTorch Connectomics (PyTC Client).

You answer questions about a SPECIFIC field or setting the user is looking at.
You have access to the application documentation via the search_documentation tool.

RULES:
1. Lead with a concrete recommendation or explanation (2-4 sentences max).
2. Use plain, non-technical language — the user has no programming knowledge.
3. Describe things in terms of what users can see and click in the interface.
4. If you have enough context, recommend a specific value or action.
5. Do NOT mention API endpoints, code, environment variables, or internal implementation.
6. You may call search_documentation up to 2 times per question — then answer with what you have.
7. You CANNOT start training or inference jobs. If the user asks, tell them to use the main AI Chat panel instead."""


def build_helper_chain():
    """
    Build a lightweight helper agent for inline field-level help.
    This agent has access to the same search_documentation tool as the main
    chatbot but has NO access to training/inference sub-agents.
    Returns ``(agent, reset_search_counter)`` — same interface as ``build_chain``.
    """
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://cscigpu08.bc.edu:4443")
    ollama_model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    ollama_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
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
