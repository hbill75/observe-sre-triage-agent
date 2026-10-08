import json
import os
import time
import urllib.parse
import urllib.request
from fastmcp import FastMCP

# FastMCP configures host and port via environment variables
os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
os.environ.setdefault("FASTMCP_PORT", "8000")

# Instantiate with only the server name
mcp = FastMCP("jaeger-mcp-server")

# In-cluster Jaeger query endpoint
JAEGER_URL = os.getenv("JAEGER_URL", "http://jaeger-standalone.default.svc.cluster.local:16686")

@mcp.tool()
def query_service_traces(service: str, limit: int = 5, lookback_seconds: int = 180) -> str:
    """
    Queries Jaeger distributed traces for a specific microservice.
    Filters out healthy spans and returns traces with latency > 1000ms or error tags.
    """
    try:
        end_time_us = int(time.time() * 1_000_000)
        start_time_us = end_time_us - (lookback_seconds * 1_000_000)

        params = urllib.parse.urlencode({
            "service": service,
            "limit": limit,
            "start": start_time_us,
            "end": end_time_us
        })
        url = f"{JAEGER_URL}/api/traces?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return f"Jaeger query failed with status code HTTP {resp.status}"
            data = json.loads(resp.read().decode())

        traces = data.get("data", [])
        if not traces:
            return f"No traces found for service '{service}' in the last {lookback_seconds}s."

        summary = []
        for trace_obj in traces:
            trace_id = trace_obj.get("traceID")
            jaeger_ui_link = f"http://localhost:16686/trace/{trace_id}"

            for s in trace_obj.get("spans", []):
                duration_ms = s.get("duration", 0) / 1000.0
                op_name = s.get("operationName", "unknown")
                raw_tags = s.get("tags", [])

                has_error = any(
                    (t.get("key") == "error" and t.get("value") in [True, "true", 1, "1"]) or
                    (t.get("key") == "error.type") or
                    (t.get("key") in ["http.status_code", "http.response.status_code"] and int(str(t.get("value", 0))) >= 400)
                    for t in raw_tags
                )

                if duration_ms > 1000 or has_error:
                    sanitized_tags = [t for t in raw_tags if not t.get("key", "").startswith("demo.")]
                    summary.append(
                        f"Trace ID: {trace_id} (UI: {jaeger_ui_link}) | "
                        f"Span: {op_name} | Duration: {duration_ms:.2f}ms | "
                        f"Tags: {json.dumps(sanitized_tags)}"
                    )

        if not summary:
            return f"All {len(traces)} traces for '{service}' completed normally within threshold."

        return "\n".join(summary[:10])

    except Exception as e:
        return f"Error executing Jaeger MCP query: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="sse")