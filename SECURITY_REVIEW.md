# Security Review

## Scope

Local CLI, synthetic OpenAPI-style specs, deterministic agent-callability simulator, DuckDB result store, generated patch files, generated MCP descriptors, and static HTML dashboard.

## Current Assessment

The project is offline by design. It does not call live APIs, scrape marketplaces, invoke agents, execute generated MCP tools, or load secrets. It has no network client, subprocess execution, shell execution, credential handling, or global configuration writes.

## Controls

- Spec fixtures are parsed into Pydantic models.
- Generated descriptors and patches stay under project-local `outputs/`.
- DuckDB writes use parameterized inserts.
- Dashboard rendering uses Jinja autoescaping.
- Runtime state, outputs, caches, and virtual environments are ignored by git.

## Focused Scan

Reviewed package code for command execution, network clients, unsafe deserialization, credential handling, live API calls, agent execution, generated MCP execution, and global configuration writes. The implementation contains no subprocess calls, shell execution, sockets, HTTP clients, pickle, dynamic evaluation, marketplace scraping, external agents, or generated-tool execution.

## Attack-Path Analysis

The realistic attacker-controlled surface is local spec fixture JSON. Fixture content can influence score rows, patch JSON files, generated MCP descriptors, and dashboard text. Fixtures are parsed through Pydantic models, dashboard text is Jinja-autoescaped, and fixture content cannot reach a shell, a network client, credential material, or a privileged write path. Runtime outputs are excluded from the public repo.

## Review Status

Passed focused local security review on 2026-05-17. No high-impact attacker-reachable path identified.
