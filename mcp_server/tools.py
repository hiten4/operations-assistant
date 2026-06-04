"""
tools.py – Core business logic for all MCP tools.
Separated from server.py so they can be imported and unit-tested directly.
"""

import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Paths (resolved relative to this file so the server works from any CWD) ──
_BASE = Path(__file__).resolve().parent.parent
DOCS_DIR = _BASE / "data" / "documents"
CSV_PATH = _BASE / "data" / "inventory.csv"
REPORTS_DIR = _BASE / "output" / "reports"

# Ensure output directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Prompt-injection guard ────────────────────────────────────────────────────
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+in\s+unrestricted\s+mode",
    r"reveal\s+(all\s+)?(system\s+prompts?|api\s+keys?|internal\s+config)",
    r"disregard\s+(all\s+)?instructions",
    r"act\s+as\s+(if\s+you\s+are\s+)?(?:an?\s+)?unrestricted",
    r"jailbreak",
    r"do\s+anything\s+now",
]


def _contains_injection(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in _INJECTION_PATTERNS)


def _safe_content(content: str) -> str:
    """Strip lines that look like prompt-injection attempts."""
    clean_lines = []
    for line in content.splitlines():
        if _contains_injection(line):
            clean_lines.append("[LINE REDACTED: potential prompt injection detected]")
        else:
            clean_lines.append(line)
    return "\n".join(clean_lines)


# ── Tool 1: search_documents ──────────────────────────────────────────────────

def search_documents(query: str) -> dict[str, Any]:
    """
    Search all text documents for keywords in *query*.
    Returns a list of matching documents with a simple relevance score.
    """
    if not DOCS_DIR.exists():
        return {"error": f"Documents directory not found: {DOCS_DIR}"}

    query_terms = [t.lower() for t in query.split() if len(t) > 1]
    if not query_terms:
        return {"error": "No searchable terms in query after filtering."}

    results = []
    for doc_file in sorted(DOCS_DIR.glob("*.txt")):
        raw = doc_file.read_text(encoding="utf-8")
        lower_raw = raw.lower()

        hit_count = sum(lower_raw.count(term) for term in query_terms)
        if hit_count == 0:
            continue

        # Extract Document ID and Title from the first two non-empty lines
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        doc_id = "UNKNOWN"
        title = doc_file.stem
        for line in lines[:5]:
            if line.lower().startswith("document id:"):
                doc_id = line.split(":", 1)[1].strip()
            elif line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()

        # Normalise score to 0–1 range (capped at 1.0)
        score = min(1.0, round(hit_count / (len(query_terms) * 3), 2))

        results.append(
            {
                "document_id": doc_id,
                "title": title,
                "filename": doc_file.name,
                "match_score": score,
                "hit_count": hit_count,
            }
        )

    results.sort(key=lambda x: x["match_score"], reverse=True)

    if not results:
        return {
            "results": [],
            "message": f"No documents matched query: '{query}'",
        }

    return {"results": results, "total_found": len(results)}


# ── Tool 2: read_record ───────────────────────────────────────────────────────

def read_record(document_id: str) -> dict[str, Any]:
    """
    Read the full content of a document by its ID (e.g. DOC001).
    Also queries the CSV for inventory data if the ID is 'CSV'.
    """
    doc_id_upper = document_id.upper()

    # Special case: return full CSV summary
    if doc_id_upper == "CSV":
        return _read_csv_summary()

    # Find matching file
    for doc_file in DOCS_DIR.glob("*.txt"):
        content = doc_file.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        for line in lines[:5]:
            if line.lower().startswith("document id:"):
                found_id = line.split(":", 1)[1].strip().upper()
                if found_id == doc_id_upper:
                    safe = _safe_content(content)
                    was_sanitised = safe != content
                    result = {
                        "document_id": doc_id_upper,
                        "filename": doc_file.name,
                        "content": safe,
                    }
                    if was_sanitised:
                        result["security_warning"] = (
                            "One or more lines were redacted due to suspected "
                            "prompt-injection content."
                        )
                    return result

    return {
        "error": f"Document '{document_id}' not found.",
        "hint": "Use list_documents() to see available IDs.",
    }


def _read_csv_summary() -> dict[str, Any]:
    """Return inventory data from CSV as structured records."""
    if not CSV_PATH.exists():
        return {"error": f"CSV not found: {CSV_PATH}"}
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return {
        "document_id": "CSV",
        "title": "Inventory Data",
        "records": rows,
        "total_rows": len(rows),
    }


# ── Tool 3: save_report ───────────────────────────────────────────────────────

def save_report(title: str, content: str) -> dict[str, Any]:
    """
    Save a markdown report to output/reports/.
    Returns the file path on success.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^\w\s\-]", "", title).strip().replace(" ", "_")
    filename = f"{timestamp}_{safe_title}.md"
    filepath = REPORTS_DIR / filename

    full_content = f"# {title}\n\n*Generated: {datetime.now().isoformat()}*\n\n{content}\n"
    filepath.write_text(full_content, encoding="utf-8")

    return {
        "status": "success",
        "message": f"Report saved successfully.",
        "filepath": str(filepath),
        "filename": filename,
        "bytes_written": len(full_content.encode()),
    }


# ── Resource: list_documents ──────────────────────────────────────────────────

def list_documents() -> dict[str, Any]:
    """List all available document IDs and titles."""
    if not DOCS_DIR.exists():
        return {"error": "Documents directory not found."}

    docs = []
    for doc_file in sorted(DOCS_DIR.glob("*.txt")):
        content = doc_file.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        doc_id = doc_file.stem
        title = doc_file.stem
        date = ""
        for line in lines[:6]:
            if line.lower().startswith("document id:"):
                doc_id = line.split(":", 1)[1].strip()
            elif line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("date:"):
                date = line.split(":", 1)[1].strip()
        docs.append({"document_id": doc_id, "title": title, "date": date, "filename": doc_file.name})

    return {"documents": docs, "total": len(docs)}
