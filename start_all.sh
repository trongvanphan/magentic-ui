#!/bin/bash
# Start all services for Magentic-UI with Custom LLM

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  🚀 Starting Magentic-UI with Custom LLM"
echo "================================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check Custom LLM API
echo ""
echo -e "${YELLOW}[1/3] Checking Custom LLM API...${NC}"
if curl -s http://localhost:8080/chat -H "Content-Type: application/json" -d '{"message":"test","model":"test"}' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Custom LLM API is running on :8080${NC}"
else
    echo -e "${RED}❌ Custom LLM API not responding on :8080${NC}"
    echo "   Please start your LLM API first."
    exit 1
fi

# Start Proxy
echo ""
echo -e "${YELLOW}[2/3] Starting LLM Proxy Server...${NC}"
pkill -f "custom_llm_proxy.py" 2>/dev/null || true
sleep 1
nohup "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/custom_llm_proxy.py" > /tmp/proxy.log 2>&1 &
PROXY_PID=$!
sleep 2

if curl -s http://localhost:8090/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Proxy running on :8090 (PID: $PROXY_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start proxy${NC}"
    cat /tmp/proxy.log
    exit 1
fi

# Start Magentic-UI
echo ""
echo -e "${YELLOW}[3/3] Starting Magentic-UI...${NC}"
pkill -f "magentic-ui" 2>/dev/null || true
sleep 1

echo ""
echo "================================================"
echo -e "${GREEN}  ✅ System Ready!${NC}"
echo "================================================"
echo ""
echo "  Services:"
echo "  ├── Custom LLM API: http://localhost:8080"
echo "  ├── LLM Proxy:      http://localhost:8090"
echo "  └── Magentic-UI:    http://localhost:8081"
echo ""
echo "  Logs:"
echo "  └── Proxy: tail -f /tmp/proxy.log"
echo ""
echo "  Stop: ./stop_all.sh"
echo ""
echo "================================================"
echo ""

# Run Magentic-UI in foreground
"$SCRIPT_DIR/venv/bin/magentic-ui" \
    --port 8081 \
    --run-without-docker \
    --config "$HOME/.magentic_ui/configs/config_proxy.yaml"
