"""
RAG Retrieval Evaluation Script
Tests whether FAISS retrieval returns the correct source document for each question.
Updated for the current 7-doc set (MaskProofreading replaces ErrorHandlingTool + WormErrorHandling).

This is a standalone utility script, not a pytest test module.
"""

import os
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

FAISS_DIR = Path(__file__).parent / "faiss_index"

QUESTIONS = [
    # ── GettingStarted.md ───────────────────────────────────────────────
    ("What is PyTC Client?", "GettingStarted.md", "easy"),
    ("How do I launch the application?", "GettingStarted.md", "easy"),
    ("What tabs are in the top navigation bar?", "GettingStarted.md", "easy"),
    ("How do I open the AI chat?", "GettingStarted.md", "easy"),
    ("What workflows are available in PyTC Client?", "GettingStarted.md", "easy"),
    ("How do I start a new chat conversation?", "GettingStarted.md", "medium"),
    ("Can I save my chat history?", "GettingStarted.md", "medium"),
    ("How do I delete a past conversation?", "GettingStarted.md", "medium"),
    ("What does the + button in the chat do?", "GettingStarted.md", "medium"),
    ("How do I collapse the chat sidebar?", "GettingStarted.md", "medium"),
    ("What are the ? buttons next to config fields?", "GettingStarted.md", "medium"),
    ("How does inline help work?", "GettingStarted.md", "medium"),
    ("Can I resize the chat drawer?", "GettingStarted.md", "hard"),
    (
        "Where can I find my previous conversations with the assistant?",
        "GettingStarted.md",
        "hard",
    ),
    (
        "If I want context-specific guidance on a parameter, what UI element should I click?",
        "GettingStarted.md",
        "hard",
    ),
    (
        "Is there a way to get AI recommendations for individual settings without opening the main chat?",
        "GettingStarted.md",
        "hard",
    ),
    # ── FileManager.md ──────────────────────────────────────────────────
    ("How do I upload files to the server?", "FileManager.md", "easy"),
    ("How do I create a new folder in the file manager?", "FileManager.md", "easy"),
    ("What is the context menu in the file manager?", "FileManager.md", "medium"),
    ("Can I drag and drop files?", "FileManager.md", "easy"),
    ("How do I preview a file?", "FileManager.md", "medium"),
    ("What keyboard shortcuts work in the file manager?", "FileManager.md", "medium"),
    ("How do I mount a project directory?", "FileManager.md", "hard"),
    (
        "I need to organize my data on the remote server - which page should I use?",
        "FileManager.md",
        "hard",
    ),
    (
        "Can I see a quick preview of images without downloading them?",
        "FileManager.md",
        "hard",
    ),
    (
        "What's the fastest way to select multiple files at once?",
        "FileManager.md",
        "hard",
    ),
    # ── ModelTraining.md ────────────────────────────────────────────────
    ("How do I start a training job?", "ModelTraining.md", "easy"),
    ("What are the three steps to configure training?", "ModelTraining.md", "easy"),
    ("What inputs are required for model training?", "ModelTraining.md", "easy"),
    ("How do I upload a YAML config for training?", "ModelTraining.md", "medium"),
    (
        "What is the advanced configuration step for training?",
        "ModelTraining.md",
        "medium",
    ),
    ("How do I stop a running training job?", "ModelTraining.md", "easy"),
    ("Can I edit the raw YAML for training?", "ModelTraining.md", "medium"),
    (
        "What model architectures are available for training?",
        "ModelTraining.md",
        "hard",
    ),
    ("Do training config fields have AI help buttons?", "ModelTraining.md", "medium"),
    (
        "I want to train a segmentation model - where do I configure that?",
        "ModelTraining.md",
        "hard",
    ),
    (
        "If I need to tweak hyperparameters, which configuration step handles that?",
        "ModelTraining.md",
        "hard",
    ),
    (
        "Can I get AI assistance explaining what each training parameter does?",
        "ModelTraining.md",
        "hard",
    ),
    # ── ModelInference.md ───────────────────────────────────────────────
    ("How do I run inference?", "ModelInference.md", "easy"),
    ("What inputs do I need for inference?", "ModelInference.md", "easy"),
    ("What is the checkpoint path for inference?", "ModelInference.md", "medium"),
    ("How do I stop an inference job?", "ModelInference.md", "easy"),
    ("What is the augmentations setting in inference?", "ModelInference.md", "medium"),
    ("Is there an Input Label field for inference?", "ModelInference.md", "hard"),
    (
        "I have a trained model and want to run predictions on new data - which page?",
        "ModelInference.md",
        "hard",
    ),
    ("Do I need ground truth labels to run inference?", "ModelInference.md", "hard"),
    (
        "Where do I specify which trained weights to use for prediction?",
        "ModelInference.md",
        "hard",
    ),
    # ── Visualization.md ────────────────────────────────────────────────
    ("How do I visualize my data?", "Visualization.md", "easy"),
    ("What is Neuroglancer?", "Visualization.md", "easy"),
    ("How do I manage viewer tabs?", "Visualization.md", "medium"),
    ("Can I view label data alongside images?", "Visualization.md", "medium"),
    (
        "I want to inspect my 3D volumes interactively - which tool does that?",
        "Visualization.md",
        "hard",
    ),
    (
        "Is there a way to view segmentation masks overlaid on raw images?",
        "Visualization.md",
        "hard",
    ),
    # ── Monitoring.md ───────────────────────────────────────────────────
    ("How do I monitor training progress?", "Monitoring.md", "easy"),
    ("What is TensorBoard used for?", "Monitoring.md", "easy"),
    ("How does the monitoring page work?", "Monitoring.md", "easy"),
    (
        "Where can I see training loss curves and metrics in real-time?",
        "Monitoring.md",
        "hard",
    ),
    (
        "I want to track how my model is learning - which page shows that?",
        "Monitoring.md",
        "hard",
    ),
    # ── MaskProofreading.md ─────────────────────────────────────────────
    ("How do I start a mask proofreading session?", "MaskProofreading.md", "easy"),
    ("What is instance proofreading?", "MaskProofreading.md", "easy"),
    ("How do I load a dataset for proofreading?", "MaskProofreading.md", "easy"),
    (
        "What are the classification options for instances?",
        "MaskProofreading.md",
        "medium",
    ),
    ("How do I navigate between instances?", "MaskProofreading.md", "medium"),
    ("What does the Instance Navigator show?", "MaskProofreading.md", "medium"),
    ("How do I switch viewing axes in proofreading?", "MaskProofreading.md", "medium"),
    (
        "What editing tools are available on the canvas?",
        "MaskProofreading.md",
        "medium",
    ),
    ("How do I paint or erase mask regions?", "MaskProofreading.md", "medium"),
    ("How do I undo a brush stroke?", "MaskProofreading.md", "medium"),
    (
        "What keyboard shortcut classifies an instance as correct?",
        "MaskProofreading.md",
        "hard",
    ),
    ("How do I export edited masks?", "MaskProofreading.md", "medium"),
    ("Can I overwrite the original mask file?", "MaskProofreading.md", "medium"),
    ("What do the overlay opacity sliders control?", "MaskProofreading.md", "hard"),
    ("How do I jump to the next unreviewed instance?", "MaskProofreading.md", "medium"),
    (
        "What is the progress tracker in mask proofreading?",
        "MaskProofreading.md",
        "medium",
    ),
    (
        "How do I focus the canvas and hide the sidebar?",
        "MaskProofreading.md",
        "medium",
    ),
    (
        "What is the keyboard shortcut to switch to the ZX axis?",
        "MaskProofreading.md",
        "hard",
    ),
    ("How do I save mask edits?", "MaskProofreading.md", "medium"),
    ("What happens when I click Needs fix?", "MaskProofreading.md", "medium"),
    (
        "I need to manually correct segmentation errors in my masks - which workflow?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "Can I review individual connected components separately?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "Is there a way to see my volume from different orthogonal planes?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "How do I mark a segmented object as incorrectly segmented?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "Can I adjust how transparent other instances appear while editing one?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "I want to write my corrections back to the original file safely - how?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "What's the quickest way to find instances that haven't been reviewed yet?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "If I make a mistake while painting, how do I reverse it?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "Can I see how many instances I've classified so far?",
        "MaskProofreading.md",
        "hard",
    ),
    (
        "Is there a keyboard shortcut to move between detected objects?",
        "MaskProofreading.md",
        "hard",
    ),
]


