"""
Self-Healing Meta-Agent for the MCP Assignment Runner.

This script reads agent_log.txt, diagnoses why prompts hit MAX_ITERATIONS
without reaching FINAL_ANSWER, then generates and applies code patches to
run_agent.py and/or server.py so that the next run succeeds.

Architecture:
  Phase 1 — Diagnostic Agent:  Parses the log, classifies each failure into a
                                known failure mode, and emits a structured
                                diagnosis JSON.
  Phase 2 — Repair Agent:      Reads the diagnosis + the source files, writes
                                targeted patches via AST-safe string replacement,
                                then re-runs the agent to verify.

Usage (from s4_code/):
    uv run python assignment_mcp_prefab/self_heal.py
    uv run python assignment_mcp_prefab/self_heal.py --dry-run    # diagnose only
    uv run python assignment_mcp_prefab/self_heal.py --log path/to/agent_log.txt
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent

try:
    from google import genai
except ImportError:
    genai = None

HERE = Path(__file__).parent
DEFAULT_LOG = HERE / "agent_log.txt"
RUN_AGENT_PY = HERE / "run_agent.py"
SERVER_PY = HERE / "server.py"

# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------

FAILURE_MODES = {
    "VALIDATION_TYPE_MISMATCH": (
        "The LLM passes a value whose Python/Pydantic type doesn't match the "
        "tool parameter schema (e.g. str where dict is expected, or vice-versa)."
    ),
    "REPEATED_SEARCH": (
        "The LLM keeps calling internet_research with different queries hoping "
        "for better data, burning through iterations before ever calling "
        "local_file_crud or prefab_research_dashboard."
    ),
    "DUPLICATE_TOOL_CALL": (
        "The LLM re-issues the exact same tool call that already succeeded, "
        "and the dedup logic doesn't nudge it hard enough."
    ),
    "MALFORMED_FUNCTION_CALL": (
        "The LLM's FUNCTION_CALL line can't be parsed — wrong delimiter, "
        "missing quotes, unmatched parens, etc."
    ),
    "PROMPT_TOO_VERBOSE": (
        "The prompt in AGENT_PROMPT.md asks for so much structured metadata "
        "that the LLM spends all iterations trying to construct the payload "
        "correctly instead of finishing the pipeline."
    ),
    "TOOL_RETURNED_HTML": (
        "internet_research fetched a URL but the response was raw HTML "
        "(JavaScript-rendered page), giving the LLM no usable text to save."
    ),
    "UNKNOWN": "Could not classify the failure.",
}


@dataclass
class PromptDiagnosis:
    prompt_number: int
    prompt_title: str
    completed: bool
    iterations_used: int
    tools_invoked: list[str]
    failure_modes: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    suggested_fix: str = ""


@dataclass
class RunDiagnosis:
    log_path: str
    prompts: list[PromptDiagnosis] = field(default_factory=list)
    global_issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 1: Diagnostic Agent — purely rule-based, no LLM needed
# ---------------------------------------------------------------------------

_PROMPT_HEADER = re.compile(r"^▶ Prompt (\d+):\s*(.+)$", re.MULTILINE)
_ITERATION = re.compile(r"^--- Iteration (\d+) ---$", re.MULTILINE)
_FINAL_ANSWER = re.compile(r"^✅ Agent completed!", re.MULTILINE)
_MAX_ITER_HIT = re.compile(r"^⚠️  Reached MAX_ITERATIONS", re.MULTILINE)
_VALIDATION_ERR = re.compile(r"validation error for call\[(\w+)\]", re.MULTILINE)
_TYPE_MISMATCH = re.compile(r"Input should be a valid (dictionary|string|integer|array)", re.MULTILINE)
_HTML_RESPONSE = re.compile(r"← .*<!DOCTYPE html>", re.MULTILINE)
_TOOL_INVOKE = re.compile(r"→ (\w+)\(", re.MULTILINE)
_FUNC_CALL = re.compile(r"^🤖 LLM: FUNCTION_CALL:", re.MULTILINE)
_INTERNET_RESEARCH = re.compile(r"→ internet_research\(", re.MULTILINE)


def _split_prompt_sections(log_text: str) -> list[tuple[int, str, str]]:
    """Split the log into (prompt_number, title, section_text) tuples."""
    headers = list(_PROMPT_HEADER.finditer(log_text))
    if not headers:
        return []
    sections: list[tuple[int, str, str]] = []
    for i, m in enumerate(headers):
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(log_text)
        sections.append((int(m.group(1)), m.group(2), log_text[start:end]))
    return sections


def diagnose_prompt(num: int, title: str, section: str) -> PromptDiagnosis:
    """Classify failures for one prompt section."""
    completed = bool(_FINAL_ANSWER.search(section))
    iterations = _ITERATION.findall(section)
    max_iter = int(iterations[-1]) if iterations else 0
    tools = sorted(set(_TOOL_INVOKE.findall(section)))

    diag = PromptDiagnosis(
        prompt_number=num,
        prompt_title=title,
        completed=completed,
        iterations_used=max_iter,
        tools_invoked=tools,
    )

    if completed:
        return diag

    # --- Check for validation type mismatches ---
    val_errors = _VALIDATION_ERR.findall(section)
    type_mismatches = _TYPE_MISMATCH.findall(section)
    if val_errors:
        diag.failure_modes.append("VALIDATION_TYPE_MISMATCH")
        for expected_type in type_mismatches:
            diag.evidence.append(
                f"Tool expected a valid {expected_type} but received the wrong type"
            )

    # --- Check for repeated search loops ---
    research_calls = _INTERNET_RESEARCH.findall(section)
    if len(research_calls) >= 4:
        diag.failure_modes.append("REPEATED_SEARCH")
        diag.evidence.append(
            f"internet_research was called {len(research_calls)} times — "
            f"the LLM kept searching instead of proceeding to local_file_crud"
        )

    # --- Check for HTML responses (JS-rendered pages) ---
    html_hits = _HTML_RESPONSE.findall(section)
    if html_hits:
        diag.failure_modes.append("TOOL_RETURNED_HTML")
        diag.evidence.append(
            f"internet_research returned raw HTML {len(html_hits)} time(s); "
            f"the target pages likely require JavaScript to render data"
        )

    # --- Check for overly complex metadata construction ---
    if max_iter >= 8 and "VALIDATION_TYPE_MISMATCH" in diag.failure_modes:
        diag.failure_modes.append("PROMPT_TOO_VERBOSE")
        diag.evidence.append(
            "The LLM spent most iterations trying to construct the metadata "
            "payload correctly, hitting validation errors repeatedly"
        )

    if not diag.failure_modes:
        diag.failure_modes.append("UNKNOWN")
        diag.evidence.append("No specific failure pattern matched")

    return diag


def diagnose_log(log_path: Path) -> RunDiagnosis:
    """Full diagnostic pass over agent_log.txt."""
    text = log_path.read_text(encoding="utf-8")
    sections = _split_prompt_sections(text)
    diag = RunDiagnosis(log_path=str(log_path))

    for num, title, section in sections:
        diag.prompts.append(diagnose_prompt(num, title, section))

    # Global issues
    failed = [p for p in diag.prompts if not p.completed]
    if failed:
        modes = set()
        for p in failed:
            modes.update(p.failure_modes)
        if "VALIDATION_TYPE_MISMATCH" in modes:
            diag.global_issues.append(
                "The run_agent.py coerce() function and the server.py tool "
                "parameter types are misaligned — the LLM produces JSON strings "
                "but coerce() or Pydantic converts them to dicts (or vice versa)."
            )
        if "REPEATED_SEARCH" in modes:
            diag.global_issues.append(
                "The system prompt doesn't enforce a hard iteration budget per "
                "tool — the LLM is free to call internet_research endlessly."
            )
    return diag


# ---------------------------------------------------------------------------
# Phase 2: Repair Agent — uses Gemini to generate targeted patches
# ---------------------------------------------------------------------------

REPAIR_SYSTEM_PROMPT = dedent("""\
You are a code-repair agent. You are given:
1. A DIAGNOSIS of why an MCP agent run failed (JSON).
2. The SOURCE CODE of two files: run_agent.py and server.py.

