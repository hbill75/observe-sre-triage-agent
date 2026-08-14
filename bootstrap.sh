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
echo "📦 Creating Kubernetes cluster 'sre-demo' using kind..."
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
echo "🧠 Installing Qdrant..."
helm upgrade --install qdrant qdrant/qdrant \
  --namespace observability \
  --set replicaCount=1 \
  --set resources.requests.memory="256Mi" \
  --wait

# 6. Install OpenLIT Stack (ClickHouse, Collector, UI)
echo "🔭 Installing OpenLIT AI Observability Stack..."
helm upgrade --install openlit openlit/openlit \
  --namespace observability \
  --wait

# 7. Install OpenTelemetry Astronomy Shop (with simulated failures)
echo "🛒 Installing OTel Astronomy Shop and Jaeger..."
cat <<EOF > otel-values.yaml
# Enable Jaeger as a sub-chart for trace storage
observability:
  jaeger:
    enabled: true

# Configure feature flags to simulate the exact errors our SRE agent will fix
components:
  flagd:
    configMap:
      create: true
      data:
        demo.flagd.json: |
          {
            "\$schema": "https://flagd.dev/schema/v0/flags.json",
            "flags": {
              "productCatalogFailure": {
                "description": "Fail product catalog service to trigger Agent investigation",
                "state": "ENABLED",
                "variants": { "on": true, "off": false },
                "defaultVariant": "on"
              }
            }
          }
EOF

helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
  --namespace observability \
  -f otel-values.yaml \
  --wait

echo "✅ Environment Bootstrap Complete!"
echo "========================================================="
echo "To access the UIs, run these port-forward commands in separate terminal tabs:"
echo ""
echo "1. Astronomy Shop Web UI: kubectl port-forward svc/otel-demo-frontendproxy 8080:8080 -n observability"
echo "2. Jaeger Trace UI:       kubectl port-forward svc/otel-demo-jaeger-query 16686:16686 -n observability"
echo "3. OpenLIT AI Dashboard:  kubectl port-forward svc/openlit 3000:3000 -n observability"
echo "========================================================="