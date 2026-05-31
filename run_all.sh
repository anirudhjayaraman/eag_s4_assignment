#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "🧹 Clearing old research data to start fresh..."
echo "=========================================================="
rm -f assignment_mcp_prefab/data/research_notes.json
mkdir -p assignment_mcp_prefab/data
echo "[]" > assignment_mcp_prefab/data/research_notes.json

echo "=========================================================="
echo "🚀 Running the Agent for all 5 Prompts..."
echo "   (This takes a few minutes — each prompt does web"
echo "    research, saves data, and renders a dashboard.)"
echo "=========================================================="
uv run python assignment_mcp_prefab/run_agent.py --all 2>&1 | tee assignment_mcp_prefab/agent_log.txt

echo ""
echo "=========================================================="
echo "✅ Agent finished! Now launching the dashboard..."
echo "=========================================================="

# Kill any leftover prefab server on the default port
lsof -ti:5175 | xargs kill -9 2>/dev/null || true
sleep 1

# Open browser after a short delay (server needs ~1s to start)
(sleep 2 && open http://127.0.0.1:5175) &

# Start the dashboard — this blocks until Ctrl+C
uv run prefab serve assignment_mcp_prefab/dashboard_app.py -p 5175
