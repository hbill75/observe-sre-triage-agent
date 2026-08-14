#!/bin/bash
# cleanup.sh - Completely removes the AI SRE Observability Demo environment

echo "🧹 Starting cleanup process..."

# 1. Delete the Kind cluster
if kind get clusters | grep -q "^sre-demo$"; then
  echo "🗑️  Deleting kind cluster 'sre-demo'..."
  kind delete cluster --name sre-demo
else
  echo "ℹ️  Cluster 'sre-demo' does not exist or was already deleted."
fi

# 2. Kill any lingering port-forward processes
echo "🔌 Cleaning up background port-forwarding processes..."
PIDS=$(pgrep -f "kubectl port-forward")
if [ -n "$PIDS" ]; then
  kill $PIDS
  echo "✅ Killed active kubectl port-forward sessions."
else
  echo "ℹ️  No active port-forward sessions found."
fi

echo "========================================================="
echo "✅ Cleanup complete! Your local environment is clean."
echo "To rebuild the environment, run: ./bootstrap.sh"
echo "========================================================="