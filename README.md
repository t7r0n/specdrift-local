# Local API Spec Drift Scoreboard

A local scoreboard for measuring whether an API specification is reliable enough for an agent to call. It scores synthetic OpenAPI-style specs across raw OpenAPI, generated MCP, and routed-agent modes, then suggests minimal spec patches and emits MCP tool descriptors.

Everything runs offline with deterministic fixtures. No live APIs, credentials, external LLMs, or marketplace scraping are required.

## Thesis

Local API spec drift and agent-callability scoreboard.

## Primitives

- Replays the main `specdrift-local` scenario from source-controlled fixtures.
- Pushes degraded `Local API Spec Drift Scoreboard` cases through the same path as clean cases, then compares the evidence.
- Frames `Local API Spec Drift Scoreboard` as a working evaluator rather than a static concept mock.
- Leaves `specdrift-local` generated state outside git while keeping the rebuild path short.

## Reproduce locally

```bash
uv sync
uv run specdrift-local init-demo
uv run specdrift-local score --iterations 20
uv run specdrift-local verify
uv run specdrift-local dashboard
```

## Review packet

- `runs/latest/specdrift.duckdb` with score rows, drift findings, and patch suggestions
- `outputs/summary.json` with Agent Callability Index (ACI) gates
- `outputs/patches/` with minimal OpenAPI-style patch files
- `outputs/mcp/` with generated MCP tool descriptors
- `outputs/dashboard.html` with leaderboard and drift diagnostics

## Confidence checks

```bash
uv run ruff check .
uv run pytest -q
uv run specdrift-local verify
```

## Data limits

`Local API Spec Drift Scoreboard` checks in synthetic fixtures only. Runtime state, dashboards, caches, virtual environments, and generated packs stay out of git.
