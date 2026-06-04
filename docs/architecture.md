# Architecture

```
User Question
      │
      ▼
  main.py
      │
      ▼
  crew.py  ──── RunTrace (observability)
      │
      ├── MCPServerAdapter (stdio transport)
      │         │
      │         ▼
      │   mcp_server/server.py  (FastMCP)
      │         │
      │         ├── search_documents()  ─── schemas.py (Pydantic)
      │         ├── read_record()            │
      │         ├── save_report()            └── tools.py (business logic)
      │         └── Resource: list_documents()
      │
      ├── Researcher Agent  (max_iter=6)
      │     Uses: search_documents, read_record
      │
      ├── Writer Agent      (max_iter=4)
      │     Uses: (reads context from Researcher)
      │
      └── Validator Agent   (max_iter=4)
            Uses: read_record (cross-checks claims)
                  │
                  ▼
           Human Approval Gate (stdin Y/N)
                  │
                  ▼
           save_report() → output/reports/
                  │
                  ▼
           trace saved → output/traces/
```

## Data Flow

```
data/documents/*.txt  ─┐
                        ├─► tools.py ─► schemas.py ─► server.py ─► MCP adapter ─► agents
data/inventory.csv    ─┘
```

## Security Layers

```
LLM input → Pydantic schema validation → tools.py business logic
                                              │
                                    injection detection (line-level)
                                              │
                                    path allowlist (DOCS_DIR only)
                                              │
                                    Validator agent (semantic check)
                                              │
                                    Human approval gate
```
