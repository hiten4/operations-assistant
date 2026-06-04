"""
schemas.py – Pydantic input validation for all MCP tools.
Treat every LLM-supplied input as untrusted.
"""

from pydantic import BaseModel, field_validator, model_validator
import re


class SearchInput(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        if len(v) > 500:
            raise ValueError("query too long (max 500 characters)")
        # Block obvious prompt injection patterns in the query itself
        injection_patterns = [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"you\s+are\s+now\s+in\s+unrestricted\s+mode",
            r"reveal\s+(all\s+)?(system\s+prompts?|api\s+keys?)",
            r"disregard\s+(all\s+)?instructions",
        ]
        lower = v.lower()
        for pattern in injection_patterns:
            if re.search(pattern, lower):
                raise ValueError("query contains disallowed content")
        return v


class ReadRecordInput(BaseModel):
    document_id: str

    @field_validator("document_id")
    @classmethod
    def valid_doc_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^DOC\d{3}$", v):
            raise ValueError(
                f"Invalid document_id '{v}'. Must match format DOC001–DOC999."
            )
        return v


class SaveReportInput(BaseModel):
    title: str
    content: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty")
        if len(v) > 200:
            raise ValueError("title too long (max 200 characters)")
        # Sanitise: allow only alphanumeric, spaces, hyphens, underscores
        safe = re.sub(r"[^\w\s\-]", "", v)
        return safe

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be empty")
        if len(v) > 50_000:
            raise ValueError("content too large (max 50 000 characters)")
        return v
