#!/usr/bin/env bash
# bootstrap.sh - Sets up the lightweight AI SRE Observability Demo environment
set -euo pipefail

echo "=========================================================="
echo "🚀 Bootstrapping AI SRE Observability Testbed (HotROD)"
echo "=========================================================="

# 1. Check prerequisites
for cmd in kind kubectl helm docker; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "❌ Error: $cmd is not installed. Please install it first."
    exit 1
  fi
done

# 2. Verify persistent OpenLIT stack is running in OrbStack / Docker
echo "🔍 Checking OpenLIT stack in OrbStack..."
if ! docker ps --format '{{.Names}}' | grep -qE "^(openlit|openlit-server)$"; then
    echo "❌ Error: OpenLIT is not running in OrbStack."
    echo "   Please start it via docker compose first, then re-run bootstrap.sh."
    exit 1
fi
echo "✅ Persistent OpenLIT stack detected."

# 3. Create the Kind cluster
echo "📦 Checking Kubernetes cluster 'sre-demo'..."
if kind get clusters | grep -q "^sre-demo$"; then
  echo "  Cluster 'sre-demo' already exists. Skipping creation."
else
  kind create cluster --name sre-demo
fi

# 4. Bridge OpenLIT to Kind & Register In-Cluster DNS
echo "🔗 Bridging OpenLIT container to Kind Docker network..."
docker network connect kind openlit-server 2>/dev/null || true

OPENLIT_KIND_IP=$(docker inspect -f '{{with index .NetworkSettings.Networks "kind"}}{{.IPAddress}}{{end}}' openlit-server 2>/dev/null || true)
if [ -n "$OPENLIT_KIND_IP" ]; then
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
  echo "✔ In-cluster OpenLIT DNS configured: ${OPENLIT_KIND_IP}:4318"
fi

# 5. Configure Helm repositories
echo "📥 Configuring Helm repositories..."
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update

# 6. Create namespace
echo "🏗️  Creating 'observability' namespace..."
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -

# 7. Install Qdrant
echo "🧠 Installing Qdrant..."
helm upgrade --install qdrant qdrant/qdrant \
  --namespace observability \
  --set replicaCount=1 \
  --set resources.requests.memory="256Mi" \
  --wait

# 8. Install Standalone Jaeger
echo "🔭 Deploying Standalone Jaeger..."
if [ ! -f "jaeger-deploy.yaml" ]; then
  echo "❌ Error: jaeger-deploy.yaml missing."
  exit 1
fi
kubectl apply -f jaeger-deploy.yaml

# 9. Deploy Jaeger HotROD
echo "🚗 Deploying Jaeger HotROD Microservices..."
kubectl apply -f hotrod-deploy.yaml

# Wait for HotROD pod readiness
kubectl rollout status deployment/hotrod -n default --timeout=60s

echo "=========================================================="
echo "✅ Environment Bootstrap Complete!"
echo "=========================================================="
echo "Port-Forward Commands:"
echo "  1. HotROD Rides UI:     kubectl port-forward svc/hotrod 8080:8080 -n default"
echo "  2. Jaeger UI & API:     kubectl port-forward svc/jaeger-standalone 16686:16686 -n default"
echo "  3. Qdrant Vector DB:    kubectl port-forward svc/qdrant 6333:6333 -n observability"
echo "  4. OpenLIT Dashboard:   http://localhost:3000 (Native in OrbStack)"
echo "=========================================================="