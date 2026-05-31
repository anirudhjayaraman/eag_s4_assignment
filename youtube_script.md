# YouTube Video Script — EAG Session 4: MCP Assignment

> **Estimated length:** 8–12 minutes
> **Format:** Narrated screencast with code walkthroughs + live dashboard demo
> **Tone:** Technical but approachable — you're explaining to peers and hiring managers

---

## 🎬 INTRO (0:00 – 0:45)

**[SCREEN: Title slide or animated text — "Building an AI Agent with MCP, Prefab & Self-Healing Code"]**

> **NARRATION:**
>
> "Hey everyone, I'm Anirudh. I'm currently taking the **EAG V3** course — that's on The School of AI, taught by Rohan Shravan. This video walks through my Session 4 assignment.
>
> Quick context on where we are in the course. EAG V3 is a 20-session program focused on building autonomous, production-ready agentic AI platforms from the ground up — without relying on frameworks like LangChain or CrewAI.
>
> The course covers all three protocol layers (MCP, A2A, and A2UI), container-isolated execution, multi-channel deployment, and browser/desktop autonomy. 
> 
> **Session 4 — where I am now — is on MCP: the Model Context Protocol.** It's an open standard by Anthropic that lets AI models call tools in a structured, type-safe way. Think of it as a USB-C port for LLMs: any model can plug into any tool server without custom glue code.
>
> The assignment challenge? Build an MCP server with three tools, wire up an autonomous agent that calls them in the right sequence, and render the final result in a Prefab dashboard — all without a human in the loop."

---

## 📋 ASSIGNMENT REQUIREMENTS (0:45 – 2:00)

**[SCREEN: Show `AGENT_PROMPT.md` in VS Code or terminal]**

> **NARRATION:**
>
> "Here's what the assignment asks for. I need to build an MCP server — `server.py` — that exposes exactly three tools:
>
> 1. **`internet_research`** — searches the web or fetches a URL.
> 2. **`local_file_crud`** — creates, reads, updates, and deletes records in a local JSON file.
> 3. **`prefab_research_dashboard`** — renders a beautiful Prefab UI dashboard from the saved data. The UI with the results of our reasearch are thus sent by the MCP server.
>
> Then I need an agent runner — `run_agent.py` — that connects to the MCP server over stdio and autonomously drives through 5 different research prompts. Each prompt must exercise all three tools in order:
>
> **Search → Save → Verify → Render.**
>
> The prompts span different domains: Tata Sons ownership, Reliance Industries shareholding, Infosys, Adani Enterprises, and even a stress test using the same dashboard schema for global GDP rankings. That last one proves the schema is generic enough to handle non-ownership data too."

**[SCREEN: Briefly scroll through the 5 prompts in `AGENT_PROMPT.md`]**

---

## 🏗️ ARCHITECTURE OVERVIEW (2:00 – 3:00)

**[SCREEN: Draw or show a simple diagram — can be a whiteboard/Excalidraw]**

```
┌────────────────┐      stdio       ┌──────────────────────┐
│  run_agent.py  │ ◄──────────────► │     server.py        │
│  (MCP Client)  │                  │    (MCP Server)      │
│                │                  │                      │
│  Gemini/Ollama │                  │  internet_research   │
│  LLM calls     │                  │  local_file_crud     │
│                │                  │  prefab_dashboard    │
└────────────────┘                  └──────────┬───────────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │  data/               │
                                    │  research_notes.json │
                                    └──────────────────────┘
```

> **NARRATION:**
>
> "The architecture is clean. `run_agent.py` is the MCP *client* — it spawns `server.py` as a child process and talks to it over standard I/O using the MCP protocol. The LLM — either Gemini or a local Ollama model — generates one action per iteration: either a `FUNCTION_CALL` or a `FINAL_ANSWER`. The runner parses the action, calls the corresponding MCP tool, feeds the result back to the LLM, and loops until the task is done."

---

## 🔧 DEEP DIVE: `server.py` (3:00 – 5:00)

**[SCREEN: Open `server.py` in editor, scroll through key sections]**

> **NARRATION:**
>
> "Let's look at `server.py`. It's built on **FastMCP** — the Python framework for MCP servers."

### Tool 1: `internet_research` (show lines ~160–200)

> "The first tool is `internet_research`. It takes a query string and optionally a `max_chars` limit. If the query looks like a URL, it fetches the page directly. Otherwise, it does a Wikipedia API search as a fallback. It returns structured JSON with the source URL, heading, and a summary."

### Tool 2: `local_file_crud` (show lines ~210–310)

> "The second tool — `local_file_crud` — is a full CRUD interface for a JSON file. It supports create, read, update, delete, and list operations. When the agent creates a record, it stores the title, content, source URL, tags, and — critically — a `metadata` dictionary. This metadata is what the dashboard reads to populate cards, tables, and charts."

**[SCREEN: Show `data/research_notes.json` briefly to show the shape of a record]**

### Tool 3: `prefab_research_dashboard` (show lines ~313–480)

