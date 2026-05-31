# MCP + Prefab Assignment

This folder contains a complete Session 4 assignment for **Model Context Protocol (MCP)** and **Prefab UI**.

## Session 4 Context

Session 4 was about MCP as the tool protocol that lets an AI agent discover and call external capabilities in a standard request/response format. The session covered:

- Python basics used in agent work: `code.interact()`, `asyncio`, `pdb`, `dotenv`, decorators, and `try`/`except`.
- Why LLMs need external tools for current facts, precise computation, file operations, and real-world actions.
- How MCP standardizes capabilities such as tools, resources, prompts, ping, sampling, and roots.
- How an MCP client can list server tools, send those tool descriptions to an LLM, and then execute the LLM's chosen tool calls.
- How Prefab can be used with MCP to push UI back to the user instead of returning only text.

## Original Assignment Requirement

> Write your own MCP server with any 3 functions that do these things:
>
> - something related to internet (search, fetch a page, get some data/api, etc)
> - perform CRUD operations on a local file (can be of any type)
> - communicates back to you via any UI.
>
> Then:
>
> uses the Prefab to push the UI related to above in your chrome plugin, web-app, desktop-app, etc.
>
> Then:
>
> show a prompt that forces the Agent to use all of these 3 including the Prefab UI, for example, Find the ownership details of Tata Sons, save those details in a text file and show it to me on a dashboard/webpage, etc. (UI must be made using Prefab).

## What This Submission Builds

This implementation builds a Tata Sons ownership research agent demo. The agent researches official ownership data, saves it locally, verifies the saved file, and renders the answer in a Prefab dashboard.

The MCP server exposes three tools:

| Requirement | Tool | What it does |
|---|---|---|
| Internet | `internet_research` | Searches/fetches internet data from a query or URL. |
| Local file CRUD | `local_file_crud` | Creates, reads, updates, deletes, and lists notes in `data/research_notes.json`, including optional structured `metadata_json`. |
| UI communication | `prefab_research_dashboard` | Returns a Prefab dashboard UI from the MCP server via `@mcp.tool(app=True)`, rendering the saved record and its metadata. |

The dashboard is designed to answer the business question first:

- Promoter public charitable trusts: **65.29%**
- Public / other-than-promoter shareholders: **34.71%**
- The 34.71% is split into body corporates, Indian individuals, and other public charitable trusts.

Those ownership values are not hardcoded in the server. They live in the saved JSON record under `metadata`, and both the MCP UI tool and standalone dashboard render that saved data. The lower "saved records" section is only there to prove the assignment's local file CRUD requirement: the agent saved the researched answer to JSON, and the Prefab UI read that local file back.

By default, the local CRUD store is `data/research_notes.json`. You can point both the MCP server and standalone dashboard at another file with:

```bash
export RESEARCH_STORE_PATH=/path/to/research_notes.json
```

## Setup

Make sure the required packages are installed in the `eag_v3` virtual environment:

```bash
# From the root of eag_v3:
uv pip install prefab-ui fastmcp google-genai python-dotenv requests
```

For the agent runner, you need either:

- **Gemini** (preferred) — set `GEMINI_API_KEY` in `s4_code/.env`. The runner picks Gemini automatically when this key is present. It tries `GEMINI_PRIMARY_MODEL` first (default `gemini-2.5-pro`) and only falls back to `GEMINI_FALLBACK_MODEL` (default `gemini-2.5-flash`) when the primary returns a quota/rate-limit/billing error. Once it falls back, it stays on the fallback for the rest of the run. Override either model via env vars:

  ```bash
  export GEMINI_PRIMARY_MODEL=gemini-2.5-pro
  export GEMINI_FALLBACK_MODEL=gemini-2.5-flash
  ```

- **Ollama** (offline fallback) — `ollama serve` and a pulled model (default `qwen2.5-coder:7b`, override via `OLLAMA_MODEL` in `s4_code/.env`). Used automatically if `GEMINI_API_KEY` is missing, or force it with `--provider ollama`.

