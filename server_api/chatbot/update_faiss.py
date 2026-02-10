# How to update faiss_index:
#     1. Edit the markdown files in server_api/chatbot/file_summaries/ as needed.
#        These are end-user-focused guides (one per application page/feature) that
#        serve as the knowledge base for the RAG chatbot.
#     2. Run this script:
#         python server_api/chatbot/update_faiss.py
#
#     You can override the embeddings model and Ollama base URL via:
#     - Environment variables: OLLAMA_EMBED_MODEL, OLLAMA_BASE_URL
#     - CLI arguments: --model, --base-url

import os
import argparse
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

def main():
    # Parse CLI arguments
    parser = argparse.ArgumentParser(
        description="Update FAISS index for RAG chatbot documentation search"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama embeddings model (default: from OLLAMA_EMBED_MODEL env or 'qwen3-embedding:8b')",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Ollama base URL (default: from OLLAMA_BASE_URL env or 'http://localhost:11434')",
    )
    args = parser.parse_args()

    # Use same defaults as build_chain() in chatbot.py
    embed_model = args.model or os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
    base_url = args.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    print(f"Using embeddings model: {embed_model}")
    print(f"Using Ollama base URL: {base_url}")

    script_directory = Path(__file__).parent.resolve()
    summaries_directory = script_directory / "file_summaries"
    faiss_directory = script_directory / "faiss_index"

    # Load full documents
    documents = []
    for md_file in summaries_directory.rglob("*.md"):
        summary = md_file.read_text(encoding="utf-8")
        relative_path = md_file.relative_to(summaries_directory)
        documents.append(
            Document(
                page_content=summary,
                metadata={"source": str(relative_path)},
            )
        )

    # Split into chunks for better embedding quality
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} docs into {len(chunks)} chunks")
    for c in chunks:
        print(f"  - {c.metadata['source']} (start={c.metadata.get('start_index', '?')}, {len(c.page_content)} chars)")

    embeddings = OllamaEmbeddings(model=embed_model, base_url=base_url)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    faiss_directory.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(faiss_directory))
    print(f"FAISS index saved with {vectorstore.index.ntotal} vectors")


if __name__ == "__main__":
    main()
