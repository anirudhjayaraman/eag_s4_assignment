# EAG V3: Building Agentic Applications

This repository tracks the progression and assignments for the **EAG V3** course, a comprehensive curriculum focused on modern LLM internals, transformer architecture, and building autonomous AI agents.

## 🎥 Course Curriculum & Lectures

A detailed log of all course sessions, including video recordings, thumbnails, and study notes, can be found in the dedicated **[LECTURES.md](LECTURES.md)** file.

| Session | Topic | Link |
| :--- | :--- | :--- |
| 1-5 | Full Video Series & Notes | [📖 View Lectures.md](LECTURES.md) |

---


## Session 1: Foundations of Transformer Architecture
**Focus:** Understand neural networks, attention mechanisms, and positional encoding that power modern AI.

**Assignment:** 
As part of the requirements for Session 1, I developed **Anveeksha Daily Board Activity**, a curriculum generation pipeline and companion web application. It leverages structured generation (via Pydantic) to extract and transform nursery logs into daily, bite-sized whiteboard activities.
🔗 **[Anveeksha GitHub Repository](https://github.com/anirudhjayaraman/anveeksha-daily-board-activity)**

## Session 2: Modern LLM Internals & The 2026 Model Landscape
**Focus:** Learn tokenization, scaling laws, RLHF alignment, and the current state of reasoning and multi-modal models.

**Assignment:**
For the post-Session 2 assignment, I built **See Through The Hype**, a practical application that demonstrates the utilization of instruction-tuned models to process, structure, and analyze complex textual data and sentiment.
🔗 **[See-Through GitHub Repository](https://github.com/anirudhjayaraman/see-through)**

## Session 3: Developer Foundations & Your First Agent
**Focus:** Build Python and Node.js skills, then create your first goal-directed agent with a working web UI.

**Code & Materials:**
The `s3_code` directory within this repository contains the progression of scripts developed during Session 3. The code covers:
- Core Python developer tools: REPL interaction (`code.interact()`) and debugging (`pdb`).
- Asynchronous programming patterns and avoiding common blocking mistakes.
- Foundational LLM integration using system prompts.
- Building a complete, goal-directed autonomous agent capable of interacting with its environment, alongside variations for mock testing and local inference (Ollama).

For an interactive overview of the code developed in this session, check out the compiled notebook: `s3_code/demo_notebook.ipynb`.

## Session 4: Model Context Protocol (MCP)
**Focus:** Exploring the Model Context Protocol (MCP) for standardized tool and data interaction between AI models and local/remote resources.

**Code & Materials:**
The `s4_code` directory contains explorations into MCP server implementations and client integrations:
- `string_reverser/`: A simple MCP demonstration.
  - `mcp_server.py`: A FastMCP server exposing a `reverse_string` tool.
  - `mcp_client.py`: An MCP client script that connects to the server and calls the string reversal tool over stdio.
- `prefab/`: An instructional 5-part track (lessons 0 through 4) designed to teach "Prefab" — a UI framework/DSL that integrates with MCP to build dynamic web apps, starting from UI basics and culminating in an AI "Talk-to-App" builder.

To test the example server using the MCP Inspector, run:
```bash
mcp dev example_mcp_server.py
```

## Session 5: Planning and Reasoning with Language Models
**Focus:** Advanced techniques for planning, multi-step reasoning, and error correction in autonomous agent loops.

