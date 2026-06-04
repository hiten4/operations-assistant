# Decision Log

## Architecture Decisions

### 1. FastMCP over raw MCP SDK
**Considered:** Raw `mcp` SDK with manual tool registration  
**Chosen:** FastMCP (decorator-based)  
**Why:** FastMCP reduces boilerplate significantly while using the same underlying protocol. The `@mcp.tool()` decorator makes tool registration clear and testable. The raw SDK would require more manual JSON schema construction with no benefit at this scale.

### 2. Groq (Llama 3.3 70B) as LLM
**Considered:** Ollama (local), OpenAI GPT-4o, Anthropic Claude  
**Chosen:** Groq free tier with `llama-3.3-70b-versatile`  
**Why:** Groq provides near-instant inference on Llama 3.3 70B for free. Ollama is slower on most laptops and unreliable for multi-step reasoning. OpenAI and Anthropic require paid keys.

### 3. Sequential Crew Process
**Considered:** Hierarchical process (manager/workers), parallel  
**Chosen:** Sequential (Researcher → Writer → Validator)  
**Why:** Each step depends on the previous step's output. Hierarchical adds a manager LLM call with no benefit here. Sequential is debuggable and deterministic for this use case.

### 4. Pydantic schemas in a separate `schemas.py`
**Considered:** Inline validation inside each tool function  
**Chosen:** Separate `schemas.py` with Pydantic models  
**Why:** Separating schemas from business logic means they can be imported by both the server and the tests independently, and they serve as self-documenting contracts for tool inputs.

### 5. Human Approval Gate placement
**Considered:** Before writing, before validation, after validation  
**Chosen:** After validation (only if APPROVED)  
**Why:** It makes no sense to ask a human to approve a report the validator already rejected. The gate should only trigger on validated, high-quality output.

### 6. Document-level injection sanitisation in `read_record()`
**Considered:** Block documents containing injection, warn the LLM in system prompt only  
**Chosen:** Line-level redaction + security_warning flag in the returned dict  
**Why:** Blocking the whole document loses the legitimate content. Line-level redaction preserves real data while neutralising the attack. The `security_warning` key signals to the LLM (and to developers reviewing traces) that the document was tampered with.

---

## What Was Tried and Rejected

| Approach | Reason Rejected |
|---|---|
| `httpx`-based SSE transport for MCP | Adds server/client complexity for no benefit in a local demo. stdio is simpler and officially supported. |
| Storing full CSV in each agent's context | Causes token bloat. Instead, `read_record('CSV')` is called on demand. |
| Using `crewai`'s built-in `FileReadTool` | Less control over injection sanitisation than custom tools. |
| Single "all-in-one" agent | Mixing research, writing, and validation in one agent causes role confusion and poorer outputs. |
| Regex-based citation verification | Too brittle. The Validator agent is better at semantic claim-checking than regex. |
