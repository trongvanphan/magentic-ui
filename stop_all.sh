#!/bin/bash
# Stop all Magentic-UI services

echo "Stopping all services..."

pkill -f "custom_llm_proxy.py" 2>/dev/null && echo "✓ Proxy stopped" || echo "- Proxy not running"
pkill -f "magentic-ui" 2>/dev/null && echo "✓ Magentic-UI stopped" || echo "- Magentic-UI not running"

echo ""
echo "All services stopped."
