# Local API Spec Drift Scoreboard

A local scoreboard for measuring whether an API specification is reliable enough for an agent to call. It scores synthetic OpenAPI-style specs across raw OpenAPI, generated MCP, and routed-agent modes, then suggests minimal spec patches and emits MCP tool descriptors.

Everything runs offline with deterministic fixtures. No live APIs, credentials, external LLMs, or marketplace scraping are required.

## Quick Start

```bash
uv sync
uv run specdrift-local init-demo
uv run specdrift-local score --iterations 20
uv run specdrift-local verify
uv run specdrift-local dashboard
```

## Outputs

- `runs/latest/specdrift.duckdb` with score rows, drift findings, and patch suggestions
- `outputs/summary.json` with Agent Callability Index (ACI) gates
- `outputs/patches/` with minimal OpenAPI-style patch files
- `outputs/mcp/` with generated MCP tool descriptors
- `outputs/dashboard.html` with leaderboard and drift diagnostics
