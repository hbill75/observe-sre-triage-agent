#!/usr/bin/env bash
# openlit-bootstrap.sh - Deploys and validates persistent OpenLIT in OrbStack
set -euo pipefail

COMPOSE_FILE="docker-compose.openlit.yaml"
COLLECTOR_CONFIG="otel/otel-collector-config.yaml"
CONTAINER_NAME="openlit-server"

echo "=========================================================="
echo "🚀 Bootstrapping Persistent OpenLIT AI Observability Stack"
echo "=========================================================="

# 1. Preflight File Checks
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "❌ Error: $COMPOSE_FILE not found."
  exit 1
fi

if [ ! -f "$COLLECTOR_CONFIG" ]; then
  echo "❌ Error: $COLLECTOR_CONFIG not found."
  exit 1
fi

# 2. Optional Reset Flag
if [[ "${1:-}" == "--reset" ]]; then
  echo "⚠️  --reset specified: Tearing down stack and wiping persistent volumes..."
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
fi

# 3. Launch Stack
echo "==> Launching ClickHouse and OpenLIT via Docker Compose..."
docker compose -f "$COMPOSE_FILE" up -d

# 4. Validate Collector Configuration Inside Container
echo "==> Validating collector configuration with otelcontribcol binary..."
# Allow a few seconds for entrypoint extraction
sleep 3
docker compose -f "$COMPOSE_FILE" exec -T openlit \
  /app/opamp/otelcontribcol validate --config /etc/otel/otel-collector-config.yaml

# 5. Polling Port 4318 for OTLP Ingestion Readiness
echo "==> Waiting for OTLP HTTP receiver (port 4318) to accept trace batches..."
MAX_RETRIES=30
RETRY_COUNT=0
READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  # Send an empty JSON trace batch
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:4318/v1/traces \
    -H "Content-Type: application/json" \
    -d '{"resourceSpans":[]}' 2>/dev/null || true)
  
  if [[ "$HTTP_CODE" =~ ^(200|400|405)$ ]]; then
    READY=true
    break
  fi

  echo "  Waiting for OTLP receiver (HTTP: ${HTTP_CODE:-down}, attempt $((RETRY_COUNT+1))/${MAX_RETRIES})..."
  RETRY_COUNT=$((RETRY_COUNT+1))
  sleep 2
done

if [ "$READY" = false ]; then
  echo "❌ Error: OpenLIT failed to accept traces on port 4318 within timeout."
  echo "Dumping recent container logs:"
  docker logs "$CONTAINER_NAME" --tail 40
  exit 1
fi

echo "✔ OpenLIT OTLP receiver is live and accepting spans on port 4318."

