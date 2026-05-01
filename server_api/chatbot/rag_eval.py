"""
RAG Retrieval Evaluation Script
Tests whether FAISS retrieval returns the correct source document for each question.
Covers both UI docs and PyTC library docs.

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
    # ── ModelTraining.md (UI page) ──────────────────────────────────────
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
    ("Do training config fields have AI help buttons?", "ModelTraining.md", "medium"),
    (
        "I want to train a segmentation model - where do I configure that in the UI?",
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
    # ── ModelInference.md (UI page) ─────────────────────────────────────
    ("How do I run inference from the UI?", "ModelInference.md", "easy"),
    ("What inputs do I need for inference in the app?", "ModelInference.md", "easy"),
    ("What is the checkpoint path for inference?", "ModelInference.md", "medium"),
    ("How do I stop an inference job?", "ModelInference.md", "easy"),
    ("What is the augmentations slider in inference?", "ModelInference.md", "medium"),
    ("Is there an Input Label field for inference?", "ModelInference.md", "hard"),
    (
        "I have a trained model and want to run predictions on new data - which page?",
        "ModelInference.md",
        "hard",
    ),
    ("Do I need ground truth labels to run inference?", "ModelInference.md", "hard"),
    (
        "Where do I specify which trained weights to use for prediction in the UI?",
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
    # ── PyTC-Overview.md ───────────────────────────────────────────────
    ("What is PyTorch Connectomics?", "PyTC-Overview.md", "easy"),
    ("What tasks does PyTC support?", "PyTC-Overview.md", "easy"),
    ("What data formats does PyTC accept?", "PyTC-Overview.md", "easy"),
    ("Does PyTC support object detection?", "PyTC-Overview.md", "medium"),
    ("What is the main entry point script for PyTC?", "PyTC-Overview.md", "medium"),
    ("Can I use PyTC for image classification?", "PyTC-Overview.md", "hard"),
    ("What configuration system does PyTC use?", "PyTC-Overview.md", "medium"),
    ("Does PyTC use Hydra or YACS for configs?", "PyTC-Overview.md", "medium"),
    ("What is the --config flag for?", "PyTC-Overview.md", "medium"),
    ("What modes does PyTC support? train, test, tune?", "PyTC-Overview.md", "medium"),
    (
        "I want to do a quick test to see if PyTC is working, is there a demo mode?",
        "PyTC-Overview.md",
        "hard",
    ),
    (
        "What is the --fast-dev-run flag?",
        "PyTC-Overview.md",
        "hard",
    ),
    # ── PyTC-Training.md ───────────────────────────────────────────────
    # Easy: direct key/concept lookup
    ("How do I run a training job with PyTC?", "PyTC-Training.md", "easy"),
    ("What learning rate schedulers are available?", "PyTC-Training.md", "easy"),
    ("How do I resume training from a checkpoint?", "PyTC-Training.md", "easy"),
    ("What is optimization.optimizer.lr?", "PyTC-Training.md", "easy"),
    ("What is the training command for PyTC?", "PyTC-Training.md", "easy"),
    # Medium: requires understanding of config structure
    ("What optimizer options does PyTC support?", "PyTC-Training.md", "medium"),
    ("How do I enable gradient clipping?", "PyTC-Training.md", "medium"),
    ("What optimizer profiles are available?", "PyTC-Training.md", "medium"),
    ("What is the warmup_cosine_lr profile?", "PyTC-Training.md", "medium"),
    ("How do I set optimization.max_epochs?", "PyTC-Training.md", "medium"),
    ("What does optimization.precision control?", "PyTC-Training.md", "medium"),
    ("How do I change data.dataloader.batch_size?", "PyTC-Training.md", "medium"),
    ("What is monitor.checkpoint.save_top_k?", "PyTC-Training.md", "medium"),
    ("How do I set the system.num_gpus?", "PyTC-Training.md", "medium"),
    ("What is the EMA feature in PyTC training?", "PyTC-Training.md", "medium"),
    # Real-user training questions (natural language)
    ("Can I train my model for a longer period of time?", "PyTC-Training.md", "medium"),
    ("How do I lower the learning rate?", "PyTC-Training.md", "easy"),
    ("How often does the model save checkpoints?", "PyTC-Training.md", "medium"),
    ("Can I use AdamW instead of SGD?", "PyTC-Training.md", "medium"),
    (
        "How do I use cosine learning rate decay?",
        "PyTC-Training.md",
        "medium",
    ),
    (
        "Can I override config values from the command line?",
        "PyTC-Training.md",
        "medium",
    ),
    (
        "Where are training checkpoints saved?",
        "PyTC-Training.md",
        "medium",
    ),
    # Hard: requires synthesis or non-obvious mapping
    (
        "How do I train for 200 epochs instead of the default?",
        "PyTC-Training.md",
        "hard",
    ),
    (
        "My training is crashing because of NaN gradients, what should I try?",
        "PyTC-Training.md",
        "hard",
    ),
    (
        "What is mixed precision training and how do I enable bf16?",
        "PyTC-Training.md",
        "hard",
    ),
    (
        "How do I use the ReduceLROnPlateau scheduler?",
        "PyTC-Training.md",
        "hard",
    ),
    (
        "How do I enable early stopping during training?",
        "PyTC-Training.md",
        "hard",
    ),
    (
        "What is the --reset-max-epochs flag for when resuming?",
        "PyTC-Training.md",
        "hard",
    ),
    (
        "I want to accumulate gradients over multiple batches, how?",
        "PyTC-Training.md",
        "hard",
    ),
    # ── PyTC-Inference.md ──────────────────────────────────────────────
    # Easy
    ("How do I run inference with a trained model?", "PyTC-Inference.md", "easy"),
    ("What is test-time augmentation in PyTC?", "PyTC-Inference.md", "easy"),
    ("What does --mode test do?", "PyTC-Inference.md", "easy"),
    ("How do I run predictions on my test data?", "PyTC-Inference.md", "easy"),
    # Medium
    ("What blending modes are available for sliding window inference?", "PyTC-Inference.md", "medium"),
    ("How do I increase the sliding window overlap?", "PyTC-Inference.md", "medium"),
    ("Can I increase inference.batch_size for faster inference?", "PyTC-Inference.md", "medium"),
    ("What is inference.sliding_window.sw_batch_size?", "PyTC-Inference.md", "medium"),
    ("How do I enable TTA flips during inference?", "PyTC-Inference.md", "medium"),
    ("What is Gaussian blending in sliding window inference?", "PyTC-Inference.md", "medium"),
    (
        "How do I specify where to save inference output?",
        "PyTC-Inference.md",
        "medium",
    ),
    (
        "Can I use test-time augmentation to improve accuracy?",
        "PyTC-Inference.md",
        "medium",
    ),
    ("What output format does inference produce?", "PyTC-Inference.md", "medium"),
    # Hard
    (
        "I'm seeing tile boundary artifacts in my predictions, how do I fix that?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "How do I run sharded inference across multiple machines?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "What is cache-aware inference in PyTC?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "Should I use the same config file for inference as I used for training?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "How do I configure postprocessing after inference?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "What is inference.test_time_augmentation.ensemble_mode?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "How do I use the --shard-id and --num-shards flags?",
        "PyTC-Inference.md",
        "hard",
    ),
    (
        "What does inference.evaluation.enabled control?",
        "PyTC-Inference.md",
        "hard",
    ),
    # ── PyTC-Models.md ─────────────────────────────────────────────────
    # Easy
    ("What model architectures does PyTC support?", "PyTC-Models.md", "easy"),
    ("What is the MONAI UNet architecture?", "PyTC-Models.md", "easy"),
    ("What loss functions does PyTC support?", "PyTC-Models.md", "easy"),
    ("What is the RSUNet architecture?", "PyTC-Models.md", "easy"),
    # Medium
    ("What is the difference between monai_unet and rsunet?", "PyTC-Models.md", "medium"),
    ("What MedNeXt model sizes are available?", "PyTC-Models.md", "medium"),
    ("What is the loss_binary profile?", "PyTC-Models.md", "medium"),
    ("How do I set model.arch.profile?", "PyTC-Models.md", "medium"),
    ("What pipeline profiles are available?", "PyTC-Models.md", "medium"),
    ("What does the binary pipeline profile do?", "PyTC-Models.md", "medium"),
    ("How do I combine BCE loss with Dice loss?", "PyTC-Models.md", "medium"),
    ("What is PerChannelBCEWithLogitsLoss?", "PyTC-Models.md", "medium"),
    # Hard
    (
        "What is the affinity-12 pipeline profile?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "How do I configure loss functions with pred_slice and target_slice?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "What label transforms are available for instance segmentation?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "What is the ABISS decoding profile?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "How do I set up a model with 12 output channels for affinity prediction?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "What is the difference between DiceLoss and WeightedBCEWithLogitsLoss?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "What activation profiles are used during TTA?",
        "PyTC-Models.md",
        "hard",
    ),
    (
        "How does the BCD pipeline combine boundary, contour, and distance targets?",
        "PyTC-Models.md",
        "hard",
    ),
    # ── PyTC-Augmentation.md ───────────────────────────────────────────
    # Easy
    ("What augmentations does PyTC support?", "PyTC-Augmentation.md", "easy"),
    ("What is CutBlur augmentation?", "PyTC-Augmentation.md", "easy"),
    ("What augmentation profiles are available?", "PyTC-Augmentation.md", "easy"),
    ("What is the aug_standard profile?", "PyTC-Augmentation.md", "easy"),
    # Medium
    ("How do I disable elastic deformation?", "PyTC-Augmentation.md", "medium"),
    (
        "What augmentation profile should I use for isotropic EM data?",
        "PyTC-Augmentation.md",
        "medium",
    ),
    (
        "What is the aug_em_neuron profile for?",
        "PyTC-Augmentation.md",
        "medium",
    ),
    (
        "How do I set data.augmentation.profile?",
        "PyTC-Augmentation.md",
        "medium",
    ),
    (
        "What is the intensity augmentation in PyTC?",
        "PyTC-Augmentation.md",
        "medium",
    ),
    (
        "What is the difference between aug_light and aug_strong?",
        "PyTC-Augmentation.md",
        "medium",
    ),
    # Hard
    (
        "How do I simulate missing sections in my training data?",
        "PyTC-Augmentation.md",
        "hard",
    ),
    (
        "What is the defect_mutex feature in augmentation?",
        "PyTC-Augmentation.md",
        "hard",
    ),
    (
        "How does the copy-paste augmentation work for instance segmentation?",
        "PyTC-Augmentation.md",
        "hard",
    ),
    (
        "What augmentation profile matches the DeepEM recipe?",
        "PyTC-Augmentation.md",
        "hard",
    ),
    (
        "How do I add mixup augmentation to my training?",
        "PyTC-Augmentation.md",
        "hard",
    ),
    (
        "What does data.augmentation.misalignment.displacement control?",
        "PyTC-Augmentation.md",
        "hard",
    ),
    # ── PyTC-Configs.md ────────────────────────────────────────────────
    # Easy
    ("What bundled configs does PyTC have?", "PyTC-Configs.md", "easy"),
    ("Which config should I use for mitochondria segmentation?", "PyTC-Configs.md", "easy"),
    ("Where are the tutorial configs located?", "PyTC-Configs.md", "easy"),
    # Medium
    ("What config is used for CREMI synapse detection?", "PyTC-Configs.md", "medium"),
    ("What architecture does neuron_snemi.yaml use?", "PyTC-Configs.md", "medium"),
    ("What is the mito_lucchi++.yaml config for?", "PyTC-Configs.md", "medium"),
    ("What base profiles do the tutorial configs inherit from?", "PyTC-Configs.md", "medium"),
    ("Are there configs for nucleus segmentation?", "PyTC-Configs.md", "medium"),
    # Hard
    (
        "What is the recommended config for neuron instance segmentation?",
        "PyTC-Configs.md",
        "hard",
    ),
    (
        "How do I choose the right config for my dataset?",
        "PyTC-Configs.md",
        "hard",
    ),
    (
        "What is the profile-based inheritance system for configs?",
        "PyTC-Configs.md",
        "hard",
    ),
    (
        "What misc configs are available for specialized tasks?",
        "PyTC-Configs.md",
        "hard",
    ),
    (
        "How do I override data paths in a tutorial config?",
        "PyTC-Configs.md",
        "hard",
    ),
    # ── PyTC-Evaluation.md ─────────────────────────────────────────────
    # Easy
    ("How do I evaluate segmentation results in PyTC?", "PyTC-Evaluation.md", "easy"),
    ("What is adapted Rand error?", "PyTC-Evaluation.md", "easy"),
    # Medium
    ("What evaluation metric should I use for instance segmentation?", "PyTC-Evaluation.md", "medium"),
    ("How do I compute IoU for binary segmentation?", "PyTC-Evaluation.md", "medium"),
    ("How do I know if my model is good?", "PyTC-Evaluation.md", "medium"),
    (
        "How do I compare my prediction against ground truth?",
        "PyTC-Evaluation.md",
        "medium",
    ),
    (
        "I have a binary segmentation prediction, how do I get precision and recall?",
        "PyTC-Evaluation.md",
        "medium",
    ),
    (
        "What Python functions does PyTC provide for evaluation?",
        "PyTC-Evaluation.md",
        "medium",
    ),
    # Hard
    (
        "What is variation of information in segmentation evaluation?",
        "PyTC-Evaluation.md",
        "hard",
    ),
    (
        "Does PyTC automatically compute metrics after inference?",
        "PyTC-Evaluation.md",
        "hard",
    ),
    ("What metric should I report for the SNEMI3D challenge?", "PyTC-Evaluation.md", "hard"),
    (
        "Is my model over-segmenting or under-segmenting? How can I tell?",
        "PyTC-Evaluation.md",
        "hard",
    ),
    (
        "What is panoptic quality and how do I compute it?",
        "PyTC-Evaluation.md",
        "hard",
    ),
    (
        "How do I evaluate my CREMI synapse detection results?",
        "PyTC-Evaluation.md",
        "hard",
    ),
    (
        "What is the cremi_distance metric?",
        "PyTC-Evaluation.md",
        "hard",
    ),
    (
        "Can I enable automatic evaluation during inference with inference.evaluation.enabled?",
        "PyTC-Evaluation.md",
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
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    results_by_doc = {}
    results_by_difficulty = {}
    top1_hits = 0
    top2_hits = 0

    for question, expected_doc, difficulty in QUESTIONS:
        docs = retriever.invoke(question)
        sources = [d.metadata.get("source", "") for d in docs]

        hit_top1 = expected_doc in sources[:1]
        hit_top2 = expected_doc in sources[:2]

        if hit_top1:
            top1_hits += 1
        if hit_top2:
            top2_hits += 1

        # Per-doc stats
        results_by_doc.setdefault(expected_doc, {"top1": 0, "top2": 0, "total": 0})
        results_by_doc[expected_doc]["total"] += 1
        if hit_top1:
            results_by_doc[expected_doc]["top1"] += 1
        if hit_top2:
            results_by_doc[expected_doc]["top2"] += 1

        # Per-difficulty stats
        results_by_difficulty.setdefault(difficulty, {"top1": 0, "top2": 0, "total": 0})
        results_by_difficulty[difficulty]["total"] += 1
        if hit_top1:
            results_by_difficulty[difficulty]["top1"] += 1
        if hit_top2:
            results_by_difficulty[difficulty]["top2"] += 1

        status = "✓" if hit_top1 else ("~" if hit_top2 else "✗")
        if not hit_top2:
            print(f"  {status}  Q: {question}")
            print(f"       Expected: {expected_doc}")
            print(f"       Got:      {', '.join(sources)}")

    total = len(QUESTIONS)
    print(f"\n{'='*60}")
    print(
        f"OVERALL:  Top-1 {top1_hits}/{total} ({100*top1_hits/total:.1f}%)  |  Top-2 {top2_hits}/{total} ({100*top2_hits/total:.1f}%)"
    )

    print(f"\nBY DOCUMENT:")
    for doc, stats in sorted(results_by_doc.items()):
        t = stats["total"]
        print(f"  {doc:30s}  top1={stats['top1']}/{t}  top2={stats['top2']}/{t}")

    print(f"\nBY DIFFICULTY:")
    for diff in ["easy", "medium", "hard"]:
        if diff in results_by_difficulty:
            stats = results_by_difficulty[diff]
            t = stats["total"]
            print(
                f"  {diff:10s}  top1={stats['top1']}/{t} ({100*stats['top1']/t:.0f}%)  top2={stats['top2']}/{t} ({100*stats['top2']/t:.0f}%)"
            )


if __name__ == "__main__":
    main()
