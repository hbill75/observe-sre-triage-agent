#!/bin/bash
# bootstrap.sh - Sets up the AI SRE Observability Demo locally

set -e

echo "🚀 Bootstrapping the AI SRE Observability Demo environment..."

# 1. Check prerequisites
for cmd in kind kubectl helm docker; do
  if ! command -v $cmd &> /dev/null; then
    echo "❌ Error: $cmd is not installed. Please install it first."
    exit 1
  fi
done

# 2. Create the Kind cluster
echo "📦 Checking Kubernetes cluster 'sre-demo'..."
if kind get clusters | grep -q "^sre-demo$"; then
  echo "Cluster 'sre-demo' already exists. Skipping creation."
else
  kind create cluster --name sre-demo
fi

# 3. Add & Update Helm Repositories
echo "📥 Configuring Helm repositories..."
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add openlit https://openlit.github.io/helm/
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update

# 4. Create a unified namespace
echo "🏗️  Creating 'observability' namespace..."
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -

# 5. Install Qdrant (Vector Database)
echo "🧠 Installing Qdrant (15m timeout)..."
helm upgrade --install qdrant qdrant/qdrant \
  --namespace observability \
  --set replicaCount=1 \
  --set resources.requests.memory="256Mi" \
  --timeout 15m \
  --wait

# 6. Install OpenLIT Stack (ClickHouse, Collector, UI)
# echo "🔭 Installing OpenLIT AI Observability Stack (15m timeout)..."
# helm upgrade --install openlit openlit/openlit \
#  --namespace observability \
#  --set service.type=ClusterIP \
#  --timeout 15m \
#  --wait

# 6.5. Install Jaeger Standalone

echo "🔭 Deploying Standalone Jaeger..."
kubectl apply -f jaeger-deploy.yaml

# 7. Install OpenTelemetry Astronomy Shop (with simulated failures and Tail Sampling)
echo "🛒 Configuring OTel Astronomy Shop and Jaeger..."

# Safety check to ensure the config file exists in the directory
if [ ! -f "otel-values.yaml" ]; then
    echo "❌ Error: otel-values.yaml not found in the current directory!"
    echo "Please ensure the configuration file is present before running this script."
    exit 1
fi

echo "🛒 Installing OTel Astronomy Shop (15m timeout)..."
helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
  --namespace observability \
  -f otel-values.yaml \
  --timeout 20m \
  --wait

echo "✅ Environment Bootstrap Complete!"
echo "========================================================="
echo "To access the UIs, run these port-forward commands in separate terminal tabs:"
echo ""
echo "1. Astronomy Shop Web UI: kubectl port-forward svc/otel-demo-frontendproxy 8080:8080 -n observability"
echo "2. Jaeger Trace UI:       kubectl port-forward svc/otel-demo-jaeger-query 16686:16686 -n observability"
echo "3. OpenLIT AI Dashboard:  kubectl port-forward svc/openlit 3000:3000 -n observability"
echo "========================================================="