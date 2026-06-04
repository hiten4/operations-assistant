# Operations Assistant

> **Week 14 Mini-Project** – Futurense AI Clinic  
> A multi-agent CrewAI system backed by a custom MCP server, built to answer business questions with evidence-backed, sourced reports.

---

## What It Does

Given a business question, a crew of three agents:
1. **Researcher** – searches company documents and inventory records via MCP tools
2. **Writer** – drafts a sourced markdown report from the evidence
3. **Validator** – checks every claim against retrieved evidence (flags unsupported claims and prompt-injection attempts)

Before saving, a **human approval gate** asks for confirmation. All runs are saved as structured **JSON traces**.

---

## Architecture

```
User Question → Researcher → Writer → Validator → Human Gate → Save Report
                    ↕           ↕          ↕
               MCP Server (FastMCP over stdio)
               ├── search_documents(query)
               ├── read_record(document_id)
               ├── save_report(title, content)
               └── Resource: list_documents
```

---

## Quick Start

### 1. Clone and install

> **⚠️ Python version:** CrewAI and MCP require **Python 3.11 or 3.12**.  
> Python 3.13 and 3.14 are **not yet supported**.  
> Download Python 3.11: https://www.python.org/downloads/release/python-3119/

```bash
git clone <your-repo-url>
cd operations-assistant

# Windows — use the py launcher to target 3.11 explicitly
py -3.11 -m venv .venv
.venv\Scripts\activate.ps1

# macOS/Linux
python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
# Get a free key at: https://console.groq.com
```

### 3. Run

```bash
# Interactive mode (choose from example questions)
python main.py

# Pass a question directly
python main.py --question "Which products are out of stock?"

# Skip human approval gate (for CI/automated runs)
python main.py --question "What does the return policy say?" --auto-approve
```

### 4. Test the MCP server in Inspector

```bash
npx @modelcontextprotocol/inspector python -m mcp_server.server
```

---

## Running Tests

```bash
# Unit tests (no API key needed)
pytest tests/test_tools.py -v

# End-to-end tests (requires GROQ_API_KEY)
pytest tests/test_end_to_end.py -v -m slow
```

---

## Project Structure

```
operations-assistant/
├── data/
│   ├── documents/          # 10 text documents (policies, tickets, notes)
│   └── inventory.csv       # 15-row inventory dataset
│
├── mcp_server/
│   ├── server.py           # FastMCP server (tools + resource)
│   ├── tools.py            # Business logic, injection detection
│   └── schemas.py          # Pydantic input validation
│
├── crew/
│   ├── agents.py           # Researcher, Writer, Validator agents
│   ├── tasks.py            # Task definitions
│   ├── crew.py             # Orchestration, tracing, human gate
│   └── llm_config.py       # Groq LLM config
│
├── output/
│   ├── reports/            # Saved markdown reports
│   └── traces/             # JSON run traces (observability)
│
├── tests/
│   ├── test_tools.py       # Unit tests for all tools + schemas
│   └── test_end_to_end.py  # Full crew integration tests
│
├── examples/
│   ├── question_1.md       # "Which products are out of stock?"
│   ├── question_2.md       # "What does the return policy say?"
│   └── question_3.md       # "What recurring issues in support tickets?"
│
├── docs/
│   ├── architecture.md     # System diagram
│   ├── decision_log.md     # What was tried, chosen, and why
│   └── reflection.md       # Project reflection (per rubric)
│
├── main.py                 # Entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Tools Reference

| Tool | Input | Output |
|---|---|---|
| `search_documents(query)` | keyword string | List of matching docs with scores |
| `read_record(document_id)` | `DOC001`–`DOC010` or `CSV` | Full document content or CSV records |
| `save_report(title, content)` | title + markdown | Saved file path |

---

## Stretch Features Implemented

| Feature | Where |
|---|---|
| **Human Approval Gate** | `crew/crew.py` – `_human_approval_gate()` |
| **Self-check Validator Agent** | `crew/agents.py` – `make_validator()` |
| **Observability Dashboard** | `crew/crew.py` – `RunTrace` class → `output/traces/` |
| **Prompt Injection Test** | `data/documents/DOC010_injection_test.txt` + `mcp_server/tools.py` – `_safe_content()` |

---

## Sample Output

```
🚀  Starting Operations Assistant
📋  Question: Which products are out of stock?
✅  MCP tools loaded: ['search_documents', 'read_record', 'save_report']

[Researcher] Calling search_documents(query="out of stock inventory")
[Researcher] Calling read_record(document_id="CSV")
[Researcher] Calling read_record(document_id="DOC008")

[Writer] Drafting sourced report...

[Validator] Verifying 5 claims...
Verdict: APPROVED

🔔  HUMAN APPROVAL GATE
Approve saving this report? [Y/N]: Y

📄  Report saved: output/reports/20240402_101532_Out_of_Stock_Products_Report.md
🔍  Trace saved: output/traces/trace_20240402_101532.json
```

---

## Security Notes

- All tool inputs validated with Pydantic before execution
- Document content scanned for prompt-injection patterns (line-level redaction)
- `max_iter` set on all agents to prevent runaway loops
- File access restricted to `data/documents/` — no arbitrary path traversal
- No secrets committed — use `.env` only

---

## Data

Documents cover: Return Policy, Shipping Policy, Product Notes (Laptops), Support Tickets #101–#104, Warehouse Rules, Supplier Notes, and an Injection Test document.  
Inventory CSV has 15 rows covering electronics and accessories.

All data is synthetic and safe to commit publicly.
