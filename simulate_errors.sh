#!/usr/bin/env bash
# simulate_traffic.sh - Generates continuous HotROD traffic (1 error + 2 healthy calls per loop)

HOTROD_URL="${HOTROD_URL:-http://localhost:8080}"
INTERVAL="${INTERVAL:-3}"

# Graceful termination trap
cleanup() {
  echo -e "\n🛑 Traffic generation stopped."
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "=============================================="
echo "🚗 HotROD Traffic Generator Active"
echo "🎯 Target:   ${HOTROD_URL}"
echo "⏱️️  Interval: ${INTERVAL}s per batch"
echo "Press [Ctrl + C] to stop at any time."
echo "=============================================="

# Check if port-forward is alive before looping
if ! curl -s --connect-timeout 2 "${HOTROD_URL}" > /dev/null; then
  echo "⚠️  Warning: Could not connect to ${HOTROD_URL}."
  echo "   Make sure 'kubectl port-forward svc/hotrod 8080:8080 -n default' is running."
  echo "----------------------------------------------"
fi

batch_count=0
while true; do
  batch_count=$((batch_count + 1))
  timestamp=$(date +"%T")

  # 1. Trigger error trace (HTTP 404 / error span)
  curl -s "${HOTROD_URL}/dispatch?customer=99999" > /dev/null 2>&1 || true

  # 2. Trigger valid customer dispatches (healthy spans)
  curl -s "${HOTROD_URL}/dispatch?customer=123" > /dev/null 2>&1 || true
  curl -s "${HOTROD_URL}/dispatch?customer=392" > /dev/null 2>&1 || true

  echo "[${timestamp}] Batch #${batch_count}: 1 error (customer=99999) + 2 valid dispatches sent"
  sleep "${INTERVAL}"
done