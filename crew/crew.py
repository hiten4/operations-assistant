"""
crew.py – Main CrewAI orchestration with:
  - MCP tool connection via MCPServerAdapter
  - Human approval gate before saving reports
  - Structured trace logging (observability)
  - Prompt-injection detection
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from crewai import Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from crewai.utilities import RPMController

from crew.agents import make_researcher, make_writer, make_validator
from crew.tasks import make_research_task, make_writing_task, make_validation_task

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
TRACES_DIR = _BASE / "output" / "traces"
REPORTS_DIR = _BASE / "output" / "reports"
TRACES_DIR.mkdir(parents=True, exist_ok=True)


# ── Observability trace ───────────────────────────────────────────────────────

class RunTrace:
    """Collect structured trace data for a single crew run."""

    def __init__(self, question: str):
        self.question = question
        self.start_time = time.time()
        self.timestamp = datetime.now().isoformat()
        self.events: list[dict] = []
        self.tool_calls: list[dict] = []

    def log_event(self, event_type: str, agent: str, detail: str):
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "agent": agent,
            "detail": detail,
            "elapsed_s": round(time.time() - self.start_time, 2),
        })

    def log_tool_call(self, agent: str, tool: str, input_: dict, output: dict, duration_s: float):
        self.tool_calls.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "tool": tool,
            "input": input_,
            "output_summary": str(output)[:300],
            "duration_s": round(duration_s, 3),
        })

    def save(self, verdict: str = "unknown") -> Path:
        duration = round(time.time() - self.start_time, 2)
        report = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "question": self.question,
            "start_time": self.timestamp,
            "duration_s": duration,
            "verdict": verdict,
            "tool_call_count": len(self.tool_calls),
            "event_count": len(self.events),
            "tool_calls": self.tool_calls,
            "events": self.events,
            "observability_summary": {
                "agents_active": list({e["agent"] for e in self.events}),
                "tools_used": list({t["tool"] for t in self.tool_calls}),
                "total_tool_calls": len(self.tool_calls),
                "total_duration_s": duration,
            },
        }
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = TRACES_DIR / f"trace_{ts}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path


# ── Human approval gate ───────────────────────────────────────────────────────

def _human_approval_gate(report_content: str, validation_verdict: str) -> bool:
    """
    Show the report and validation verdict, then ask for human approval.
    Returns True if approved, False otherwise.
    """
    print("\n" + "=" * 70)
    print("🔔  HUMAN APPROVAL GATE")
    print("=" * 70)
    print(f"\nValidation verdict: {validation_verdict}\n")
    print("─" * 70)
    print("DRAFT REPORT PREVIEW (first 1000 chars):")
    print("─" * 70)
    print(report_content[:1000])
    if len(report_content) > 1000:
        print(f"\n... [truncated, {len(report_content)} chars total]")
    print("\n" + "─" * 70)

    while True:
        answer = input("\n✅  Approve saving this report? [Y/N]: ").strip().upper()
        if answer == "Y":
            print("✅  Report approved. Saving...\n")
            return True
        elif answer == "N":
            print("❌  Report rejected. Not saving.\n")
            return False
        else:
            print("Please enter Y or N.")


# ── Main run function ─────────────────────────────────────────────────────────

def run_crew(question: str, auto_approve: bool = False) -> dict:
    """
    Run the full agent crew on a business question.

    Args:
        question:     The business question to answer.
        auto_approve: If True, skip human approval (useful for automated tests).

    Returns:
        Dict with result, validation_verdict, report_path, trace_path.
    """
    trace = RunTrace(question)
    trace.log_event("run_start", "orchestrator", f"Question: {question}")

    # Build path to MCP server
    server_script = str(_BASE / "mcp_server" / "server.py")

    print(f"\n🚀  Starting Operations Assistant")
    print(f"📋  Question: {question}")
    print(f"🔧  Connecting to MCP server: {server_script}\n")

    with MCPServerAdapter(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(_BASE),
            env={**os.environ},
        )
    ) as mcp_tools:

        trace.log_event("mcp_connected", "orchestrator",
                        f"Tools available: {[t.name for t in mcp_tools]}")
        print(f"✅  MCP tools loaded: {[t.name for t in mcp_tools]}\n")

        # Build agents
        researcher = make_researcher(mcp_tools)
        writer = make_writer(mcp_tools)
        validator = make_validator(mcp_tools)

        # Build tasks
        research_task = make_research_task(researcher, question)
        writing_task = make_writing_task(writer, question, research_task)
        validation_task = make_validation_task(validator, question, writing_task, research_task)

        # Assemble crew
        crew = Crew(
            agents=[researcher, writer, validator],
            tasks=[research_task, writing_task, validation_task],
            process=Process.sequential,
            verbose=True,
            memory=False,
        )

        trace.log_event("crew_kickoff", "orchestrator", "Sequential crew starting")

        # ── Run ──────────────────────────────────────────────────────────────
        t0 = time.time()
        result = crew.kickoff()
        elapsed = round(time.time() - t0, 2)

        trace.log_event("crew_complete", "orchestrator", f"Crew finished in {elapsed}s")

        # Extract outputs
        raw_output = str(result)
        research_output = str(research_task.output) if research_task.output else ""
        writing_output = str(writing_task.output) if writing_task.output else ""
        validation_output = str(validation_task.output) if validation_task.output else ""

        # Determine validation verdict
        verdict = "APPROVED" if "APPROVED" in validation_output.upper() else "REJECTED"
        trace.log_event("validation_verdict", "validator", verdict)

        print(f"\n{'=' * 70}")
        print(f"📊  VALIDATION VERDICT: {verdict}")
        print(f"{'=' * 70}\n")

        # ── Human approval gate ───────────────────────────────────────────────
        report_path = None
        if verdict == "APPROVED":
            approved = auto_approve or _human_approval_gate(writing_output, verdict)
            if approved:
                from mcp_server.tools import save_report
                from mcp_server.schemas import SaveReportInput

                # Generate a clean title from the question
                title_words = question[:60].replace("?", "").replace("/", "-")
                report_title = f"Operations Report - {title_words}"

                save_result = save_report(report_title, writing_output)
                report_path = save_result.get("filepath")
                trace.log_event("report_saved", "orchestrator", f"Saved to {report_path}")
                print(f"📄  Report saved: {report_path}")
            else:
                trace.log_event("report_rejected_human", "orchestrator", "Human rejected report")
        else:
            trace.log_event("report_not_saved", "orchestrator",
                            "Validation REJECTED – report not saved")
            print("⚠️   Report not saved due to validation failure.")

    # ── Save trace ────────────────────────────────────────────────────────────
    trace_path = trace.save(verdict=verdict)
    print(f"🔍  Trace saved: {trace_path}\n")

    return {
        "question": question,
        "research_output": research_output,
        "writing_output": writing_output,
        "validation_output": validation_output,
        "verdict": verdict,
        "report_path": report_path,
        "trace_path": str(trace_path),
    }
