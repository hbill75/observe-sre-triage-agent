#!/bin/bash
# cleanup.sh - Removes ephemeral demo resources while preserving OpenLIT history

echo "🧹 Starting cleanup process..."

# 1. Delete the Kind cluster
if kind get clusters | grep -q "^sre-demo$"; then
  echo "🗑️  Deleting kind cluster 'sre-demo'..."
  kind delete cluster --name sre-demo
else
  echo "ℹ️  Cluster 'sre-demo' does not exist or was already deleted."
fi

# 2. Kill lingering port-forward processes
echo "🔌 Cleaning up background port-forwarding processes..."
PIDS=$(pgrep -f "kubectl port-forward")
if [ -n "$PIDS" ]; then
  kill $PIDS
  echo "✅ Killed active kubectl port-forward sessions."
else
  echo "ℹ️  No active port-forward sessions found."
fi

echo "========================================================="
echo "✅ Ephemeral cluster resources cleaned up!"
echo "ℹ️  Persistent OpenLIT/ClickHouse containers in OrbStack remain intact."
echo "   (To destroy OpenLIT data: docker compose -f docker-compose.openlit.yaml down -v)"
echo "========================================================="