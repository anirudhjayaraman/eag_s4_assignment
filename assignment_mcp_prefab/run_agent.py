"""
Agent runner for the Session 4 MCP + Prefab assignment.

Connects to server.py as an MCP client over stdio, then uses a local Ollama
model or Gemini model to drive an agentic loop that:
  1. Searches the internet  (internet_research)
  2. Saves the result       (local_file_crud)
  3. Reads it back          (local_file_crud)
  4. Renders a dashboard    (prefab_research_dashboard)

Prompts come from AGENT_PROMPT.md (each "## Prompt N — Title" section + its
```text fenced block). After each run, the runner injects metadata.tools_invoked
into the just-saved record so the Prefab dashboard shows ✓/✗ proof per tool.

Examples (from s4_code/):
    uv run python assignment_mcp_prefab/run_agent.py                 # run ALL prompts
    uv run python assignment_mcp_prefab/run_agent.py --list          # list prompts and exit
    uv run python assignment_mcp_prefab/run_agent.py --prompt 1      # run a single one
    uv run python assignment_mcp_prefab/run_agent.py --prompts 1,3   # run a subset
    uv run python assignment_mcp_prefab/run_agent.py --all --provider gemini

Requires for the Ollama provider:
    - Ollama running locally (ollama serve)
    - A model pulled (default: qwen2.5-coder:7b, override with OLLAMA_MODEL)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load .env from s4_code/ (one level up from this file)
load_dotenv(Path(__file__).parent.parent / ".env")

try:
    from google import genai
except ImportError:
    genai = None

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

# Gemini tier: try the paid/preferred model first, fall back to the free model
# only when the primary returns a quota / rate-limit / billing error. Once we
# fall back this session, we stay on the fallback to avoid hammering the
# exhausted quota.
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-pro")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

MAX_ITERATIONS = 15
LLM_TIMEOUT = 180

_gemini_model_locked: str | None = None  # set to fallback after primary exhausted

HERE = Path(__file__).parent
PROMPTS_PATH = HERE / "AGENT_PROMPT.md"
DEFAULT_STORE_PATH = HERE / "data" / "research_notes.json"
STORE_PATH = Path(os.getenv("RESEARCH_STORE_PATH", str(DEFAULT_STORE_PATH))).expanduser()

EXPECTED_TOOLS = ("internet_research", "local_file_crud", "prefab_research_dashboard")


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_ollama(prompt: str) -> str:
    """Blocking call to Ollama's /api/generate endpoint."""
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["response"]
    except requests.ConnectionError:
        raise RuntimeError(
            f"Can't reach Ollama at {OLLAMA_HOST}. Is it running? Try: ollama serve"
        )
    except requests.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error: {e}. Did you pull the model? Try: ollama pull {OLLAMA_MODEL}"
        )


def _is_quota_error(exc: Exception) -> bool:
    """Heuristic: does this Gemini error look like quota / rate-limit / billing?"""
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in (
            "resource_exhausted",
            "quota",
            "rate limit",
            "rate-limit",
            "ratelimit",
            "429",
            "permission_denied",
            "billing",
            "free_tier",
            "exceeded",
        )
    )


def call_gemini(prompt: str) -> str:
    """Call Gemini, preferring the paid model; fall back to the free one on quota."""
    global _gemini_model_locked
    if not genai:
        raise RuntimeError("google-genai package is not installed. Run: uv pip install google-genai")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY environment variable is missing.")

    client = genai.Client()

    # Once we've fallen back to the free tier, stay there for the rest of the run.
    if _gemini_model_locked == GEMINI_FALLBACK_MODEL:
        candidates = [GEMINI_FALLBACK_MODEL]
    else:
        candidates = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]

    last_exc: Exception | None = None
    for model in candidates:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2},
            )
            if _gemini_model_locked is None and model == GEMINI_FALLBACK_MODEL:
                # First successful call already on the fallback (e.g. user has no paid access).
                print(f"  ℹ️  Gemini: using {model} (fallback)")
            elif _gemini_model_locked != model and model == GEMINI_FALLBACK_MODEL:
                # Just transitioned to the fallback because the primary errored above.
                print(f"  ⚠️  Gemini: {GEMINI_PRIMARY_MODEL} exhausted — switched to {model} for the rest of this run.")
            _gemini_model_locked = model
            return response.text
        except Exception as exc:
            last_exc = exc
            if model == GEMINI_PRIMARY_MODEL and _is_quota_error(exc):
                print(f"  ⚠️  Gemini {GEMINI_PRIMARY_MODEL} quota/limit hit: {exc}")
                print(f"      Retrying with {GEMINI_FALLBACK_MODEL}...")
                continue
            raise
    raise last_exc if last_exc else RuntimeError("Gemini call failed for unknown reason")


