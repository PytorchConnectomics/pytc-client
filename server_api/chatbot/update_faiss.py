# How to update faiss_index:
#     1. Edit the markdown files in server_api/chatbot/file_summaries/ as needed.
#        These are end-user-focused guides (one per application page/feature) that
#        serve as the knowledge base for the RAG chatbot.
#     2. Run this script:
#         python server_api/chatbot/update_faiss.py

from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

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

embeddings = OllamaEmbeddings(
    model="qwen3-embedding:8b", base_url="http://cscigpu08.bc.edu:11434"
)
vectorstore = FAISS.from_documents(chunks, embeddings)
faiss_directory.mkdir(parents=True, exist_ok=True)
vectorstore.save_local(str(faiss_directory))
print(f"FAISS index saved with {vectorstore.index.ntotal} vectors")
