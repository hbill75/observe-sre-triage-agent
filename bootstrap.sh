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
if ! docker ps | grep -q "openlit-server"; then
  echo "⚠️  OpenLIT is not running in Docker. Starting it now via docker compose..."
  docker compose -f docker-compose.openlit.yaml up -d
else
  echo "✅ Persistent OpenLIT stack detected."
fi

# 3. Create the Kind cluster
echo "📦 Checking Kubernetes cluster 'sre-demo'..."
if kind get clusters | grep -q "^sre-demo$"; then
  echo "Cluster 'sre-demo' already exists. Skipping creation."
else
  kind create cluster --name sre-demo
fi

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
echo "1. Astronomy Shop Web UI: kubectl port-forward svc/otel-demo-frontendproxy 8080:8080 -n observability"
echo "2. Jaeger Trace UI:       kubectl port-forward svc/jaeger-standalone 16686:16686 -n default"
echo "3. Qdrant Vector DB:      kubectl port-forward svc/qdrant 6333:6333 -n observability"
echo "4. OpenLIT Dashboard:     http://localhost:3000 (Persistent in OrbStack, no port-forward needed)"
echo "========================================================="