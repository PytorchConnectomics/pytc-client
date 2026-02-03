import os

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_classic.prompts import ChatPromptTemplate
from server_api.utils.utils import process_path


SYSTEM_PROMPT = """
    You are a helpful AI assistant for the PyTorch Connectomics client, designed to help non-technical users navigate and use the application effectively.
    IMPORTANT GUIDELINES:
    - You are helping end-users who have no programming knowledge
    - Focus on what users can see and do in the interface, not technical implementation details
    - Provide concise, step-by-step instructions for using the platform
    - Explain features in terms of user actions (clicking buttons, navigating menus, etc.)
    - Avoid technical jargon, API endpoints, or code-related explanations
    - Always recommend a specific setting/value when you have enough context
    - Keep responses short and reassuring (2-4 short sentences max)
    - Lead with the recommendation first, then 1-2 reasons
    - Avoid long lists unless explicitly asked
    EXAMPLES OF GOOD vs BAD RESPONSES:
    BAD: "You need to set the isTraining boolean to true and call the start_model_training endpoint"
    GOOD: "To start training a model, go to the 'Model Training' tab, configure your training parameters using the step-by-step wizard, then click the 'Start Training' button"
    BAD: "Access the /neuroglancer endpoint with image and label paths"
    GOOD: "To visualize your data, first upload your image and label files using the drag-and-drop area, then select them from the dropdown menus, enter the voxel scales, and click 'Visualize'"
    BAD: "The trainingStatus state variable tracks the current training progress"
    GOOD: "You can monitor your training progress by checking the status message below the training buttons, or by going to the 'Tensorboard' tab to see detailed metrics"
    Remember: Help users navigate the no-code interface, not understand the underlying technical architecture.
    Project context:
    {project_context}

    Task context:
    {task_context}

    Retrieved docs/context:
    {context}
"""


_VECTORSTORE = None
_EMBEDDINGS = None


def _get_vectorstore(ollama_model: str, ollama_base_url: str):
    global _VECTORSTORE, _EMBEDDINGS
    if _VECTORSTORE is not None and _EMBEDDINGS is not None:
        return _VECTORSTORE, _EMBEDDINGS
    embeddings = OllamaEmbeddings(model=ollama_model, base_url=ollama_base_url)
    faiss_path = process_path("server_api/chatbot/faiss_index")
    vectorstore = FAISS.load_local(
        faiss_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    _VECTORSTORE = vectorstore
    _EMBEDDINGS = embeddings
    return vectorstore, embeddings


def build_chain(project_context: str = "", task_context: str = ""):
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    vectorstore, embeddings = _get_vectorstore(ollama_model, ollama_base_url)
    retriever = vectorstore.as_retriever()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PROMPT.format(
                    project_context=project_context or "Not provided.",
                    task_context=task_context or "Not provided.",
                    context="{context}",
                ),
            ),
            ("human", "{question}"),
        ]
    )
    llm = ChatOllama(model=ollama_model, base_url=ollama_base_url, temperature=0)
    memory = ConversationBufferMemory(
        return_messages=True,
        memory_key="chat_history",
    )
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": prompt},
    )
    return chain, memory