async def generate(prompt: str, provider: str) -> str:
    """Run the blocking LLM call in a thread so the event loop stays free."""
    loop = asyncio.get_event_loop()
    if provider == "gemini":
        return await loop.run_in_executor(None, call_gemini, prompt)
    else:
        return await loop.run_in_executor(None, call_ollama, prompt)


# ---------------------------------------------------------------------------
# Prompt loading from AGENT_PROMPT.md
# ---------------------------------------------------------------------------

PROMPT_PATTERN = re.compile(
    r'^## Prompt (\d+)\s+[—-]\s+(.+?)\n(.*?)(?=^## |\Z)',
    re.MULTILINE | re.DOTALL,
)
CODE_BLOCK_PATTERN = re.compile(r'```(?:text)?\n(.*?)\n```', re.DOTALL)


def load_prompts(md_path: Path) -> list[dict]:
    """Parse `## Prompt N — Title` sections from AGENT_PROMPT.md.

    Each prompt body is the first fenced code block under its heading.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Prompts file not found: {md_path}")
    text = md_path.read_text(encoding="utf-8")
    prompts: list[dict] = []
    for match in PROMPT_PATTERN.finditer(text):
        n = int(match.group(1))
        title = match.group(2).strip()
        section = match.group(3)
        code_match = CODE_BLOCK_PATTERN.search(section)
        if not code_match:
            continue
        body = code_match.group(1).strip()
        prompts.append({"n": n, "title": title, "body": body})
    return prompts


def select_prompts(prompts: list[dict], args: argparse.Namespace) -> list[dict]:
    """Pick the prompts to run based on CLI flags. Default: all."""
    if args.prompt is not None:
        chosen = [p for p in prompts if p["n"] == args.prompt]
        if not chosen:
            raise SystemExit(f"No prompt with n={args.prompt}. Use --list to see options.")
        return chosen
    if args.prompts:
        wanted = set()
        for token in args.prompts.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                wanted.add(int(token))
            except ValueError:
                raise SystemExit(f"Bad --prompts value: {token!r}. Use comma-separated ints.")
        chosen = [p for p in prompts if p["n"] in wanted]
        missing = wanted - {p["n"] for p in chosen}
        if missing:
            raise SystemExit(f"Unknown prompt numbers: {sorted(missing)}. Use --list to see options.")
        return chosen
    return prompts


# ---------------------------------------------------------------------------
# JSON store helpers (for injecting tools_invoked after a run)
# ---------------------------------------------------------------------------

def inject_tools_invoked(record_id: str | None, tools_invoked: list[str], prompt_label: str) -> None:
    """Patch the saved record so the dashboard can render ✓/✗ proof badges.

    Also annotates which prompt produced the record. We write directly rather
    than going through MCP — this is runner housekeeping, not a tool the LLM
    is being graded on.
    """
    if not record_id or not STORE_PATH.exists():
        return
    try:
        records = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(records, list):
        return
    for record in records:
        if record.get("id") == record_id:
            metadata = record.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            metadata["tools_invoked"] = sorted(set(tools_invoked))
            metadata["agent_prompt"] = prompt_label
            record["metadata"] = metadata
            break
    else:
        return
    STORE_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tool-call parsing helpers
# ---------------------------------------------------------------------------

def describe_tools(tools) -> str:
    """Build a numbered description of each MCP tool for the system prompt."""
    lines = []
    for i, t in enumerate(tools, 1):
        props = (t.inputSchema or {}).get("properties", {})
        params = ", ".join(
            f"{n}: {p.get('type', '?')}" for n, p in props.items()
        ) or "no params"
        lines.append(f"{i}. {t.name}({params}) — {t.description or ''}")
    return "\n".join(lines)


def coerce(value: str, schema_type: str):
    """Convert a string argument to the type declared in the tool schema."""
    if schema_type == "integer":
        return int(value)
    if schema_type == "number":
        return float(value)
    if schema_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    if schema_type == "array":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [s.strip().strip('"').strip("'") for s in value.strip("[]").split(",")]
    if schema_type == "object":
        # The LLM may send a JSON string for dict params — parse it
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return {}
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def resolve_schema_type(info: dict) -> str:
    """Extract the effective type from a JSON Schema property, handling anyOf."""
    if "type" in info:
        return info["type"]
    for variant in info.get("anyOf", []):
        t = variant.get("type", "")
        if t and t != "null":
            return t
    return "string"


def first_directive(text: str) -> str:
    """Pick the first line that looks like our protocol."""
    for line in (text or "").splitlines():
        s = line.strip().lstrip("`").lstrip()
        if s.startswith("FUNCTION_CALL:") or s.startswith("FINAL_ANSWER:"):
            return s
    return (text or "").strip()


def parse_function_call(text: str) -> tuple[str, list[str]]:
    """Parse both pipe-delimited and parenthesized function call formats."""
    _, call = text.split(":", 1)
    call = call.strip()

    paren_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)$', call, re.DOTALL)
    if paren_match:
        func_name = paren_match.group(1)
        args_str = paren_match.group(2).strip()
        if not args_str:
            return func_name, []
        raw_args = []
        current = []
        depth = 0
        in_quote = None
        for ch in args_str:
            if ch in ('"', "'") and in_quote is None:
                in_quote = ch
            elif ch == in_quote:
                in_quote = None
            elif in_quote is None:
                if ch in ('(', '[', '{'):
                    depth += 1
                elif ch in (')', ']', '}'):
                    depth -= 1
                elif ch == ',' and depth == 0:
                    raw_args.append(''.join(current).strip())
                    current = []
                    continue
            current.append(ch)
        if current:
            raw_args.append(''.join(current).strip())
        cleaned = []
        for arg in raw_args:
            arg = arg.strip()
            if (arg.startswith('"') and arg.endswith('"')) or \
               (arg.startswith("'") and arg.endswith("'")):
                arg = arg[1:-1]
            cleaned.append(arg)
        return func_name, cleaned

    parts = [p.strip() for p in call.split("|")]
    return parts[0], parts[1:]


def extract_created_record_id(payload: str) -> str | None:
    """Pull the id out of a local_file_crud create response, if present."""
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or not parsed.get("ok"):
        return None
    record = parsed.get("record")
    if isinstance(record, dict):
        return record.get("id")
    return None


# ---------------------------------------------------------------------------
# Per-prompt agent loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """You are a research agent that uses MCP tools to complete tasks.

