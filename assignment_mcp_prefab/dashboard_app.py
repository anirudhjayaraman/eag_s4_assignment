from __future__ import annotations

import json
import os
from pathlib import Path

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
    Tab,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    Tabs,
    Text,
)


DEFAULT_STORE_PATH = Path(__file__).parent / "data" / "research_notes.json"
STORE_PATH = Path(os.getenv("RESEARCH_STORE_PATH", str(DEFAULT_STORE_PATH))).expanduser()


def read_records() -> list[dict]:
    if not STORE_PATH.exists():
        return []
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


records = read_records()
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
                        short_title = title[:24] + ("..." if len(title) > 24 else "")

                        headline_cards = metadata.get("headline_cards", [])
                        ownership_rows = metadata.get("ownership_rows", [])
                        non_promoter_rows = metadata.get("non_promoter_rows", [])
                        large_holders = metadata.get("large_holders", [])
                        tools_invoked = metadata.get("tools_invoked", [])
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
                                    for record in records:
                                        with TableRow():
                                            TableCell(record.get("id", ""))
                                            TableCell(record.get("title", "")[:56])
                                            TableCell(record.get("source_url", "")[:64])
                                            TableCell(record.get("updated_at", ""))
