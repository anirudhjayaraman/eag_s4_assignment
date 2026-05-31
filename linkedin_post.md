# LinkedIn Post — EAG Session 4: MCP Assignment

> Pick one of the versions below, or mix and match. Both are under 3000 characters (LinkedIn limit).

---

## Version A: Technical Story (Recommended)

---

**I built an autonomous research agent that searches the web, saves structured data, and renders a live dashboard — all without human intervention. Here's how.**

I'm currently taking the EAG course — a 20-session program on building autonomous, production-ready agentic AI platforms from the ground up (no LangChain or CrewAI!). Session 4 is about MCP — the **Model Context Protocol**, an open standard from Anthropic that gives LLMs a type-safe way to call external tools.

Think of MCP as a "USB-C for AI": any model can plug into any tool server without bespoke API glue.

**🧩 What I built:**

An MCP server (`server.py`) exposing three tools:
→ `internet_research` — web search and page fetching
→ `local_file_crud` — full CRUD on a local JSON file
→ `prefab_research_dashboard` — renders a Prefab UI dashboard via MCP

An autonomous agent runner (`run_agent.py`) that:
→ Connects to the MCP server over stdio
→ Uses Gemini 2.5 Pro to decide what to do next
→ Calls tools in a loop: search → save → verify → render
→ Runs 5 different research prompts without human input

**📊 The 5 prompts span:**
1. Tata Sons ownership structure
2. Reliance Industries shareholding
3. Infosys shareholding
4. Adani Enterprises shareholding
5. A stress test: World's Top 5 Economies by GDP (same dashboard schema, different domain)

**🩺 The fun part — Guardrails & Error Handling:**

The initial runs hit API limits or looped on the same actions. So I built robust guardrails into the agent loop:
• Duplicate call detection
• API rate limit fallbacks (from Gemini Pro to Flash)
• Forced progression after 3 searches

With these guardrails, all 5 prompts completed successfully on the first try.

**🎯 Key takeaways:**
- MCP makes tool orchestration declarative and model-agnostic
- Agent loops need guardrails: call caps, duplicate detection, forced progression
- API fallbacks are essential when running multiple autonomous steps on rate-limited tiers

📺 Full walkthrough video: [link to YouTube]
💻 Code: https://github.com/anirudhjayaraman/materials_eag

#MCP #AIAgents #LLM #Gemini #Python #MachineLearning #BuildInPublic #AgenticAI

---

## Version B: Shorter & Punchier

---

What happens when you give an LLM three tools and tell it to figure things out?

For Session 4 of the EAG course (where we build agentic AI platforms from the ground up, without frameworks like CrewAI), I built:

🔧 An MCP server with 3 tools — web search, file CRUD, and a dashboard renderer
🤖 An autonomous agent that calls them in the right order — no human in the loop
📊 A tabbed Prefab dashboard showing 5 different research results
🩺 Built-in guardrails and fallbacks to handle API limits and prevent infinite loops

The agent ran 5 prompts — from Tata Sons ownership to global GDP rankings — each requiring: search → save → verify → render.

The first runs failed due to API limits or endless search loops. So I added robust guardrails — duplicate detection, call caps, and automatic model fallback from Pro to Flash. After that, everything passed.

MCP is like USB-C for LLMs: one protocol, any model, any tool. This assignment made that click for me.

Code + video in comments 👇

#MCP #AIAgents #LLM #Python #BuildInPublic #AgenticAI

---

## Posting Tips

| Tip | Why |
|---|---|
| Post between 8–10 AM IST (Tue–Thu) | Peak LinkedIn engagement window |
| Add a carousel or screenshot | Posts with images get 2× engagement |
| Screenshots to include | Terminal showing all 5 ✓ prompts, the Prefab dashboard with tabs, the architecture diagram |
| Tag the course/instructors | Amplifies reach |
| First comment | Drop the GitHub link + YouTube link in the first comment for better algorithm treatment |
| Reply to every comment in the first hour | LinkedIn rewards early engagement |