> "The third tool is the showstopper — `prefab_research_dashboard`. It's decorated with `@mcp.tool(app=True)`, which means it returns a full Prefab UI instead of just text.
>
> It reads *all* the records from the JSON file and renders them using the **Tabs** component — each record gets its own clickable tab. Inside each tab, you get headline metric cards, ownership breakdown tables, detailed sub-tables, and a research summary — all dynamically populated from the metadata the agent saved in the previous step.
>
> At the bottom there's a proof table showing the IDs, titles, and timestamps of all saved records — this proves the local file CRUD requirement."

---

## 🤖 DEEP DIVE: `run_agent.py` (5:00 – 7:00)

**[SCREEN: Open `run_agent.py` in editor]**

> **NARRATION:**
>
> "Now `run_agent.py` — this is the brain."

### The Agent Loop (show lines ~449–548)

> "The core is a simple but effective agent loop. For each prompt, the runner:
>
> 1. Sends the system prompt + task + history to the LLM.
> 2. Parses the response — expecting either `FUNCTION_CALL: tool(args)` or `FINAL_ANSWER: done`.
> 3. If it's a function call, it maps the arguments to the tool's schema, calls the tool via MCP, and appends the result to the conversation history.
> 4. Loops until `FINAL_ANSWER` or a max of 15 iterations.

### Self-Healing Guardrails (show lines ~483–505)

> "I built in two guardrails that prevented the agent from getting stuck:
>
> **Duplicate detection** — if the LLM repeats the exact same tool call, the runner skips it and nudges the model: 'You already did this. Move on.'
>
> **Call caps** — `internet_research` is limited to 3 calls per prompt. If the LLM keeps searching without acting on results, the runner forces it forward. Without this, the agent would burn all 15 iterations googling the same thing."

### Gemini Tier Fallback (show lines ~122–161)

> "One neat production detail: the runner tries Gemini 2.5 Pro first, and if it hits a quota or rate-limit error, it silently falls back to Gemini 2.5 Flash for the rest of the run. No crash, no manual intervention."

---

## 📊 LIVE DEMO: The Dashboard (7:00 – 8:30)

**[SCREEN: Run `./run_all.sh` in terminal — or use pre-recorded footage if the run takes too long]**

> **NARRATION:**
>
> "Let me run the whole thing end to end. I have a single shell script — `run_all.sh` — that clears old data, runs all 5 prompts through the agent, and then launches the Prefab dashboard."

**[SCREEN: Show terminal output as prompts complete one by one]**

> "You can see each prompt going through the cycle: search, save, verify, render. All 5 complete with `FINAL_ANSWER` and all three tools confirmed as invoked."

**[SCREEN: Switch to browser showing the dashboard at `http://127.0.0.1:5175`]**

> "And here's the result. Five tabs — one per research topic:
>
> - **Tata Sons** — 66% promoter trusts, 18.4% Shapoorji Pallonji, the rest with Tata family and companies.
> - **Reliance Industries** — promoter vs public split with FII/DII breakdown.
> - **Infosys** — low promoter holding typical of IT companies.
> - **Adani Enterprises** — high promoter concentration.
> - **Top 5 Economies** — stress test showing the same schema works for GDP data.
>
> Each tab has headline cards, detailed ownership tables, and the full research summary — all populated autonomously by the agent."

**[SCREEN: Scroll through 2-3 tabs to show the content]**

---

## 🎤 OUTRO (10:00 – 10:30)

**[SCREEN: Back to title slide or face cam]**

> **NARRATION:**
>
> "To summarize: this assignment demonstrates MCP-native tool orchestration, autonomous multi-step agent execution, and structured Prefab UI rendering via MCP.
>
> All the code is on my GitHub — link in the description. If you're building agentic systems with MCP, I hope this gives you a concrete reference. Thanks for watching!"

---

## 📝 Video Description (Copy-Paste for YouTube)

```
EAG Session 4 Assignment — Building an Autonomous Research Agent with MCP & Prefab

In this walkthrough, I build a complete MCP (Model Context Protocol) system:
• An MCP server with 3 tools: web research, local file CRUD, and Prefab UI dashboards
• An autonomous agent runner that uses Gemini/Ollama to drive 5 research prompts end-to-end
• A tabbed Prefab dashboard showing all research results in a single view

Tech stack: Python, FastMCP, Prefab UI, Gemini 2.5 Pro/Flash, MCP over stdio

🔗 GitHub: https://github.com/anirudhjayaraman/materials_eag
📚 Course: EAG

#MCP #AI #Agents #LLM #Python #Prefab #Gemini #MachineLearning
```

---

## 🎥 Recording Tips

| Section | What to show on screen |
|---|---|
| Intro | Title slide or animated text |
| Requirements | `AGENT_PROMPT.md` in editor |
| Architecture | Diagram (Excalidraw / whiteboard / the ASCII art above) |
| server.py | Code editor with key functions highlighted |
| run_agent.py | Code editor, focus on the agent loop |
| Live demo | Terminal running `./run_all.sh`, then browser with dashboard |
| Outro | Face cam or title slide |
