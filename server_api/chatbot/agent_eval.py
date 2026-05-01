"""
End-to-end agent evaluation for training command generation.

Sends 10 realistic user requests through the full agent pipeline and
prints tool call logs + full responses for manual review.
"""

import sys
import re
from io import StringIO

TRAINING_REQUESTS = [
    # Basic config selection
    "Give me the training command for mitochondria segmentation on the Lucchi dataset",
    "Give me the command to train synapse detection on CREMI",
    "Write the training command for neuron segmentation on SNEMI3D",
    "Generate a command to train on the MitoEM-R dataset",
    "Give me the command to train nucleus segmentation on zebrafish data",
    "Write the command for vesicle segmentation training",
    "Give me a quick demo training command to test if everything works",
    # Single override
    "Give me the command to train CREMI synapse detection with learning rate 0.0001",
    "Write the training command for Lucchi mitochondria with 300 epochs",
    "Generate the command to train SNEMI3D neuron segmentation with batch size 4",
    "Give me the command to train MitoEM-H with AdamW optimizer",
    "Write the command for Lucchi mito training with bf16 mixed precision",
    # Multiple overrides
    "Generate the training command for vesicle segmentation with learning rate 0.001 and gradient clipping of 1.0",
    "Give me the command to train Lucchi mito with 200 epochs and learning rate 0.0005",
    "Write the command to train CREMI synapse detection, saving checkpoints every 5 epochs with early stopping patience 20",
    # Advanced / tricky
    "Give me the command for neuron instance segmentation training at 40nm resolution with gradient clipping 1.0",
    "Generate the training command for MitoEM-R with cosine learning rate schedule and 500 epochs",
    "Write the command to train on the MitoEM human+rat combined dataset with 4 GPUs",
    "Give me the training command for Lucchi mitochondria, but I want to save only the top 1 checkpoint",
    "Generate a command to train SNEMI3D neurons with learning rate 0.0003, batch size 2, and gradient clipping 0.5",
]

INFERENCE_REQUESTS = [
    # Basic inference
    "Give me the inference command for my trained Lucchi mito model. The checkpoint is at outputs/mito_lucchi/checkpoints/epoch=100.ckpt",
    "Write the command to run inference on CREMI with my checkpoint at outputs/syn_cremi/checkpoints/last.ckpt",
    "Generate the inference command for SNEMI3D using checkpoint outputs/neuron_snemi/checkpoints/epoch=050.ckpt",
    # With overrides
    "Give me the inference command for Lucchi mito with checkpoint outputs/mito_lucchi/checkpoints/epoch=100.ckpt and Gaussian blending",
    "Write the command to run inference on CREMI with checkpoint outputs/syn_cremi/checkpoints/last.ckpt and test-time augmentation enabled",
    "Generate the inference command for MitoEM-R with checkpoint outputs/mitoem_r/checkpoints/epoch=200.ckpt and output saved to results/mitoem_predictions/",
    # Advanced
    "Give me the command to run inference on vesicle data with checkpoint outputs/vesicle_xm/checkpoints/epoch=150.ckpt, sliding window overlap 0.75, and Gaussian blending",
    "Write the inference command for SNEMI3D neuron segmentation using outputs/neuron_snemi/checkpoints/epoch=100.ckpt with TTA enabled and ensemble mode set to mean",
    "Generate the command to run inference on the Lucchi dataset with checkpoint outputs/mito_lucchi/checkpoints/best.ckpt and batch size 2",
    "Give me the inference command for nucleus segmentation on zebrafish with checkpoint outputs/nuc_nucmm/checkpoints/epoch=080.ckpt and save output to results/nuc_output/",
]


def main():
    from server_api.chatbot.chatbot import build_chain

    print("Building agent chain...")
    supervisor, reset_search = build_chain()
    print("Agent chain ready.\n")

    all_requests = [("TRAIN", r) for r in TRAINING_REQUESTS]

    for i, (category, request) in enumerate(all_requests):
        print(f"\n{'=' * 80}")
        print(f"[{category}] TEST {i + 1}/{len(all_requests)}")
        print(f"USER: {request}")
        print("=" * 80)

        # Capture stdout to get tool call logs
        old_stdout = sys.stdout
        captured = StringIO()
        sys.stdout = captured

        try:
            reset_search()
            result = supervisor.invoke(
                {"messages": [{"role": "user", "content": request}]}
            )
            messages = result.get("messages", [])
            response = messages[-1].content if messages else "(no response)"
        except Exception as e:
            response = f"ERROR: {e}"
        finally:
            sys.stdout = old_stdout
            tool_log = captured.getvalue()

        # Print tool calls
        tool_calls = re.findall(r"\[TOOL\] .*", tool_log)
        if tool_calls:
            print("\nTOOL CALLS:")
            for tc in tool_calls:
                print(f"  {tc}")

        print(f"\nRESPONSE:\n{response}")
        print()


if __name__ == "__main__":
    main()
