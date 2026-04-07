import argparse
import os
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_OLLAMA_BASE_URL = "http://cscigpu08.bc.edu:4443"
DEFAULT_OLLAMA_EMBED_MODEL = "qwen3-embedding:8b"
INDEX_FILENAMES = ("index.faiss", "index.pkl")


def get_chatbot_paths(base_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    root = (base_dir or Path(__file__).parent).resolve()
    return root / "file_summaries", root / "faiss_index"


def resolve_ollama_settings(
    model: Optional[str] = None, base_url: Optional[str] = None
) -> Tuple[str, str]:
    embed_model = model or os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_OLLAMA_EMBED_MODEL)
    resolved_base_url = base_url or os.getenv(
        "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL
    )
    return embed_model, resolved_base_url


def faiss_index_exists(faiss_directory: Path) -> bool:
    return all((faiss_directory / name).is_file() for name in INDEX_FILENAMES)


def build_faiss_index(
    summaries_directory: Path,
    faiss_directory: Path,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
):
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_ollama import OllamaEmbeddings

    embed_model, resolved_base_url = resolve_ollama_settings(model, base_url)

    print(f"Using embeddings model: {embed_model}")
    print(f"Using Ollama base URL: {resolved_base_url}")

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

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} docs into {len(chunks)} chunks")
    for c in chunks:
        print(
            f"  - {c.metadata['source']} (start={c.metadata.get('start_index', '?')}, {len(c.page_content)} chars)"
        )

    embeddings = OllamaEmbeddings(model=embed_model, base_url=resolved_base_url)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    faiss_directory.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(faiss_directory))
    print(f"FAISS index saved with {vectorstore.index.ntotal} vectors")


def ensure_faiss_index(
    *,
    summaries_directory: Optional[Path] = None,
    faiss_directory: Optional[Path] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> bool:
    default_summaries_directory, default_faiss_directory = get_chatbot_paths()
    summaries_directory = summaries_directory or default_summaries_directory
    faiss_directory = faiss_directory or default_faiss_directory

    if faiss_index_exists(faiss_directory):
        return False

    build_faiss_index(
        summaries_directory,
        faiss_directory,
        model=model,
        base_url=base_url,
    )
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild the generated FAISS index for chatbot documentation search"
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Ollama embeddings model "
            f"(default: OLLAMA_EMBED_MODEL or '{DEFAULT_OLLAMA_EMBED_MODEL}')"
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Ollama base URL "
            f"(default: OLLAMA_BASE_URL or '{DEFAULT_OLLAMA_BASE_URL}')"
        ),
    )
    args = parser.parse_args()

    summaries_directory, faiss_directory = get_chatbot_paths()
    build_faiss_index(
        summaries_directory,
        faiss_directory,
        model=args.model,
        base_url=args.base_url,
    )


if __name__ == "__main__":
    main()
