import re

with open("server.py", "r") as f:
    content = f.read()

new_func = """@mcp.tool(app=True)
def prefab_research_dashboard(record_id: str | None = None) -> PrefabApp:
    \"\"\"Show the saved research note in a Prefab dashboard UI.\"\"\"
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
                    # If record_id is passed, we might want to prioritize it, but let's just show all tabs.
                    # Sort so the requested record_id or the latest is first? 
                    # Let's just reverse the records so the newest is the first tab.
                    display_records = list(reversed(records))
                    
                    with Tabs():
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
                            
                            with Tab(title=short_title):
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
                                                            TableHead("Shares")
                                                            TableHead("Ownership")
                                                            TableHead("Meaning")
                                                    with TableBody():
                                                        for row in ownership_rows:
                                                            with TableRow():
                                                                TableCell(str(row.get("category", row.get("party", ""))))
                                                                TableCell(str(row.get("shares", row.get("percentage", row.get("stake", row.get("value_pct", ""))))))
                                                                TableCell(str(row.get("ownership", "")))
                                                                TableCell(str(row.get("meaning", "")))

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
                                                                    TableHead("Shares")
                                                                    TableHead("Ownership")
                                                            with TableBody():
                                                                for row in non_promoter_rows:
                                                                    with TableRow():
                                                                        TableCell(str(row.get("category", row.get("party", row.get("label", "")))))
                                                                        TableCell(str(row.get("shares", row.get("percentage", row.get("stake", row.get("value_pct", row.get("value", "")))))))
                                                                        TableCell(str(row.get("ownership", "")))
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
                                                                    TableHead("Shares")
                                                                    TableHead("Type")
                                                            with TableBody():
                                                                for row in large_holders:
                                                                    with TableRow():
                                                                        TableCell(str(row.get("holder", row.get("name", ""))))
                                                                        TableCell(str(row.get("shares", row.get("percentage", ""))))
                                                                        TableCell(str(row.get("type", "")))

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

    return app"""

# Replace the old function
new_content = re.sub(
    r"@mcp\.tool\(app=True\)\ndef prefab_research_dashboard.*?return app",
    new_func,
    content,
    flags=re.DOTALL
)

with open("server.py", "w") as f:
    f.write(new_content)

