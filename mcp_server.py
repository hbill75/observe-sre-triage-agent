#!/usr/bin/env python3
# mcp_server.py - FastMCP server exposing Jaeger trace analysis to AI agents

import requests
from fastmcp import FastMCP

mcp = FastMCP("JaegerSREBridge")

# Jaeger's UI query backend endpoint
JAEGER_API_URL = "http://localhost:16686/api/traces"

@mcp.tool()
def analyze_service_traces(service_name: str, limit: int = 5) -> str:
    """
    Query Jaeger for recent traces of a specific microservice to identify errors and latency bottlenecks.
    
    Args:
        service_name: The name of the microservice (e.g., 'frontend', 'recommendation', 'productcatalog')
        limit: Number of recent traces to analyze (default: 5)
    """
    try:
        print(f"🔍 MCP Bridge querying Jaeger for service: {service_name}")
        
        # Jaeger query parameters
        params = {
            "service": service_name,
            "limit": limit
        }
        
        response = requests.get(JAEGER_API_URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        traces = data.get("data", [])
        
        if not traces:
            return f"No traces found for service: '{service_name}'. Ensure traffic is flowing."
        
        analysis_results = []
        for trace in traces[:limit]:
            trace_id = trace.get("traceID", "unknown")
            spans = trace.get("spans", [])
            
            error_count = 0
            max_duration = 0
            longest_span = "unknown"
            
            for span in spans:
                tags = span.get("tags", [])
                is_error = any(tag.get("key") == "error" and tag.get("value") is True for tag in tags)
                if is_error:
                    error_count += 1
                
                duration_ms = span.get("duration", 0) / 1000
                if duration_ms > max_duration:
                    max_duration = duration_ms
                    longest_span = span.get("operationName", "unknown")

            summary = f"Trace ID: {trace_id} | Spans: {len(spans)}\n"
            if error_count > 0:
                summary += f"  ⚠️ CRITICAL: Found {error_count} error spans.\n"
            summary += f"  ⏱️ Longest Operation: '{longest_span}' took {max_duration:.2f}ms\n"
            analysis_results.append(summary)

        return f"Trace Analysis for {service_name}:\n" + "\n".join(analysis_results)
        
    except requests.exceptions.HTTPError as e:
        return f"Jaeger API HTTP Error ({e.response.status_code}): Check endpoint path."
    except requests.exceptions.ConnectionError:
        return "Connection Error: Could not reach Jaeger at http://localhost:16686. Verify kubectl port-forward."
    except Exception as e:
        return f"Unexpected error: {str(e)}"

if __name__ == "__main__":
    mcp.run()