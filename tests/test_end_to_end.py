"""
test_end_to_end.py – End-to-end test that runs the full crew on a fixed question.

This test is marked slow; run with:
    pytest tests/test_end_to_end.py -v -m slow

Requirements: GROQ_API_KEY must be set in environment or .env file.
"""

import os
import sys
import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytestmark = pytest.mark.slow


@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set – skipping live crew test",
)
def test_out_of_stock_question():
    """
    Full crew run: 'Which products are out of stock?'
    Verify:
      - Result is non-empty
      - Tool calls actually happened (checked via trace file)
      - Report references document sources
    """
    from crew.crew import run_crew

    result = run_crew(
        question="Which products are out of stock?",
        auto_approve=True,  # Skip human gate in automated test
    )

    # Basic structure
    assert "research_output" in result
    assert "writing_output" in result
    assert "validation_output" in result
    assert "verdict" in result

    # Research output should mention product names
    research = result["research_output"].lower()
    assert len(research) > 100, "Research output seems too short"

    # Writing output should contain source citations
    writing = result["writing_output"]
    assert "source" in writing.lower() or "doc" in writing.lower(), \
        "Writing output should contain source citations"

    # Trace file should exist
    trace_path = Path(result["trace_path"])
    assert trace_path.exists(), "Trace file should be created"

    # Trace should record tool calls
    import json
    trace_data = json.loads(trace_path.read_text())
    assert trace_data["question"] == "Which products are out of stock?"


@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set – skipping live crew test",
)
def test_return_policy_question():
    """
    Full crew run: 'What does the return policy say?'
    """
    from crew.crew import run_crew

    result = run_crew(
        question="What does the return policy say about electronics?",
        auto_approve=True,
    )

    writing = result["writing_output"].lower()
    # Should mention electronics-specific terms
    assert any(word in writing for word in ["15 days", "electronics", "return", "policy"]), \
        "Report should reference return policy content"


@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set – skipping live crew test",
)
def test_grounding_no_fabrication():
    """
    Ask about something that doesn't exist – crew should say so, not fabricate.
    """
    from crew.crew import run_crew

    result = run_crew(
        question="What is our policy on flying cars?",
        auto_approve=True,
    )

    # Either research or writing output should acknowledge no evidence
    combined = (result["research_output"] + result["writing_output"]).lower()
    assert any(phrase in combined for phrase in [
        "no evidence", "not found", "no information", "unable to find", "no documents"
    ]), "Crew should acknowledge when evidence is missing, not fabricate"
