#!/bin/bash
# bootstrap.sh - Sets up the AI SRE Observability Demo environment

set -e

echo "🚀 Bootstrapping the AI SRE Observability Demo environment..."

# 1. Check prerequisites
for cmd in kind kubectl helm docker; do
  if ! command -v $cmd &> /dev/null; then
    echo "❌ Error: $cmd is not installed. Please install it first."
    exit 1
  fi
done

# 2. Verify persistent OpenLIT stack is running in OrbStack / Docker
echo "🔍 Checking OpenLIT stack in OrbStack..."
if ! docker ps --format '{{.Names}}' | grep -q "^openlit-server$"; then
  echo "❌ Error: OpenLIT is not running in OrbStack."
  echo "   Please run './openlit-bootstrap.sh' first, then re-run bootstrap.sh."
  exit 1
fi

# Quick connectivity test against port 4318
if ! curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4318/v1/traces | grep -qE '200|400|405'; then
  echo "❌ Error: OpenLIT container is running, but port 4318 is not accepting traffic."
  echo "   Check logs with: docker logs openlit-server --tail 30"
  exit 1
fi
echo "✅ Persistent OpenLIT stack detected and healthy."

# 3. Create the Kind cluster
echo "📦 Checking Kubernetes cluster 'sre-demo'..."
if kind get clusters | grep -q "^sre-demo$"; then
  echo "Cluster 'sre-demo' already exists. Skipping creation."
else
  kind create cluster --name sre-demo
fi

# ==============================================================================
# Bridge OpenLIT Container to Kind Network & Register In-Cluster DNS
# ==============================================================================
echo "🔗 Bridging OpenLIT container to Kind Docker network..."
docker network connect kind openlit-server 2>/dev/null || true

OPENLIT_KIND_IP=$(docker inspect -f '{{with index .NetworkSettings.Networks "kind"}}{{.IPAddress}}{{end}}' openlit-server 2>/dev/null || true)

if [ -z "$OPENLIT_KIND_IP" ]; then
  echo "❌ Error: Could not determine IP address for openlit-server on the 'kind' network."
  exit 1
fi

echo "✔ OpenLIT attached to 'kind' network at IP: ${OPENLIT_KIND_IP}"

echo "📡 Registering in-cluster DNS service for OpenLIT..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: openlit
  namespace: default
spec:
  ports:
    - name: otlp-http
      port: 4318
      targetPort: 4318
    - name: otlp-grpc
      port: 4317
      targetPort: 4317
---
apiVersion: v1
kind: Endpoints
metadata:
  name: openlit
  namespace: default
subsets:
  - addresses:
      - ip: ${OPENLIT_KIND_IP}
    ports:
      - name: otlp-http
        port: 4318
      - name: otlp-grpc
        port: 4317
EOF

echo "✔ In-cluster endpoint registered: http://openlit.default.svc.cluster.local:4318 -> ${OPENLIT_KIND_IP}:4318"

# 4. Add & Update Helm Repositories
echo "📥 Configuring Helm repositories..."
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update

# 5. Create a unified namespace
echo "🏗️  Creating 'observability' namespace..."
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -

# 6. Install Qdrant (Vector Database)
echo "🧠 Installing Qdrant (15m timeout)..."
helm upgrade --install qdrant qdrant/qdrant \
  --namespace observability \
  --set replicaCount=1 \
  --set resources.requests.memory="256Mi" \
  --timeout 15m \
  --wait

# 7. Install Standalone Jaeger
echo "🔭 Deploying Standalone Jaeger..."
kubectl apply -f jaeger-deploy.yaml

# 8. Install OpenTelemetry Astronomy Shop
echo "🛒 Configuring OTel Astronomy Shop and Jaeger..."

if [ ! -f "otel-values.yaml" ]; then
    echo "❌ Error: otel-values.yaml not found in the current directory!"
    exit 1
fi

echo "🛒 Installing OTel Astronomy Shop (20m timeout)..."
helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
  --namespace observability \
  -f otel-values.yaml \
  --timeout 20m \
  --wait

echo "✅ Environment Bootstrap Complete!"
echo "========================================================="
echo "To access the UIs:"
echo ""
echo "1. Astronomy Shop Web UI: kubectl port-forward svc/frontend-proxy 8080:8080 -n observability"
echo "2. Jaeger Trace UI:       kubectl port-forward svc/jaeger-standalone 16686:16686 -n default"
echo "3. Qdrant Vector DB:      kubectl port-forward svc/qdrant 6333:6333 -n observability"
echo "4. OpenLIT Dashboard:     http://localhost:3000 (Persistent in OrbStack, no port-forward needed)"
echo "========================================================="