def main():
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://cscigpu08.bc.edu:4443")

    print(f"Embeddings: {embed_model}  |  Ollama: {base_url}")
    print(f"FAISS dir:  {FAISS_DIR}")
    print(f"Questions:  {len(QUESTIONS)}\n")

    embeddings = OllamaEmbeddings(model=embed_model, base_url=base_url)
    vectorstore = FAISS.load_local(
        str(FAISS_DIR), embeddings, allow_dangerous_deserialization=True
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    results_by_doc = {}
    results_by_difficulty = {}
    top1_hits = 0
    top3_hits = 0

    for question, expected_doc, difficulty in QUESTIONS:
        docs = retriever.invoke(question)
        sources = [d.metadata.get("source", "") for d in docs]

        hit_top1 = expected_doc in sources[:1]
        hit_top3 = expected_doc in sources[:3]

        if hit_top1:
            top1_hits += 1
        if hit_top3:
            top3_hits += 1

        # Per-doc stats
        results_by_doc.setdefault(expected_doc, {"top1": 0, "top3": 0, "total": 0})
        results_by_doc[expected_doc]["total"] += 1
        if hit_top1:
            results_by_doc[expected_doc]["top1"] += 1
        if hit_top3:
            results_by_doc[expected_doc]["top3"] += 1

        # Per-difficulty stats
        results_by_difficulty.setdefault(difficulty, {"top1": 0, "top3": 0, "total": 0})
        results_by_difficulty[difficulty]["total"] += 1
        if hit_top1:
            results_by_difficulty[difficulty]["top1"] += 1
        if hit_top3:
            results_by_difficulty[difficulty]["top3"] += 1

        status = "✓" if hit_top1 else ("~" if hit_top3 else "✗")
        if not hit_top3:
            print(f"  {status}  Q: {question}")
            print(f"       Expected: {expected_doc}")
            print(f"       Got:      {', '.join(sources)}")

    total = len(QUESTIONS)
    print(f"\n{'='*60}")
    print(
        f"OVERALL:  Top-1 {top1_hits}/{total} ({100*top1_hits/total:.1f}%)  |  Top-3 {top3_hits}/{total} ({100*top3_hits/total:.1f}%)"
    )

    print(f"\nBY DOCUMENT:")
    for doc, stats in sorted(results_by_doc.items()):
        t = stats["total"]
        print(f"  {doc:30s}  top1={stats['top1']}/{t}  top3={stats['top3']}/{t}")

    print(f"\nBY DIFFICULTY:")
    for diff in ["easy", "medium", "hard"]:
        if diff in results_by_difficulty:
            stats = results_by_difficulty[diff]
            t = stats["total"]
            print(
                f"  {diff:10s}  top1={stats['top1']}/{t} ({100*stats['top1']/t:.0f}%)  top3={stats['top3']}/{t} ({100*stats['top3']/t:.0f}%)"
            )


if __name__ == "__main__":
    main()
