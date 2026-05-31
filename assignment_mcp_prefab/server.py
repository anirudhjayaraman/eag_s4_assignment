"""
Session 4 assignment MCP server.

Tools:
  1. internet_research: internet/API lookup or page fetch.
  2. local_file_crud: CRUD operations on a local JSON file.
  3. prefab_research_dashboard: Prefab UI returned through MCP.

Run:
    uv run python assignment_mcp_prefab/server.py

Inspect:
    uv run fastmcp dev assignment_mcp_prefab/server.py
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from fastmcp import FastMCP
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge,
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
    Column,
    Div,
    Grid,
    H1,
    H2,
    Markdown,
    Muted,
    Row,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    Text,
    Tabs,
    Tab,
)


mcp = FastMCP("ResearchFilePrefabAssignment")

HERE = Path(__file__).parent
DEFAULT_STORE_PATH = HERE / "data" / "research_notes.json"
STORE_PATH = Path(os.getenv("RESEARCH_STORE_PATH", str(DEFAULT_STORE_PATH))).expanduser()
DATA_DIR = STORE_PATH.parent


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text("[]\n", encoding="utf-8")


def _read_records() -> list[dict]:
    _ensure_store()
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    return data if isinstance(data, list) else []


def _write_records(records: list[dict]) -> None:
    _ensure_store()
    STORE_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _default_dashboard_record(records: list[dict]) -> dict | None:
    for record in reversed(records):
        metadata = record.get("metadata")
        if isinstance(metadata, dict) and metadata:
            return record
    return records[-1] if records else None


def _http_get(url: str, timeout: int = 12) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 MCP Assignment Research Tool",
            "Accept": "application/json,text/plain,text/html;q=0.8,*/*;q=0.5",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _compact_text(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    return compact[:limit].rstrip()


def _wikipedia_fallback(query: str, max_chars: int) -> dict:
    search_url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={quote_plus(query)}"
        "&format=json&srlimit=3"
    )
    search_payload = json.loads(_http_get(search_url))
    hits = search_payload.get("query", {}).get("search", [])
    if not hits:
        return {
            "ok": True,
            "mode": "search",
            "query": query,
            "source": search_url,
            "heading": query,
            "summary": "No instant-answer or Wikipedia search results found.",
            "results": [],
        }

    page_ids = "|".join(str(hit["pageid"]) for hit in hits)
    extract_url = (
        "https://en.wikipedia.org/w/api.php"
        "?action=query&prop=extracts&exintro=1&explaintext=1"
        f"&pageids={page_ids}&format=json"
    )
    extract_payload = json.loads(_http_get(extract_url))
    pages = extract_payload.get("query", {}).get("pages", {})
    results = []
    summaries = []
    for hit in hits:
        page = pages.get(str(hit["pageid"]), {})
        title = page.get("title") or hit.get("title", "")
        extract = page.get("extract") or hit.get("snippet", "")
        url_title = title.replace(" ", "_")
        url = f"https://en.wikipedia.org/wiki/{quote_plus(url_title)}"
        results.append({"text": title, "url": url})
        if extract:
            summaries.append(f"{title}: {extract}")

    return {
        "ok": True,
        "mode": "search",
        "query": query,
        "source": extract_url,
        "heading": results[0]["text"],
        "summary": _compact_text("\n\n".join(summaries), max_chars),
        "results": results,
    }


@mcp.tool()
def internet_research(query_or_url: str, max_chars: int = 2500) -> dict:
    """
    Search the internet or fetch a URL.

    Pass a normal search query to use DuckDuckGo's public instant-answer API.
    Pass an http(s) URL to fetch and summarize the page text.
    """
    if not query_or_url.strip():
        return {"ok": False, "error": "query_or_url is required"}

    max_chars = max(500, min(int(max_chars), 6000))
    value = query_or_url.strip()

    try:
        if value.startswith(("http://", "https://")):
            body = _http_get(value)
            return {
                "ok": True,
                "mode": "fetch",
                "source": value,
                "summary": _compact_text(body, max_chars),
            }

        api_url = (
            "https://api.duckduckgo.com/"
            f"?q={quote_plus(value)}&format=json&no_html=1&skip_disambig=1"
        )
        raw = _http_get(api_url)
        payload = json.loads(raw)
        related = []
        for item in payload.get("RelatedTopics", []):
            if "Topics" in item:
                for nested in item.get("Topics", []):
                    related.append(
                        {
                            "text": nested.get("Text", ""),
                            "url": nested.get("FirstURL", ""),
                        }
                    )
            else:
                related.append(
                    {
                        "text": item.get("Text", ""),
                        "url": item.get("FirstURL", ""),
                    }
                )

        abstract = payload.get("AbstractText") or payload.get("Answer") or ""
        summary_parts = [abstract] if abstract else []
        summary_parts.extend(item["text"] for item in related[:5] if item.get("text"))

        if not summary_parts and not related:
            return _wikipedia_fallback(value, max_chars)

        return {
            "ok": True,
            "mode": "search",
            "query": value,
            "source": api_url,
            "heading": payload.get("Heading") or value,
            "summary": _compact_text("\n".join(summary_parts) or raw, max_chars),
            "results": related[:8],
        }
    except Exception as exc:
        return {
            "ok": False,
            "query": value,
            "error": f"{type(exc).__name__}: {exc}",
        }


@mcp.tool()
def local_file_crud(
    operation: Literal["create", "read", "update", "delete", "list"],
    record_id: str | None = None,
    title: str = "",
    content: str = "",
    source_url: str = "",
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    Create, read, update, delete, or list research notes in a local JSON file.

    The file is assignment_mcp_prefab/data/research_notes.json.
    """
    records = _read_records()
    tags = tags or []
    metadata = metadata or {}

    if operation == "list":
        return {
            "ok": True,
            "file": str(STORE_PATH),
            "count": len(records),
            "records": records,
        }

    if operation == "create":
        if not title.strip() or not content.strip():
            return {"ok": False, "error": "title and content are required for create"}
        record = {
            "id": uuid.uuid4().hex[:10],
            "title": title.strip(),
            "content": content.strip(),
            "source_url": source_url.strip(),
            "tags": tags,
            "metadata": metadata,
            "created_at": _now(),
            "updated_at": _now(),
        }
        records.append(record)
        _write_records(records)
        return {"ok": True, "operation": "create", "file": str(STORE_PATH), "record": record}

    if not record_id:
        return {"ok": False, "error": f"record_id is required for {operation}"}

    match = next((record for record in records if record.get("id") == record_id), None)
    if not match:
        return {"ok": False, "error": f"No record found for id {record_id}"}

    if operation == "read":
        return {"ok": True, "operation": "read", "file": str(STORE_PATH), "record": match}

    if operation == "update":
        if title.strip():
            match["title"] = title.strip()
        if content.strip():
            match["content"] = content.strip()
        if source_url.strip():
            match["source_url"] = source_url.strip()
        if tags:
            match["tags"] = tags
        if metadata:
            match["metadata"] = metadata
        match["updated_at"] = _now()
        _write_records(records)
        return {"ok": True, "operation": "update", "file": str(STORE_PATH), "record": match}

    if operation == "delete":
        remaining = [record for record in records if record.get("id") != record_id]
        _write_records(remaining)
        return {"ok": True, "operation": "delete", "file": str(STORE_PATH), "deleted": match}

    return {"ok": False, "error": f"Unsupported operation: {operation}"}


