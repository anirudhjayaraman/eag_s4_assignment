# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo scope

`s4_code/` is the Session 4 (Model Context Protocol) directory of the EAG V3 course. It is **not** a self-contained Python project — the `pyproject.toml`, `uv.lock`, `.venv`, and `.python-version` (3.12) all live one level up at `/Users/anirudh/Documents/eag_v3/`. Always run commands via `uv run …` so they pick up that parent virtualenv.

## Common commands

All commands run from `s4_code/`.

```bash
# Main Session 4 assignment — end-to-end agent loop hitting all 3 MCP tools.
# Auto-uses Gemini if GEMINI_API_KEY is set, else Ollama. Force one with --provider {gemini,ollama}.
uv run python assignment_mcp_prefab/run_agent.py

# Same run, but tee the transcript (used for the assignment submission).
uv run python assignment_mcp_prefab/run_agent.py | tee assignment_mcp_prefab/agent_log.txt

# Standalone Prefab dashboard (reads assignment_mcp_prefab/data/research_notes.json).
# Serves on http://127.0.0.1:5175
uv run prefab serve assignment_mcp_prefab/dashboard_app.py

# Run the assignment MCP server directly (for Claude Desktop / inspector).
uv run python assignment_mcp_prefab/server.py
uv run fastmcp inspect assignment_mcp_prefab/server.py

# Older inspector pattern (still in README for example_mcp_server.py).
mcp dev example_mcp_server.py

# Prefab lessons (each lesson's README explains which command to use).
uv run prefab serve prefab/01_hello_prefab/hello.py
uv run python prefab/02_state_and_events/counter.py
```

If a package is missing, install into the parent venv:

```bash
# From /Users/anirudh/Documents/eag_v3:
uv pip install prefab-ui fastmcp google-genai python-dotenv requests
```

Ollama prerequisites for `run_agent.py` / `AgenticMCPUsageOllama.py`: `ollama serve` running, with the model named by `OLLAMA_MODEL` pulled (default `qwen2.5-coder:7b`).

## Environment

`s4_code/.env` is the one `python-dotenv` loads (both `run_agent.py` and `talk2mcp.py` reference it). Recognised vars:

- `GEMINI_API_KEY` — toggles the default provider in `run_agent.py`.
- `OLLAMA_MODEL`, `OLLAMA_HOST` — Ollama routing.
- `RESEARCH_STORE_PATH` — overrides the CRUD JSON file path used by both `assignment_mcp_prefab/server.py` and `dashboard_app.py`. Keep them in sync if you point one at a custom file.

## Architecture: the two recurring patterns

Most files here are instances of one of two patterns. Recognising them up front saves re-reading.

### 1. FastMCP server with optional Prefab UI tools

A FastMCP server exposes Python functions as tools via `@mcp.tool()`. The Session 4 twist is `@mcp.tool(app=True)` — a tool that returns a `PrefabApp` instead of a string/dict. The MCP host renders that app inline instead of showing text. `assignment_mcp_prefab/server.py` mixes both kinds: two normal tools (`internet_research`, `local_file_crud`) plus one app tool (`prefab_research_dashboard`). `prefab/03_prefab_in_mcp/server.py` is the minimal teaching version.

The Prefab DSL itself is "nested `with` blocks describe the UI tree" — `PrefabApp` is the root, `Card`/`Column`/`Row`/etc. are children. State (`Rx`) and actions (`SetState`) only matter for interactive lessons (`prefab/02_…`, `prefab/04_…`); the assignment dashboard is read-only.

### 2. FUNCTION_CALL / FINAL_ANSWER agent loop

`run_agent.py`, `talk2mcp.py`, and `AgenticMCPUsageOllama.py` all implement the same loop:

1. Spawn an MCP server over stdio (`StdioServerParameters` + `stdio_client`).
2. `session.list_tools()` and build a numbered description for the prompt.
3. Each iteration: ask the LLM, parse one of two directives, repeat until `FINAL_ANSWER`:
   - `FUNCTION_CALL: tool_name|arg1|arg2` (pipe-delimited; original `talk2mcp.py` style)
   - `FUNCTION_CALL: tool_name("arg1", "arg2")` (parenthesized; preferred in `run_agent.py`)
4. Coerce string args to the schema-declared type before `session.call_tool(...)`.

`run_agent.py` is the most current of the three and handles **both** call syntaxes, plus `anyOf` schemas, plus duplicate-call detection that nudges the model to advance instead of looping. When adding new agent variants, copy from it, not from `talk2mcp.py`.

The pipe vs parenthesized split matters: if you change the prompt to allow one syntax, make sure `parse_function_call` accepts it. `run_agent.py:167` is the parser to update.

## Other notable layouts

- `assignment_mcp_prefab/data/research_notes.json` is the canonical JSON store for the CRUD demo. The dashboard tools look for the **last record that has a non-empty `metadata` dict** as the "selected" record to render — records without metadata only appear in the "saved records" proof table at the bottom.
- `prefab/` is a guided 5-lesson track (00 → 04). Each lesson has its own README that should be read before the code.
- `string_reverser/`, `example_mcp_server.py`, `example2.py`, `talk2mcp.py` are earlier teaching examples. `example_mcp_server.py` includes Windows-only Paint automation guarded by `IS_WINDOWS` — those tools no-op on macOS/Linux.
- `__MACOSX/`, `.ipynb_checkpoints/`, `prefab.zip`, and `.DS_Store` files are artefacts; ignore them rather than editing.
