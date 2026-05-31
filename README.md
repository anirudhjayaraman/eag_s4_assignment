# EAG V3: Session 4 - MCP Assignment

This repository contains my assignment for **Session 4** of the **EAG V3** course, a comprehensive program focused on building autonomous, production-ready agentic AI platforms from the ground up.

## Model Context Protocol (MCP)

**Focus:** Exploring the Model Context Protocol (MCP) for standardized tool and data interaction between AI models and local/remote resources.

**Code & Materials:**
This repository contains explorations into MCP server implementations and client integrations:
- `assignment_mcp_prefab/`: The core assignment where an autonomous agent searches the web, stores data locally via CRUD tools, and renders a live Prefab UI dashboard using MCP.
- `string_reverser/`: A simple MCP demonstration.
  - `mcp_server.py`: A FastMCP server exposing a `reverse_string` tool.
  - `mcp_client.py`: An MCP client script that connects to the server and calls the string reversal tool over stdio.
- `prefab/`: An instructional 5-part track designed to teach "Prefab" — a UI framework/DSL that integrates with MCP to build dynamic web apps.

To test the example server using the MCP Inspector, run:
```bash
mcp dev example_mcp_server.py
```
