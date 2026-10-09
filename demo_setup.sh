#!/usr/bin/env bash
# demo_setup.sh - Post-bootstrap setup, iTerm automation, and agent prep
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=========================================================="
echo "🚀 Initializing SRE Agent Environment & Workflows"
echo "=========================================================="

# ------------------------------------------------------------------------------
# 1. Open iTerm Window 1: Port-Forwards
# ------------------------------------------------------------------------------
echo "🔌 Launching port-forwards in a new iTerm window..."
osascript <<EOF
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "cd \"$REPO_DIR\" && ./port_forwards.sh"
    end tell
end tell
EOF

# ------------------------------------------------------------------------------
# 2. Virtual Environment & Dependencies (Targeting Python 3.11+)
# ------------------------------------------------------------------------------
echo "🐍 Locating modern Python (>= 3.10)..."
PY_BIN=""
if command -v python3.11 >/dev/null 2>&1; then
    PY_BIN="$(command -v python3.11)"
elif command -v brew >/dev/null 2>&1 && [ -x "$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11" ]; then
    PY_BIN="$(brew --prefix python@3.11)/bin/python3.11"
elif command -v python3.12 >/dev/null 2>&1; then
    PY_BIN="$(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c "import sys; print(sys.version_info >= (3, 10))" 2>/dev/null || echo "False")
    if [ "$PY_VER" = "True" ]; then
        PY_BIN="$(command -v python3)"
    fi
fi

if [ -z "$PY_BIN" ]; then
    echo "❌ Error: Python 3.10+ (preferably Python 3.11) is required."
    echo "Please install it via Homebrew: brew install python@3.11"
    exit 1
fi

echo "✔ Using Python binary: $PY_BIN ($($PY_BIN --version))"

if [ ! -d ".venv" ]; then
    "$PY_BIN" -m venv .venv
    echo "✔ Created .venv"
fi

# Activate virtual environment
source .venv/bin/activate

echo "📦 Installing and upgrading dependencies from requirements.txt..."
pip install --quiet --upgrade pip setuptools wheel
pip install --quiet -r requirements.txt
echo "✔ Dependencies installed."

# ------------------------------------------------------------------------------
# 3. Configure .env and Gemini API Key
# ------------------------------------------------------------------------------
echo "🔑 Checking .env configuration..."

EXISTING_KEY=""
if [ -f ".env" ]; then
    EXISTING_KEY=$(grep -E '^GEMINI_API_KEY=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'" || true)
fi

if [ -n "$EXISTING_KEY" ]; then
    read -r -p "Detected existing GEMINI_API_KEY. Keep it? [Y/n]: " KEEP_KEY
    if [[ "$KEEP_KEY" =~ ^[Nn] ]]; then
        read -r -s -p "Enter new Google Gemini API Key: " GEMINI_KEY
        echo ""
    else
        GEMINI_KEY="$EXISTING_KEY"
    fi
else
    read -r -s -p "Enter Google Gemini API Key: " GEMINI_KEY
    echo ""
fi

cat <<EOF > .env
GEMINI_API_KEY="$GEMINI_KEY"
OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
OPENLIT_ENVIRONMENT="development"
MCP_SERVER_URL="http://localhost:8000/sse"
QDRANT_URL="http://localhost:6333"
EOF
echo "✔ .env file configured."

# ------------------------------------------------------------------------------
# 4. Wait for Qdrant Port-Forward & Seed Vector Memory
# ------------------------------------------------------------------------------
echo "⏳ Waiting for Qdrant port-forward on localhost:6333 to be reachable..."
MAX_RETRIES=20
RETRY_COUNT=0
until curl -s http://localhost:6333/collections >/dev/null 2>&1 || [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; do
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
    echo "❌ Error: Qdrant was not reachable at http://localhost:6333 within 20s."
    echo "Please check the port_forwards.sh iTerm window."
    exit 1
fi
echo "✔ Qdrant is reachable."

echo "🧠 Seeding Qdrant vector database (INC-2001 & RB-010)..."
python3 seed_qdrant.py
echo "✔ Qdrant seeded."

# ------------------------------------------------------------------------------
# 5. Open iTerm Window 2: Traffic / Error Simulator
# ------------------------------------------------------------------------------
echo "🚗 Launching HotROD error generator in a new iTerm window..."
osascript <<EOF
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "cd \"$REPO_DIR\" && ./simulate_errors.sh"
    end tell
end tell
EOF

# ------------------------------------------------------------------------------
# 6. Completion Banner & Quick Links
# ------------------------------------------------------------------------------
echo ""
echo "=========================================================="
echo "✅ Environment Ready!"
echo "=========================================================="
echo "🔗 Access Points & Dashboards:"
echo "   • HotROD UI:         http://localhost:8080"
echo "   • Jaeger Web UI:     http://localhost:16686"
echo "   • Jaeger MCP Server: http://localhost:8000/sse"
echo "   • Qdrant Vector DB:  http://localhost:6333"
echo "   • OpenLIT Dashboard: http://localhost:3000"
echo "----------------------------------------------------------"
echo "Run the agent triage workflow in this window:"
echo ""
echo "    source .venv/bin/activate"
echo "    python3 sre_agents.py"
echo "=========================================================="