Available tools:
{tools_desc}

Respond with EXACTLY ONE line, in one of these two formats:
  FUNCTION_CALL: tool_name("arg1", "arg2", ...)
  FINAL_ANSWER: <short natural-language summary of what you did>

IMPORTANT: Use parentheses and quotes to format arguments, like a Python function call. Do NOT use pipe "|" separators.

Examples of correct FUNCTION_CALL format:
  FUNCTION_CALL: internet_research("Tata Sons ownership")
  FUNCTION_CALL: internet_research("Tata Sons ownership", 3000)
  FUNCTION_CALL: local_file_crud("create", "", "Tata Sons Ownership", "The ownership details...", "https://example.com", '["tata-sons","ownership"]', '{{"title":"Tata Sons Ownership","headline_cards":[]}}')
  FUNCTION_CALL: local_file_crud("list")
  FUNCTION_CALL: prefab_research_dashboard()

Rules:
- Output only the single directive line. No prose, no markdown, no code fences.
- Use parentheses and quotes `tool_name("arg1")`, NOT pipes `|`.
- Provide args in the exact order of the tool's parameters.
- Do not invent tools that are not listed above.
- After each FUNCTION_CALL you'll receive the result; use it to decide the NEXT DIFFERENT step.
- NEVER repeat a tool call that already succeeded. Move on to the next step.
- When the task is complete, emit FINAL_ANSWER.
- For the local_file_crud tool, use these operations: create, read, update, delete, list.
- For arrays like tags, format them as JSON arrays e.g. ["tag1","tag2"].
- When calling prefab_research_dashboard, you can pass a record_id or leave it empty.
- CRITICAL: For the metadata parameter of local_file_crud, pass a raw JSON object
  (NOT a quoted string). Example: {{"title":"My Title"}} not "{{\\"title\\":\\"My Title\\"}}".
  If the metadata is rejected, try again with simplified metadata containing only
  headline_cards and ownership_rows — do NOT keep retrying with the same format.