### Running from Antigravity (or any IDE terminal)

Just open Antigravity's built-in terminal in this repo and run any of the `uv run python assignment_mcp_prefab/run_agent.py …` commands below. Antigravity is not hosting the agent — `run_agent.py` is — so all you need is for the terminal to see the parent `uv` venv (it will, since `uv run` resolves it from the workspace root) and for `s4_code/.env` to contain `GEMINI_API_KEY`.

## How to Run

### 1. Run the Agent Demo (end-to-end)

This is the main demo. It starts the MCP server, connects a Gemini- or Ollama-powered agent, and exercises all 3 tools in sequence. Prompts are read live from [`AGENT_PROMPT.md`](AGENT_PROMPT.md); every `## Prompt N — Title` section with a ```` ```text ```` block is auto-discovered.

To run **every** prompt and tee the transcript to `agent_log.txt`:

```bash
# From s4_code/:
uv run python assignment_mcp_prefab/run_agent.py | tee assignment_mcp_prefab/agent_log.txt
```

Other selection modes:

```bash
uv run python assignment_mcp_prefab/run_agent.py --list           # list prompts and exit
uv run python assignment_mcp_prefab/run_agent.py --prompt 1       # run just one
uv run python assignment_mcp_prefab/run_agent.py --prompts 1,3,5  # run a subset
uv run python assignment_mcp_prefab/run_agent.py --all --provider gemini
```

For each prompt the agent will:
1. Call `internet_research` to look up the data from a credible source
2. Call `local_file_crud` (create) to save the result into the local JSON file
3. Call `local_file_crud` (list) to confirm it was saved
4. Call `prefab_research_dashboard` to render the dashboard
5. Emit `FINAL_ANSWER`

**Proof that all 3 tools were called.** Two places:
- The transcript (`agent_log.txt`) — every `FUNCTION_CALL: tool_name(...)` line is the canonical proof, plus a per-prompt summary and an overall ✓/✗ table the runner prints at the end.
- The Prefab dashboard — the "MCP Tools Invoked For This Record" card at the top shows ✓ or ✗ for each of the three expected tools. The runner injects `metadata.tools_invoked` into the record the agent created, so the badges reflect what the LLM actually did, not what we hoped it would do.

### 2. View the Standalone Dashboard

After the agent has saved data, view the ownership dashboard in your browser:

```bash
# From s4_code/:
uv run prefab serve assignment_mcp_prefab/dashboard_app.py
```

Then open [http://127.0.0.1:5175](http://127.0.0.1:5175).

### 3. Run the MCP Server Directly

For use with Claude Desktop, FastMCP Inspector, or other MCP hosts:

```bash
# From s4_code/:
uv run python assignment_mcp_prefab/server.py
```

For the FastMCP inspector:

```bash
uv run fastmcp inspect assignment_mcp_prefab/server.py
```

## Demo Prompt

Use the prompt in [AGENT_PROMPT.md](AGENT_PROMPT.md) if you want to manually paste it into an MCP host. The `run_agent.py` script uses this prompt automatically.

## MCP Host Config Example

For an MCP client that launches servers over stdio:

```json
{
  "mcpServers": {
    "research-file-prefab": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/Users/anirudh/Documents/eag_v3/s4_code/assignment_mcp_prefab/server.py"
      ]
    }
  }
}
```

## Files

| File | Purpose |
|---|---|
| `server.py` | MCP server with all 3 tools |
| `run_agent.py` | Agentic loop (Ollama + MCP client) that demos all tools end-to-end |
| `dashboard_app.py` | Standalone Prefab ownership dashboard for browser viewing |
| `AGENT_PROMPT.md` | The prompt that forces the agent to use all 3 tools |
| `data/research_notes.json` | Local JSON store proving create/read/list CRUD operations |
