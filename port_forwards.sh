#!/usr/bin/env bash
# port_forwards.sh - Manages port-forwards for HotROD, Jaeger, and Qdrant
set -euo pipefail

LOG_FILE="/tmp/k8s_port_forwards.log"
> "$LOG_FILE"

PIDS=()

cleanup() {
  echo -e "\n🛑 Stopping port-forwards..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "✔ All port-forward tunnels closed."
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "=========================================================="
echo "🔌 Activating Local Port-Forwards"
echo "=========================================================="

# 1. HotROD (default namespace)
kubectl port-forward svc/hotrod 8080:8080 -n default >> "$LOG_FILE" 2>&1 &
PIDS+=("$!")
echo "  • HotROD (8080 -> 8080) starting [PID: $!]..."

# 2. Jaeger Standalone (default namespace)
kubectl port-forward svc/jaeger-standalone 16686:16686 -n default >> "$LOG_FILE" 2>&1 &
PIDS+=("$!")
echo "  • Jaeger UI/API (16686 -> 16686) starting [PID: $!]..."

# 3. Qdrant (observability namespace)
kubectl port-forward svc/qdrant 6333:6333 -n observability >> "$LOG_FILE" 2>&1 &
PIDS+=("$!")
echo "  • Qdrant DB (6333 -> 6333) starting [PID: $!]..."

echo "=========================================================="
echo "⏳ Waiting for local endpoints to accept connections..."

wait_for_port() {
  local name="$1"
  local url="$2"
  local max_retries=15
  local count=0

  until curl -s -o /dev/null "$url" 2>/dev/null || [ "$count" -ge "$max_retries" ]; do
    sleep 1
    count=$((count + 1))
  done

  if [ "$count" -ge "$max_retries" ]; then
    echo "⚠️  Warning: ${name} (${url}) did not respond within 15s. Check ${LOG_FILE}"
  else
    echo "✔ ${name} is reachable at ${url}"
  fi
}

wait_for_port "HotROD UI" "http://localhost:8080"
wait_for_port "Jaeger UI" "http://localhost:16686"
wait_for_port "Qdrant API" "http://localhost:6333"

echo "=========================================================="
echo "✅ All 3 services forwarded successfully!"
echo "Press [Ctrl + C] in this window to stop all tunnels."
echo "Logs streaming to: ${LOG_FILE}"
echo "=========================================================="

while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "❌ A port-forward process (PID $pid) terminated unexpectedly."
      echo "Tail of ${LOG_FILE}:"
      tail -n 15 "$LOG_FILE"
      exit 1
    fi
  done
  sleep 3
done