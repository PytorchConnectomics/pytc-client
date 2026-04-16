"""
Standalone Agent Test Script
Tests the multi-agent chatbot system without starting the full app.
Shows all RAG retrievals, tool calls, and final responses.

Usage:
  python agent_cli.py                     # interactive mode
  python agent_cli.py -b                  # batch: run 20-question PyTC eval
  python agent_cli.py "your question"     # single question
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server_api.chatbot.chatbot import build_chain


# ── Failed questions from 40-question test ──────────────────────────────────

BATCH_QUESTIONS = [
    # Test #10 - Fabricated CLI flags --batch-size, --checkpoint-interval
    "Give me the command to train on CREMI with batch size 2 and save checkpoints every 5000 iterations",
    
    # Test #14 - Didn't override scheduler explicitly
    "Train on MitoEM with the WarmupCosineLR scheduler and a base learning rate of 0.002",
    
    # Test #17 - Wrong override format --inference.AUG_NUM=8
    "Generate an inference command for CREMI. Use configs/CREMI/CREMI-Base.yaml and checkpoint outputs/CREMI/checkpoint_100000.pth.tar with 8 TTA augmented views",
    
    # Test #32 - Fabricated scripts/evaluate.py
    "How do I evaluate synapse detection results for the CREMI challenge?",
]


def run_batch():
    """Run the 20-question batch test. Agent is built once and reused."""
    print("Building agent (one-time)...")
    agent, reset_search_counter = build_chain()
    print(f"Running {len(BATCH_QUESTIONS)} tests...\n")

    for i, q in enumerate(BATCH_QUESTIONS, 1):
        reset_search_counter()

        print(f"\n{'='*80}")
        print(f"TEST {i}/{len(BATCH_QUESTIONS)}")
        print(f"Q: {q}")
        print(f"{'='*80}\n")

        t0 = time.time()
        try:
            result = agent.invoke({"messages": [("user", q)]})
            response = result["messages"][-1].content
        except Exception as e:
            response = f"[ERROR] {e}"
        elapsed = time.time() - t0

        print(f"\n{'─'*80}")
        print("RESPONSE:")
        print(f"{'─'*80}")
        print(response)
        print(f"\n({elapsed:.1f}s)")

    print(f"\n{'#'*80}")
    print(f"BATCH COMPLETE — {len(BATCH_QUESTIONS)} questions answered")
    print(f"{'#'*80}")


def run_single(question: str):
    """Test the agent with a single question."""
    print(f"\n{'='*80}")
    print(f"QUESTION: {question}")
    print(f"{'='*80}\n")
    agent, reset_search_counter = build_chain()
    reset_search_counter()
    result = agent.invoke({"messages": [("user", question)]})
    response = result["messages"][-1].content
    print(f"\n{'─'*80}")
    print("FINAL RESPONSE:")
    print(f"{'─'*80}")
    print(response)
    print(f"\n{'='*80}\n")


def interactive_mode():
    """Interactive mode for testing custom questions."""
    print("\n" + "="*80)
    print("INTERACTIVE AGENT TEST MODE")
    print("="*80)
    print("Type your questions to test the agent.")
    print("Type 'quit' or 'exit' to stop.\n")
    agent, reset_search_counter = build_chain()
    while True:
        try:
            question = input("\nYour question: ").strip()
            if question.lower() in ['quit', 'exit', 'q']:
                break
            if not question:
                continue
            reset_search_counter()
            result = agent.invoke({"messages": [("user", question)]})
            response = result["messages"][-1].content
            print(f"\n{'─'*60}")
            print(response)
            print(f"{'─'*60}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test the chatbot agent")
    parser.add_argument("-b", "--batch", action="store_true", help="Run 20-question graded batch test")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("question", nargs="*", help="Single question to test")
    args = parser.parse_args()

    if args.batch:
        run_batch()
    elif args.interactive:
        interactive_mode()
    elif args.question:
        run_single(" ".join(args.question))
    else:
        interactive_mode()
