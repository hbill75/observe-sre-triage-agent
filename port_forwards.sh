#!/usr/bin/env bash
# port_forwards.sh - Background tunnels for SRE agent demo
set -euo pipefail

LOG_FILE="/tmp/sre_port_forwards.log"
> "$LOG_FILE"

echo "=========================================================="
echo "🔌 Initializing Kubernetes Port-Forwards..."
echo "=========================================================="

# 1. HotROD Application / UI (Traffic Simulation Target)
kubectl port-forward svc/hotrod 8080:8080 -n default >> "$LOG_FILE" 2>&1 &
echo "  • HotROD UI:         http://localhost:8080"

# 2. Qdrant Vector DB (Tickets & Runbooks)
kubectl port-forward svc/qdrant 6333:6333 -n observability >> "$LOG_FILE" 2>&1 &
echo "  • Qdrant Vector DB:  http://localhost:6333"

# 3. Jaeger MCP Server (SSE Endpoint for SRE Agents)
kubectl port-forward svc/jaeger-mcp 8000:8000 -n default >> "$LOG_FILE" 2>&1 &
echo "  • Jaeger MCP SSE:    http://localhost:8000/sse"

# 4. Jaeger Standalone Web UI (Visual Verification)
kubectl port-forward svc/jaeger-standalone 16686:16686 -n default >> "$LOG_FILE" 2>&1 &
echo "  • Jaeger Web UI:     http://localhost:16686"

echo "=========================================================="
echo "✅ All port-forwards started in background."
echo "   Output logs routed to $LOG_FILE."
echo "=========================================================="