"""


async def run_prompt(
    session: ClientSession,
    tools,
    task: str,
    provider: str,
) -> dict:
    """Run one agent loop. Returns {tools_invoked, created_record_id, final_answer, completed}."""
    tools_desc = describe_tools(tools)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tools_desc=tools_desc)

    history: list[str] = []
    last_call: str | None = None
    tools_invoked: set[str] = set()
    tool_call_counts: dict[str, int] = {}  # per-tool call counter
    TOOL_CALL_LIMITS = {"internet_research": 3}  # max calls per tool
    created_record_id: str | None = None
    final_answer: str | None = None
    completed = False

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Iteration {iteration} ---")
        context = "\n".join(history) if history else "(no prior steps)"
        prompt = (
            f"{system_prompt}\n"
            f"Task: {task}\n\n"
            f"Previous steps:\n{context}\n\n"
            f"What is your next single action? Do NOT repeat a previous step."
        )

        try:
            raw = await generate(prompt, provider)
        except Exception as e:
            print(f"❌ LLM error ({provider}): {e}")
            break

        text = first_directive(raw)
        print(f"🤖 LLM: {text}")

        if text.startswith("FINAL_ANSWER:"):
            final_answer = text
            completed = True
            print("\n" + "=" * 70)
            print("✅ Agent completed!")
            print(text)
            break

        if not text.startswith("FUNCTION_CALL:"):
            print("⚠️  Unexpected response format — stopping.")
            print(f"Raw model output:\n{raw}")
            break

        func_name, raw_args = parse_function_call(text)

        call_sig = f"{func_name}|{'|'.join(raw_args)}"
        if call_sig == last_call:
            nudge = (
                f"Iteration {iteration}: SKIPPED — you already called {func_name} "
                f"with the same arguments and it succeeded. "
                f"Move to the NEXT step in the task. Do NOT call {func_name} again."
            )
            print("  🔄 Duplicate call detected — nudging model to next step")
            history.append(nudge)
            continue

        # Guard: cap per-tool calls to prevent search loops
        tool_call_counts[func_name] = tool_call_counts.get(func_name, 0) + 1
        limit = TOOL_CALL_LIMITS.get(func_name)
        if limit and tool_call_counts[func_name] > limit:
            nudge = (
                f"Iteration {iteration}: You have already called {func_name} "
                f"{limit} times. You MUST move on to the next tool now. "
                f"Use the data you already have."
            )
            print(f"  🛑 {func_name} call limit ({limit}) exceeded — forcing next step")
            history.append(nudge)
            continue

        tool = next((t for t in tools if t.name == func_name), None)
        if tool is None:
            msg = f"Unknown tool {func_name!r}"
            print(f"⚠️  {msg}")
            history.append(f"Iteration {iteration}: {msg}")
            continue

        props = (tool.inputSchema or {}).get("properties", {})
        arguments = {}
        for (name, info), val in zip(props.items(), raw_args):
            arguments[name] = coerce(val, resolve_schema_type(info))

        print(f"  → {func_name}({json.dumps(arguments, default=str)[:200]})")
        try:
            result = await session.call_tool(func_name, arguments=arguments)
            payload = (
                result.content[0].text
                if result.content and hasattr(result.content[0], "text")
                else str(result)
            )
            tools_invoked.add(func_name)
            if func_name == "local_file_crud" and arguments.get("operation") == "create":
                created_record_id = extract_created_record_id(payload) or created_record_id
        except Exception as e:
            payload = f"ERROR: {e}"

        last_call = call_sig

        display_payload = payload[:500] + ("..." if len(payload) > 500 else "")
        print(f"  ← {display_payload}")
        history.append(
            f"Iteration {iteration}: called {func_name}({json.dumps(arguments, default=str)[:150]}) → {payload[:300]}"
        )
    else:
        print(f"\n⚠️  Reached MAX_ITERATIONS ({MAX_ITERATIONS}) without FINAL_ANSWER.")

    return {
        "tools_invoked": sorted(tools_invoked),
        "created_record_id": created_record_id,
        "final_answer": final_answer,
        "completed": completed,
    }


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def print_prompt_index(prompts: list[dict]) -> None:
    print("Available prompts (from AGENT_PROMPT.md):")
    for p in prompts:
        print(f"  {p['n']}: {p['title']}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one or more AGENT_PROMPT.md prompts through the assignment MCP server.",
    )
    parser.add_argument("--list", action="store_true", help="List prompts and exit.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--prompt", type=int, help="Run a single prompt by number.")
    selection.add_argument("--prompts", type=str, help="Run a subset, e.g. --prompts 1,3,5")
    selection.add_argument("--all", action="store_true", help="Run every prompt (default).")
    parser.add_argument(
        "--provider",
        choices=["ollama", "gemini"],
        help="Which LLM provider to use (default: gemini if API key present, else ollama).",
    )
    args = parser.parse_args()

    prompts = load_prompts(PROMPTS_PATH)
    if not prompts:
        raise SystemExit(f"No prompts parsed from {PROMPTS_PATH}. Check the heading format.")

    if args.list:
        print_prompt_index(prompts)
        return

    selected = select_prompts(prompts, args)

    provider = args.provider
    if not provider:
        provider = "gemini" if os.getenv("GEMINI_API_KEY") else "ollama"

    server_script = str(HERE / "server.py")
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", server_script],
    )

    print(f"✓ Will run {len(selected)} prompt(s) via {provider.upper()}: "
          f"{', '.join(str(p['n']) for p in selected)}")

    summaries: list[dict] = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Connected to assignment MCP server")
            tools = (await session.list_tools()).tools
            print(f"✓ Loaded {len(tools)} tools\n")

            for prompt in selected:
                label = f"Prompt {prompt['n']}: {prompt['title']}"
                print("\n" + "█" * 70)
                print(f"▶ {label}")
                print("█" * 70)
                print(f"📋 Task:\n{prompt['body']}\n")
                print("=" * 70)

                result = await run_prompt(session, tools, prompt["body"], provider)

                inject_tools_invoked(
                    result["created_record_id"],
                    result["tools_invoked"],
                    label,
                )

                all_three = set(EXPECTED_TOOLS).issubset(result["tools_invoked"])
                summaries.append({
                    "label": label,
                    "completed": result["completed"],
                    "all_three": all_three,
                    "tools_invoked": result["tools_invoked"],
                    "created_record_id": result["created_record_id"],
                    "final_answer": result["final_answer"],
                })

                print("\n--- Per-prompt summary ---")
                print(f"  Completed (FINAL_ANSWER): {result['completed']}")
                print(f"  Tools invoked: {result['tools_invoked']}")
                print(f"  All 3 expected tools called: {all_three}")
                print(f"  Created record id: {result['created_record_id']}")

    print("\n" + "=" * 70)
    print("📊 OVERALL RUN SUMMARY")
    print("=" * 70)
    for s in summaries:
        mark = "✓" if s["all_three"] and s["completed"] else "✗"
        print(f"  {mark} {s['label']}")
        print(f"      tools_invoked: {s['tools_invoked']}")
        print(f"      record_id: {s['created_record_id']}")
    print("\n📊 To view the dashboard, run:")
    print("   uv run prefab serve assignment_mcp_prefab/dashboard_app.py")
    print("   Then open http://127.0.0.1:5175 in your browser.")
    print("   (The dashboard renders the most recent record with non-empty metadata.)")


if __name__ == "__main__":
    asyncio.run(main())
