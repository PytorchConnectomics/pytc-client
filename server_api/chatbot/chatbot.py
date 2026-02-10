# Multi-agent chatbot system for PyTorch Connectomics.

# Architecture:
# - Supervisor Agent: Routes tasks to appropriate sub-agents
# - Training Agent: Handles config selection and training command generation
# - Inference Agent: Handles checkpoint listing and inference command generation
# - RAG: Documentation search via FAISS vector store

import os

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain.agents import create_agent
from server_api.utils.utils import process_path
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

CRITICAL RULES:
1. **Only state facts from retrieved documentation or tool output.** Do NOT invent features, shortcuts, buttons, or workflows that are not explicitly described in the retrieved context.
2. **If the documentation does not cover something, say so.** For example: "The documentation does not mention this feature."
3. **Answer every part of the user's question.** If they ask about two things, address both.
4. **Be concise.** Give clear, direct answers. Avoid filler phrases like "Happy proofreading!" or restating the same information in multiple formats.
5. **Do not fabricate keyboard shortcuts, API endpoints, or UI elements.** Only mention those explicitly listed in the retrieved docs.

Sub-agents available:
1. **Training Agent**: Config selection, training job setup, hyperparameter overrides
2. **Inference Agent**: Checkpoint management, inference/evaluation commands

Tools:
- search_documentation: Search PyTC docs for UI guides and feature explanations. Use this for any question about the application interface, pages, buttons, or workflows.
- delegate_to_training_agent: Send training-related tasks to training agent
- delegate_to_inference_agent: Send inference-related tasks to inference agent

When using search_documentation results:
- Base your entire answer on the returned text
- Quote specific details (shortcuts, endpoints, steps) exactly as they appear
- If the returned docs don't fully answer the question, state what is missing rather than guessing"""


def build_chain():
    """Build the multi-agent system with supervisor, training, and inference agents."""
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "mistral:latest")
    ollama_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "mistral:latest")
    llm = ChatOllama(model=ollama_model, base_url=ollama_base_url, temperature=0)
    embeddings = OllamaEmbeddings(model=ollama_embed_model, base_url=ollama_base_url)
    faiss_path = process_path("server_api/chatbot/faiss_index")
    vectorstore = FAISS.load_local(
        faiss_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

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
        print(f"[TOOL] search_documentation(query={query!r})")
        docs = retriever.invoke(query)
        if not docs:
            print("[TOOL] search_documentation → no results")
            return "No relevant documentation found."
        print(f"[TOOL] search_documentation → {len(docs)} docs: {[d.metadata.get('source', '?') for d in docs]}")
        return "\n\n".join([doc.page_content for doc in docs])

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
        response = messages[-1].content if messages else "Training agent did not respond."
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
        response = messages[-1].content if messages else "Inference agent did not respond."
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

    return supervisor, None