Your job is to output a JSON array of patches. Each patch is an object:
{
  "file": "run_agent.py" or "server.py",
  "find": "<exact multi-line string to find in the file>",
  "replace": "<exact multi-line replacement string>",
  "rationale": "<one-sentence explanation>"
}

Rules:
- The "find" string MUST appear exactly once in the file. Be precise.
- Only patch what is necessary to fix the diagnosed failures.
- Do NOT rewrite entire files. Surgical patches only.
- If the diagnosis mentions VALIDATION_TYPE_MISMATCH where the LLM sends
  a JSON string for a dict parameter, the fix should be in run_agent.py's
  coerce() function to also try json.loads for "object" schema types,
  OR adjust the system prompt to tell the LLM to pass raw JSON objects
  (not quoted strings) for dict parameters.
- If the diagnosis mentions REPEATED_SEARCH, add a counter/guard in
  run_agent.py's run_prompt() that caps internet_research calls at 3
  and force-nudges the LLM to move on.
- If the diagnosis mentions PROMPT_TOO_VERBOSE, simplify the prompt
  instructions in AGENT_PROMPT.md or the system prompt to reduce the
  metadata burden on the LLM.
- Output ONLY the JSON array. No markdown fences, no prose.
""")


def _call_gemini(prompt: str) -> str:
    if not genai:
        raise RuntimeError("google-genai not installed")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set")
    from dotenv import load_dotenv
    load_dotenv(HERE.parent / ".env")
    client = genai.Client()
    response = client.models.generate_content(
        model=os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.5-flash"),
        contents=prompt,
        config={"temperature": 0.2},
    )
    return response.text


def generate_patches(diagnosis: RunDiagnosis) -> list[dict]:
    """Ask the Repair Agent LLM to produce patches given the diagnosis."""
    diag_json = json.dumps(
        {
            "failed_prompts": [
                {
                    "prompt": p.prompt_number,
                    "title": p.prompt_title,
                    "iterations": p.iterations_used,
                    "tools_invoked": p.tools_invoked,
                    "failure_modes": p.failure_modes,
                    "evidence": p.evidence,
                }
                for p in diagnosis.prompts
                if not p.completed
            ],
            "global_issues": diagnosis.global_issues,
        },
        indent=2,
    )

    run_agent_src = RUN_AGENT_PY.read_text(encoding="utf-8")
    server_src = SERVER_PY.read_text(encoding="utf-8")

    prompt = (
        f"{REPAIR_SYSTEM_PROMPT}\n\n"
        f"=== DIAGNOSIS ===\n{diag_json}\n\n"
        f"=== run_agent.py ===\n{run_agent_src}\n\n"
        f"=== server.py ===\n{server_src}\n"
    )

    raw = _call_gemini(prompt)

    # Strip markdown fences if the LLM wraps output
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
    raw = re.sub(r"\n?```\s*$", "", raw.strip())

    try:
        patches = json.loads(raw)
    except json.JSONDecodeError:
        print("❌ Repair agent returned invalid JSON. Raw output:\n")
        print(raw[:2000])
        return []

    if not isinstance(patches, list):
        patches = [patches]
    return patches


def apply_patches(patches: list[dict], dry_run: bool = False) -> list[str]:
    """Apply patches to the source files. Returns list of results."""
    results: list[str] = []
    file_map = {
        "run_agent.py": RUN_AGENT_PY,
        "server.py": SERVER_PY,
    }

    for i, patch in enumerate(patches, 1):
        fname = patch.get("file", "")
        find = patch.get("find", "")
        replace = patch.get("replace", "")
        rationale = patch.get("rationale", "")

        target = file_map.get(fname)
        if not target:
            results.append(f"  Patch {i}: SKIP — unknown file {fname!r}")
            continue

        content = target.read_text(encoding="utf-8")
        count = content.count(find)

        if count == 0:
            results.append(
                f"  Patch {i} ({fname}): SKIP — 'find' string not found.\n"
                f"    Rationale: {rationale}\n"
                f"    Find (first 120 chars): {find[:120]!r}"
            )
            continue
        if count > 1:
            results.append(
                f"  Patch {i} ({fname}): SKIP — 'find' string matched {count} times (ambiguous)."
            )
            continue

        if dry_run:
            results.append(
                f"  Patch {i} ({fname}): WOULD APPLY — {rationale}"
            )
        else:
            new_content = content.replace(find, replace, 1)
            target.write_text(new_content, encoding="utf-8")
            results.append(
                f"  Patch {i} ({fname}): APPLIED ✓ — {rationale}"
            )

    return results


# ---------------------------------------------------------------------------
# Phase 3: Verify — re-run the agent and check
# ---------------------------------------------------------------------------

def verify_fix() -> bool:
    """Re-run the agent and check if all prompts now complete."""
    print("\n🔄 Re-running agent to verify fixes...")
    result = subprocess.run(
        ["uv", "run", "python", str(RUN_AGENT_PY)],
        cwd=str(HERE.parent),
        capture_output=True,
        text=True,
        timeout=600,
    )

    output = result.stdout + result.stderr
    # Write the new log
    new_log = HERE / "agent_log.txt"
    new_log.write_text(output, encoding="utf-8")

    # Check results
    successes = output.count("✅ Agent completed!")
    failures = output.count("Reached MAX_ITERATIONS")
    total = successes + failures

    print(f"\n📊 Verification: {successes}/{total} prompts completed successfully")
    if failures > 0:
        print(f"   ⚠️  {failures} prompt(s) still failing")
    return failures == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Self-healing meta-agent for the MCP runner.")
    parser.add_argument(
        "--log", type=Path, default=DEFAULT_LOG,
        help="Path to agent_log.txt to analyze.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Diagnose and generate patches but don't apply them.",
    )
    parser.add_argument(
        "--diagnose-only", action="store_true",
        help="Only run the diagnostic phase, skip repair.",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Apply patches but skip the verification re-run.",
    )
    args = parser.parse_args()

    if not args.log.exists():
        print(f"❌ Log file not found: {args.log}")
        print("   Run the agent first: uv run python assignment_mcp_prefab/run_agent.py | tee assignment_mcp_prefab/agent_log.txt")
        sys.exit(1)

    # ── Phase 1: Diagnose ──
    print("═" * 70)
    print("  PHASE 1: DIAGNOSTIC AGENT")
    print("═" * 70)

    diagnosis = diagnose_log(args.log)

    failed = [p for p in diagnosis.prompts if not p.completed]
    passed = [p for p in diagnosis.prompts if p.completed]

    print(f"\n📋 Analyzed {len(diagnosis.prompts)} prompt(s):")
    for p in diagnosis.prompts:
        mark = "✅" if p.completed else "❌"
        print(f"  {mark} Prompt {p.prompt_number}: {p.prompt_title}")
        if not p.completed:
            print(f"     Iterations used: {p.iterations_used}")
            print(f"     Failure modes:   {', '.join(p.failure_modes)}")
            for ev in p.evidence:
                print(f"     Evidence:        {ev}")

    if diagnosis.global_issues:
        print("\n🌐 Global issues detected:")
        for issue in diagnosis.global_issues:
            print(f"  • {issue}")

    if not failed:
        print("\n✅ All prompts completed successfully! No repairs needed.")
        return

    print(f"\n⚠️  {len(failed)} of {len(diagnosis.prompts)} prompts failed.")

    if args.diagnose_only:
        print("\n(--diagnose-only flag set, stopping here)")
        return

    # ── Phase 2: Repair ──
    print("\n" + "═" * 70)
    print("  PHASE 2: REPAIR AGENT")
    print("═" * 70)

    try:
        patches = generate_patches(diagnosis)
    except RuntimeError as e:
        print(f"\n❌ Cannot run repair agent: {e}")
        print("   Falling back to built-in fixes based on diagnosis...")
        patches = _builtin_fixes(diagnosis)

    if not patches:
        print("\n⚠️  No patches generated. Manual intervention required.")
        return

    print(f"\n🔧 Generated {len(patches)} patch(es):")
    results = apply_patches(patches, dry_run=args.dry_run)
    for r in results:
        print(r)

    if args.dry_run:
        print("\n(--dry-run flag set, patches NOT applied)")
        return

    # ── Phase 3: Verify ──
    if args.no_verify:
        print("\n(--no-verify flag set, skipping re-run)")
        return

    all_pass = verify_fix()
    if all_pass:
        print("\n🎉 All prompts now complete successfully! Self-heal succeeded.")
    else:
        print("\n⚠️  Some prompts still failing. Run self_heal.py again for another pass,")
        print("   or inspect the new agent_log.txt for remaining issues.")


def _builtin_fixes(diagnosis: RunDiagnosis) -> list[dict]:
    """Deterministic patches for known failure modes — no LLM required."""
    patches: list[dict] = []
    modes = set()
    for p in diagnosis.prompts:
        if not p.completed:
            modes.update(p.failure_modes)

    if "VALIDATION_TYPE_MISMATCH" in modes:
        # Fix coerce() to handle "object" schema type by trying json.loads
        patches.append({
            "file": "run_agent.py",
            "find": (
                '    if value.startswith("[") or value.startswith("{"):\n'
                '        try:\n'
                '            return json.loads(value)\n'
                '        except json.JSONDecodeError:\n'
                '            pass\n'
                '    return value'
            ),
            "replace": (
                '    if schema_type == "object":\n'
                '        # The LLM may send a JSON string for dict params — parse it\n'
                '        if isinstance(value, dict):\n'
                '            return value\n'
                '        try:\n'
                '            parsed = json.loads(value)\n'
                '            if isinstance(parsed, dict):\n'
                '                return parsed\n'
                '        except (json.JSONDecodeError, TypeError):\n'
                '            pass\n'
                '        return {}\n'
                '    if value.startswith("[") or value.startswith("{"):\n'
                '        try:\n'
                '            return json.loads(value)\n'
                '        except json.JSONDecodeError:\n'
                '            pass\n'
                '    return value'
            ),
            "rationale": (
                "Add explicit handling for 'object' schema type in coerce() so "
                "JSON strings are parsed into dicts before being passed to Pydantic."
            ),
        })

        # Also add a note to the system prompt about metadata format
        patches.append({
            "file": "run_agent.py",
            "find": (
                '- When calling prefab_research_dashboard, you can pass a record_id or leave it empty.\n'
                '"""'
            ),
            "replace": (
                '- When calling prefab_research_dashboard, you can pass a record_id or leave it empty.\n'
                '- CRITICAL: For the metadata parameter of local_file_crud, pass a raw JSON object\n'
                '  (NOT a quoted string). Example: {"title":"My Title"} not "{\\"title\\":\\"My Title\\"}"".\n'
                '  If the metadata is rejected, try again with simplified metadata containing only\n'
                '  headline_cards and ownership_rows — do NOT keep retrying with the same format.\n'
                '"""'
            ),
            "rationale": (
                "Tell the LLM explicitly how to format the metadata parameter "
                "and to simplify on failure instead of retrying the same format."
            ),
        })

    if "REPEATED_SEARCH" in modes:
        # Add a per-tool call counter with a cap on internet_research
        patches.append({
            "file": "run_agent.py",
            "find": (
                '    tools_invoked: set[str] = set()\n'
                '    created_record_id: str | None = None'
            ),
            "replace": (
                '    tools_invoked: set[str] = set()\n'
                '    tool_call_counts: dict[str, int] = {}  # per-tool call counter\n'
                '    TOOL_CALL_LIMITS = {"internet_research": 3}  # max calls per tool\n'
                '    created_record_id: str | None = None'
            ),
            "rationale": "Initialize per-tool call counters to prevent search loops.",
        })

        # Add the guard check before dispatching
        patches.append({
            "file": "run_agent.py",
            "find": (
                '        tool = next((t for t in tools if t.name == func_name), None)\n'
                '        if tool is None:'
            ),
            "replace": (
                '        # Guard: cap per-tool calls to prevent search loops\n'
                '        tool_call_counts[func_name] = tool_call_counts.get(func_name, 0) + 1\n'
                '        limit = TOOL_CALL_LIMITS.get(func_name)\n'
                '        if limit and tool_call_counts[func_name] > limit:\n'
                '            nudge = (\n'
                '                f"Iteration {iteration}: You have already called {func_name} "\n'
                '                f"{limit} times. You MUST move on to the next tool now. "\n'
                '                f"Use the data you already have."\n'
                '            )\n'
                '            print(f"  🛑 {func_name} call limit ({limit}) exceeded — forcing next step")\n'
                '            history.append(nudge)\n'
                '            continue\n'
                '\n'
                '        tool = next((t for t in tools if t.name == func_name), None)\n'
                '        if tool is None:'
            ),
            "rationale": (
                "Cap internet_research at 3 calls per prompt to prevent the LLM "
                "from burning all iterations on search without proceeding."
            ),
        })

    return patches


if __name__ == "__main__":
    main()
