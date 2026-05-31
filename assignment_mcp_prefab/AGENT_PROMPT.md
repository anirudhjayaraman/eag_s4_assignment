# Prompts That Force All 3 Tools

Paste any of these into your MCP host after connecting `assignment_mcp_prefab/server.py`. Each one drives the agent through `internet_research` → `local_file_crud` (create) → `local_file_crud` (read/list) → `prefab_research_dashboard`.

## Schema reminder

The dashboard renders these `metadata_json` fields (see `server.py:326-472`). Reuse this shape for every prompt — the column headers are hardcoded as `Category | Shares | Ownership | Meaning`, `Category | Shares | Ownership`, and `Holder | Shares | Type`, so prompts work best when the subject is an "entity → quantity → share-of-total" breakdown.

```json
{
  "title": "...",
  "subtitle": "...",
  "as_of": "...",
  "ownership_table_title": "...",
  "detail_table_title": "...",
  "detail_table_subtitle": "...",
  "headline_cards":   [{"label": "...", "description": "...", "value": "...", "detail": "...", "note": "..."}],
  "ownership_rows":   [{"category": "...", "shares": "...", "ownership": "...", "meaning": "..."}],
  "non_promoter_rows":[{"category": "...", "shares": "...", "ownership": "..."}],
  "large_holders":    [{"holder": "...", "shares": "...", "type": "..."}]
}
```

## Prompt 1 — Tata Sons (original)

```text
Find the current ownership details of Tata Sons from a credible official source.

You must use these MCP tools in this order:
1. Use `internet_research` to search for Tata Sons ownership or shareholding details from Tata's official FY25 filings/documents.
2. Use `local_file_crud` to create a saved research note in the local JSON file. Include a clear title, the official source URL, tags, the ownership summary from the internet result, and `metadata_json` containing the dashboard fields/tables the Prefab UI should render.
3. Use `local_file_crud` again with `operation="read"` or `operation="list"` to prove the note was saved.
4. Use `prefab_research_dashboard` to show the ownership split in a Prefab UI dashboard. I want to see the promoter % up front and the public-shareholder breakdown side-by-side with any named large holders.

Do not answer only in prose. The final thing I should see is the Prefab dashboard UI.
```

## Prompt 2 — Reliance Industries shareholding

```text
Find Reliance Industries' latest published shareholding pattern from a credible source (BSE/NSE filings, Reliance's investor relations site, or its annual report).

You must use these MCP tools in this order:
1. `internet_research` — search for "Reliance Industries shareholding pattern" and pull the most recent quarter's promoter vs public split, plus the breakdown of public shareholders (FIIs, DIIs, mutual funds, retail).
2. `local_file_crud` with `operation="create"` — save the result. Set tags like ["reliance","shareholding","equity-markets","quarterly-filing"], a source_url pointing to the filing, and metadata_json shaped like the schema above:
   - headline_cards: two cards for Promoter and Public blocks (label, value as a %, detail as share count or value)
   - ownership_rows: top-level Promoter vs Public split
   - non_promoter_rows: the public subgroups (FIIs, DIIs, mutual funds, individuals, etc.)
   - large_holders: any named entities (e.g., Reliance Industries Holding Pvt Ltd, LIC) called out in the filing
3. `local_file_crud` with `operation="list"` — confirm the record was saved.
4. `prefab_research_dashboard` — render the saved record. I want to see the promoter % up front and the public-shareholder breakdown side-by-side with any named large holders.

The final research should come out in a Prefab dashboard UI.
```

## Prompt 3 — Infosys shareholding

```text
Find Infosys Ltd's latest published shareholding pattern (BSE/NSE quarterly filing or annual report).

Use the MCP tools in this exact order:
1. `internet_research` — query for "Infosys shareholding pattern latest quarter" and pull the promoter vs public split plus public subgroups (FIIs, DIIs, mutual funds, insurance, retail, others). Infosys is a low-promoter-holding company so the split will look very different from a typical Indian conglomerate — surface that contrast in your summary.
2. `local_file_crud` `operation="create"` — save the record with tags ["infosys","it-services","shareholding"], a credible source_url, and metadata_json populated with:
   - headline_cards: Promoter % and Public % cards, plus optionally a "Largest FII holder" highlight
   - ownership_rows: Promoter vs Public top-level
   - non_promoter_rows: the public-shareholder subgroups
   - large_holders: named promoters/founders if disclosed and the largest FII/DII holders if available
3. `local_file_crud` `operation="list"` — prove the save.
4. `prefab_research_dashboard` — render it.

The final research should come out in a Prefab dashboard UI.
```

## Prompt 4 — Adani Enterprises shareholding

```text
Pull the latest shareholding pattern for Adani Enterprises Ltd from an official disclosure (BSE/NSE filing or the company's investor page).

Drive the MCP tools in order:
1. `internet_research` — find the most recent quarterly shareholding pattern. Capture the promoter & promoter-group %, the public %, and the named promoter entities (e.g., S.B. Adani Family Trust, Gautam Adani, members of the Adani family) if listed.
2. `local_file_crud` `operation="create"` — save with tags ["adani","adani-enterprises","shareholding","promoter-group"], a credible source_url, and metadata_json:
   - headline_cards: Promoter Group %, Public %, and a "Pledged shares" highlight if disclosed
   - ownership_rows: Promoter & promoter-group vs Public
   - non_promoter_rows: FII / DII / mutual fund / retail breakdown
   - large_holders: each named Adani-family promoter entity with its share count and a "Promoter" type label
3. `local_file_crud` `operation="list"` — confirm.
4. `prefab_research_dashboard` — render. Make the promoter concentration immediately visible.

The final research should come out in a Prefab dashboard UI.
```

## Prompt 5 — Repurpose the schema for a non-ownership breakdown (stress test)

This one is here to verify the dashboard renders cleanly for non-ownership data. The hardcoded column headers ("Shares", "Ownership") will read slightly off, but the structure still works.

```text
Build a dashboard of the world's top 5 economies by nominal GDP (latest IMF or World Bank figures).

Use the MCP tools in order:
1. `internet_research` — find the latest nominal GDP figures for the top 5 countries.
2. `local_file_crud` `operation="create"` — save with tags ["macroeconomics","gdp","imf","global-rankings"], a credible source_url, and metadata_json mapped onto the schema:
   - title: "Top 5 Economies by Nominal GDP"
   - subtitle: "...as of <year>, in USD trillions"
   - as_of: source year/quarter
   - ownership_table_title: "Top 5 Economies"
   - headline_cards: top 2 economies as headline cards (label=country, value=GDP, detail=share of world GDP, note=growth rate)
   - ownership_rows: one row per country (category=country, shares=GDP in $T, ownership=share of world GDP %, meaning=key driver sector)
   - large_holders: [] (skip)
   - non_promoter_rows: [] (skip)
3. `local_file_crud` `operation="list"` — confirm.
4. `prefab_research_dashboard` — render.

The final research should come out in a Prefab dashboard UI.
```

## Tips for swapping the agent's hardcoded task

`run_agent.py` has the Tata task baked in at `run_agent.py:288-300`. To test one of the prompts above via the agent loop instead of an MCP host, replace the `task = (...)` string with the prompt body, then run:

```bash
uv run python assignment_mcp_prefab/run_agent.py | tee assignment_mcp_prefab/agent_log.txt
```

Each new record gets its own UUID id and `metadata`, so the dashboard's "last record with non-empty metadata wins" rule means the most recent run is what you'll see at `http://127.0.0.1:5175`.
