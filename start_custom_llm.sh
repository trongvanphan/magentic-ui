#!/bin/bash

# Start Magentic-UI with Custom LLM Provider
# Sử dụng LLM API local của bạn tại http://localhost:8080

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate venv if exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
fi

echo "================================================"
echo "  🚀 Magentic-UI with Custom LLM"
echo "  Using: http://localhost:8080/chat"
echo "================================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Step 1: Check Custom LLM API
echo ""
echo -e "${BLUE}Step 1: Checking Custom LLM API...${NC}"
echo "================================================"

if curl -s http://localhost:8080 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Custom LLM API is running on port 8080${NC}"
else
    echo -e "${RED}❌ Custom LLM API not responding on port 8080${NC}"
    echo "   Please start your LLM API first."
    exit 1
fi

# Test the API
echo "Testing API..."
RESPONSE=$(curl -s --location 'http://localhost:8080/chat' \
    --header 'Authorization: Bearer localApiToken' \
    --form 'message="Hello, are you working?"' \
    --form 'model="copilot/gpt-4o"' 2>/dev/null || echo "error")

if [[ "$RESPONSE" == *"response"* ]]; then
    echo -e "${GREEN}✓ API test successful${NC}"
else
    echo -e "${YELLOW}⚠️  API test inconclusive, continuing anyway...${NC}"
fi

# Step 2: Check FARA Server (optional)
echo ""
echo -e "${BLUE}Step 2: Checking FARA-7B Server (optional)...${NC}"
echo "================================================"

if check_port 8000; then
    echo -e "${GREEN}✓ FARA server running on port 8000${NC}"
    FARA_AVAILABLE=true
else
    echo -e "${YELLOW}⚠️  FARA server not running on port 8000${NC}"
    echo "   Web Surfer will use Custom LLM instead."
    FARA_AVAILABLE=false
fi

# Step 3: Install/Setup Magentic-UI
echo ""
echo -e "${BLUE}Step 3: Setting up Magentic-UI...${NC}"
echo "================================================"

cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -e . --quiet 2>/dev/null || pip install -e .

# Install additional dependencies for custom client
pip install aiohttp --quiet 2>/dev/null || true

# Install playwright if needed
playwright install 2>/dev/null || true

echo -e "${GREEN}✓ Magentic-UI setup complete${NC}"

# Step 4: Start Magentic-UI
echo ""
echo -e "${BLUE}Step 4: Starting Magentic-UI...${NC}"
echo "================================================"

CONFIG_FILE="$SCRIPT_DIR/config_custom_llm.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

if check_port 8081; then
    echo -e "${YELLOW}⚠️  Port 8081 already in use${NC}"
else
    echo "Starting Magentic-UI on port 8081..."
    magentic-ui --port 8081 --config "$CONFIG_FILE" --run-without-docker &
    sleep 5
    
    if check_port 8081; then
        echo -e "${GREEN}✓ Magentic-UI is running${NC}"
    fi
fi

# Summary
echo ""
echo "================================================"
echo -e "${GREEN}  🎉 System Started!${NC}"
echo "================================================"
echo ""
echo "  Services:"
echo "  ├── Custom LLM API: http://localhost:8080"
if [ "$FARA_AVAILABLE" = true ]; then
echo "  ├── FARA-7B:        http://localhost:8000"
fi
echo "  └── Magentic-UI:    http://localhost:8081"
echo ""
echo -e "  ${GREEN}✓ Không cần OpenAI API key!${NC}"
echo -e "  ${GREEN}✓ Sử dụng LLM API của bạn!${NC}"
echo ""
echo "  Open: ${BLUE}http://localhost:8081${NC}"
echo "================================================"