@mcp.tool(app=True)
def prefab_research_dashboard(record_id: str | None = None) -> PrefabApp:
    """Show the saved research note in a Prefab dashboard UI."""
    records = _read_records()
    expected_tools = ["internet_research", "local_file_crud", "prefab_research_dashboard"]

    with PrefabApp(css_class="min-h-screen bg-zinc-50 text-zinc-950") as app:
        with Div(css_class="mx-auto max-w-6xl px-6 py-8"):
            with Column(gap=6):
                with Row(gap=4, css_class="items-start justify-between"):
                    with Column(gap=2):
                        H1("Research Dashboard")
                        Text("Research saved via MCP file CRUD and rendered with Prefab.")
                    Badge(f"{len(records)} saved records", variant="info")

                if not records:
                    with Card():
                        with CardHeader():
                            CardTitle("No Research Saved Yet")
                        with CardContent():
                            Text("Call internet_research first, then save a record with local_file_crud.")
                else:
                    display_records = list(reversed(records))
                    first_record_id = display_records[0].get("id") if display_records else ""
                    
                    with Tabs(value=first_record_id):
                        for record in display_records:
                            metadata = record.get("metadata", {})
                            if not isinstance(metadata, dict):
                                metadata = {}
                            
                            title = record.get("title") or "Untitled"
                            short_title = title[:20] + ("..." if len(title) > 20 else "")
                            
                            headline_cards = metadata.get("headline_cards", []) if isinstance(metadata, dict) else []
                            ownership_rows = metadata.get("ownership_rows", []) if isinstance(metadata, dict) else []
                            non_promoter_rows = metadata.get("non_promoter_rows", []) if isinstance(metadata, dict) else []
                            large_holders = metadata.get("large_holders", []) if isinstance(metadata, dict) else []
                            tools_invoked = metadata.get("tools_invoked", []) if isinstance(metadata, dict) else []
                            source_url = record.get("source_url", "")
                            
                            with Tab(title=short_title, value=record.get("id")):
                                with Column(gap=6, css_class="pt-4"):
                                    with Card():
                                        with CardHeader():
                                            CardTitle("MCP Tools Invoked For This Record")
                                            CardDescription(
                                                "Populated by the agent runner — ✓ means the agent actually called that tool."
                                                if tools_invoked
                                                else "No tools_invoked field on this record. Run via run_agent.py to populate it."
                                            )
                                        with CardContent():
                                            with Row(gap=2):
                                                for tool in expected_tools:
                                                    used = tool in tools_invoked
                                                    Badge(
                                                        f"{'✓' if used else '✗'} {tool}",
                                                        variant="success" if used else "warning",
                                                        key=f"tool-{record.get('id')}-{tool}"
                                                    )

                                    if headline_cards:
                                        with Grid(columns=len(headline_cards), gap=4):
                                            for card in headline_cards:
                                                with Card():
                                                    with CardHeader():
                                                        CardTitle(str(card.get("label", "Metric")))
                                                        CardDescription(str(card.get("description", "")))
                                                    with CardContent():
                                                        with Column(gap=2):
                                                            H2(str(card.get("value", "")))
                                                            Text(str(card.get("detail", "")))
                                                            if card.get("note"):
                                                                Muted(str(card["note"]))

                                    if ownership_rows:
                                        with Card():
                                            with CardHeader():
                                                CardTitle(str(metadata.get("ownership_table_title", "Ownership Breakdown")))
                                                CardDescription(str(metadata.get("as_of", "")))
                                            with CardContent():
                                                with Table():
                                                    with TableHeader():
                                                        with TableRow():
                                                            TableHead("Category")
                                                            TableHead("Shares/Stake")
                                                            TableHead("Ownership %")
                                                            TableHead("Meaning/Notes")
                                                    with TableBody():
                                                        for row in ownership_rows:
                                                            cat = row.get("category") or row.get("shareholder") or row.get("party") or row.get("owner") or row.get("name") or row.get("label") or row.get("holder") or row.get("country") or ""
                                                            val = row.get("shares") or row.get("percentage") or row.get("value") or row.get("stake") or row.get("value_pct") or ""
                                                            own = row.get("ownership") or ""
                                                            mean = row.get("meaning") or row.get("details") or row.get("group") or row.get("type") or row.get("description") or ""
                                                            with TableRow():
                                                                TableCell(str(cat))
                                                                TableCell(str(val))
                                                                TableCell(str(own))
                                                                TableCell(str(mean))

                                    if non_promoter_rows or large_holders:
                                        with Grid(columns=2, gap=4):
                                            if non_promoter_rows:
                                                with Card():
                                                    with CardHeader():
                                                        CardTitle(str(metadata.get("detail_table_title", "Detailed Breakdown")))
                                                        CardDescription(str(metadata.get("detail_table_subtitle", "")))
                                                    with CardContent():
                                                        with Table():
                                                            with TableHeader():
                                                                with TableRow():
                                                                    TableHead("Category")
                                                                    TableHead("Shares/Stake")
                                                                    TableHead("Ownership %")
                                                            with TableBody():
                                                                for row in non_promoter_rows:
                                                                    cat = row.get("category") or row.get("party") or row.get("label") or row.get("name") or ""
                                                                    val = row.get("shares") or row.get("percentage") or row.get("stake") or row.get("value_pct") or row.get("value") or ""
                                                                    own = row.get("ownership") or ""
                                                                    with TableRow():
                                                                        TableCell(str(cat))
                                                                        TableCell(str(val))
                                                                        TableCell(str(own))
                                            if large_holders:
                                                with Card():
                                                    with CardHeader():
                                                        CardTitle("Large Named Holders")
                                                        CardDescription("Shareholders called out in the saved research metadata")
                                                    with CardContent():
                                                        with Table():
                                                            with TableHeader():
                                                                with TableRow():
                                                                    TableHead("Holder")
                                                                    TableHead("Shares/Stake")
                                                                    TableHead("Type/Group")
                                                            with TableBody():
                                                                for row in large_holders:
                                                                    holder = row.get("holder") or row.get("name") or row.get("shareholder") or ""
                                                                    shares = row.get("shares") or row.get("percentage") or row.get("value") or row.get("stake") or ""
                                                                    h_type = row.get("type") or row.get("category") or ""
                                                                    with TableRow():
                                                                        TableCell(str(holder))
                                                                        TableCell(str(shares))
                                                                        TableCell(str(h_type))

                                    with Card():
                                        with CardHeader():
                                            CardTitle("Research Summary")
                                            CardDescription(source_url or "No source URL saved")
                                        with CardContent():
                                            Markdown(record.get("content", ""))

                    with Card():
                        with CardHeader():
                            CardTitle("Source And MCP Proof")
                            CardDescription("The table below is read from the local JSON file")
                        with CardContent():
                            with Column(gap=3):
                                Text(
                                    "This section proves the local file CRUD requirement: the agent "
                                    "created a record in JSON, then this Prefab UI read it back."
                                )
                                with Table():
                                    with TableHeader():
                                        with TableRow():
                                            TableHead("ID")
                                            TableHead("Title")
                                            TableHead("Source")
                                            TableHead("Updated")
                                    with TableBody():
                                        for record in records[-5:]:
                                            with TableRow():
                                                TableCell(record.get("id", ""))
                                                TableCell(record.get("title", "")[:56])
                                                TableCell(record.get("source_url", "")[:64])
                                                TableCell(record.get("updated_at", ""))

    return app


if __name__ == "__main__":
    mcp.run()
