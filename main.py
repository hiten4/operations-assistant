"""
main.py – Entry point for the Operations Assistant.

Usage:
    python main.py
    python main.py --question "Which products are out of stock?"
    python main.py --auto-approve   (skip human approval gate; useful for CI)
"""

import argparse
import sys
from dotenv import load_dotenv

load_dotenv()


DEFAULT_QUESTION = "Which products are out of stock and what does our reorder policy say?"

EXAMPLE_QUESTIONS = [
    "Which products are out of stock?",
    "What does the return policy say about electronics?",
    "What recurring issues appear in our support tickets?",
]


def main():
    parser = argparse.ArgumentParser(description="Operations Assistant (MCP + CrewAI)")
    parser.add_argument(
        "--question", "-q",
        type=str,
        default=None,
        help="Business question to answer. Leave blank to choose interactively.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        default=False,
        help="Skip human approval gate (for automated runs / tests).",
    )
    args = parser.parse_args()

    question = args.question

    if not question:
        print("\n📋  Operations Assistant – Example Questions")
        print("=" * 50)
        for i, q in enumerate(EXAMPLE_QUESTIONS, 1):
            print(f"  {i}. {q}")
        print(f"  4. Enter your own question")
        print()

        choice = input("Choose [1-4]: ").strip()
        if choice in ("1", "2", "3"):
            question = EXAMPLE_QUESTIONS[int(choice) - 1]
        elif choice == "4":
            question = input("Enter your question: ").strip()
        else:
            question = DEFAULT_QUESTION

    if not question:
        print("No question provided. Exiting.")
        sys.exit(1)

    from crew.crew import run_crew
    result = run_crew(question, auto_approve=args.auto_approve)

    print("\n" + "=" * 70)
    print("✅  RUN COMPLETE")
    print("=" * 70)
    print(f"Verdict:    {result['verdict']}")
    print(f"Report:     {result.get('report_path', 'Not saved')}")
    print(f"Trace:      {result['trace_path']}")
    print()


if __name__ == "__main__":
    main()
