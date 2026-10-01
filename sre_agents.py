import os
import sys
import time
import json
import logging
import urllib.parse
import urllib.request
from typing import TypedDict, List, Any
from dotenv import load_dotenv

logging.getLogger("google.genai").setLevel(logging.ERROR)

from qdrant_client import QdrantClient
from fastembed import TextEmbedding

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.theme import Theme

import openlit

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    print("❌ Error: GEMINI_API_KEY is not set.")
    sys.exit(1)

# Service Endpoints
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
JAEGER_URL = os.getenv("JAEGER_URL", "http://localhost:16686")
APP_ENVIRONMENT = os.getenv("OPENLIT_ENVIRONMENT", "development")

openlit.init(
    otlp_endpoint=OTLP_ENDPOINT,
    application_name="Autonomous-SRE-Team",
    environment=APP_ENVIRONMENT,
    disable_batch=True
)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

def get_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join([str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content])
    return str(content)

# FastEmbed Singleton
_EMBEDDING_MODEL = None

def get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _EMBEDDING_MODEL

def query_qdrant(query: str, collection: str = "runbooks", limit: int = 1) -> str:
    try:
        client = QdrantClient(url=QDRANT_URL, check_compatibility=False)
        embedding_model = get_embedding_model()
        query_vector = list(embedding_model.embed([query]))[0].tolist()

        response = client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit
        )
        if not response.points:
            return f"No relevant records found in '{collection}' for: {query}"

        return "\n\n".join([f"--- Score: {h.score:.3f} ---\n{json.dumps(h.payload, indent=2)}" for h in response.points])
    except Exception as e:
        return f"Error querying Qdrant: {str(e)}"

# 1. Update query_jaeger lookback default to 3600 seconds (1 hour)
def query_jaeger(service: str, limit: int = 5, lookback_seconds: int = 3600) -> str:
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
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                return f"Failed to retrieve traces: HTTP {response.status}"
            data = json.loads(response.read().decode())

        traces = data.get("data", [])
        if not traces:
            return f"No traces found for service '{service}' in the last {lookback_seconds}s."

        summary = []
        for trace_obj in traces:
            trace_id = trace_obj.get("traceID")
            for s in trace_obj.get("spans", []):
                duration_ms = s.get("duration", 0) / 1000.0
                op_name = s.get("operationName", "unknown")
                raw_tags = s.get("tags", [])
                
                # Capture slow spans or explicit error tags
                has_error = any(
                    (t.get("key") == "error" and t.get("value") in [True, "true", 1, "1"]) or
                    (t.get("key") == "error.type") or
                    (t.get("key") == "http.status_code" and int(t.get("value", 0)) >= 400)
                    for t in raw_tags
                )

                if duration_ms > 1000 or has_error:
                    summary.append(
                        f"Trace ID: {trace_id} | Span: {op_name} | "
                        f"Duration: {duration_ms:.2f}ms | Tags: {json.dumps(raw_tags)}"
                    )
        
        return "\n".join(summary[:10]) if summary else f"All {len(traces)} traces in the last {lookback_seconds}s executed normally."
    except Exception as e:
        return f"Error querying Jaeger: {str(e)}"
    
# State Definition
class SREState(TypedDict):
    incident_id: str
    impacted_services: List[str]
    triage_summary: str
    telemetry_findings: str
    final_rca_report: str

def dispatcher_node(state: SREState) -> dict:
    incident_id = state["incident_id"]
    print(f"📋 [Dispatcher Node] Triaging incident {incident_id}...")

    ticket_context = query_qdrant(query=f"Incident {incident_id}", collection="tickets", limit=1)
    runbook_context = query_qdrant(query=f"Troubleshooting guidelines for {incident_id} customer dispatch failure", collection="runbooks", limit=1)

    prompt = [
        SystemMessage(content=(
            "You are an elite SRE dispatcher specializing in microservice incident triage. "
            "Analyze the ticket and runbook to identify affected services and summarize the issue."
        )),
        HumanMessage(content=(
            f"Incident ID: {incident_id}\n\n"
            f"Ticket Context:\n{ticket_context}\n\n"
            f"Runbook Context:\n{runbook_context}\n\n"
            "Instructions:\n"
            "1. List all affected services from: ['frontend', 'customer', 'driver', 'route'].\n"
            "2. Summarize observed symptoms.\n"
            "3. State recommended runbook troubleshooting steps."
        ))
    ]
    
    raw_response = llm.invoke(prompt)
    triage_text = get_text_content(raw_response.content)
    
    known_services = ["frontend", "customer", "driver", "route"]
    detected_services = [svc for svc in known_services if svc in triage_text.lower()]
    if not detected_services:
        detected_services = ["frontend", "customer"]

    return {
        "impacted_services": detected_services,
        "triage_summary": triage_text
    }

def troubleshooter_node(state: SREState) -> dict:
    incident_id = state["incident_id"]
    triage_summary = state["triage_summary"]
    services = state["impacted_services"]
    
    print(f"🔍 [Troubleshooter Node] Analyzing Jaeger traces for: {', '.join(services)}...")

    telemetry_dump = []
    for svc in services:
        traces = query_jaeger(service=svc, limit=5, lookback_seconds=3600)
        telemetry_dump.append(f"=== Service: {svc} ===\n{traces}")
    telemetry_str = "\n\n".join(telemetry_dump)

    prompt = [
        SystemMessage(content=(
            "You are a senior Site Reliability Engineer specializing in distributed tracing. "
            "Synthesize an incident Root Cause Analysis (RCA) report in Markdown with sections:\n"
            "- Executive Summary\n"
            "- Telemetry Analysis (include trace IDs, latency metrics, and error spans)\n"
            "- Root Cause Identification\n"
            "- Immediate & Long-term Action Items\n\n"
            "CRITICAL DATA INTEGRITY INSTRUCTION:\n"
            "You must ONLY analyze the exact trace IDs, span names, latency metrics, and error tags "
            "provided in the Live Jaeger Trace Telemetry section below. "
            "DO NOT fabricate, simulate, or reconstruct hypothetical trace IDs or metrics. "
            "If a service reports no traces or normal execution, accurately state that finding."
        )),
        HumanMessage(content=(
            f"Incident ID: {incident_id}\n\n"
            f"Triage Assessment:\n{triage_summary}\n\n"
            f"Live Jaeger Trace Telemetry:\n{telemetry_str}\n\n"
            "Produce the final RCA report."
        ))
    ]

    raw_response = llm.invoke(prompt)
    rca_text = get_text_content(raw_response.content)

    return {
        "telemetry_findings": telemetry_str,
        "final_rca_report": rca_text
    }

workflow = StateGraph(SREState)
workflow.add_node("dispatcher", dispatcher_node)
workflow.add_node("troubleshooter", troubleshooter_node)
workflow.add_edge(START, "dispatcher")
workflow.add_edge("dispatcher", "troubleshooter")
workflow.add_edge("troubleshooter", END)

sre_graph = workflow.compile()

custom_theme = Theme({
    "dispatcher": "bold cyan",
    "troubleshooter": "bold magenta",
    "incident": "bold red",
    "success": "bold green"
})
console = Console(theme=custom_theme)

def run_sre_workflow(incident_id: str) -> str:
    console.print(Panel(
        f"[incident]🔥 Active SRE Investigation Initialized[/incident]\n[bold white]Incident Target:[/bold white] {incident_id}",
        border_style="red"
    ))

    initial_state: SREState = {
        "incident_id": incident_id,
        "impacted_services": [],
        "triage_summary": "",
        "telemetry_findings": "",
        "final_rca_report": ""
    }

    final_report = ""
    for update in sre_graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_output in update.items():
            if node_name == "dispatcher":
                services = ", ".join(node_output.get("impacted_services", []))
                console.print(Panel(
                    Markdown(node_output["triage_summary"]),
                    title=f"[dispatcher]🤖 Dispatcher Agent[/dispatcher] | Flagged: [yellow]{services}[/yellow]",
                    border_style="cyan"
                ))
            elif node_name == "troubleshooter":
                final_report = node_output["final_rca_report"]
                console.print(Panel(
                    "[bold green]✓ Jaeger Traces Parsed & Synthesized[/bold green]",
                    title="[troubleshooter]🔍 SRE Troubleshooter Agent[/troubleshooter]",
                    border_style="magenta"
                ))

    return final_report

if __name__ == "__main__":
    incident_to_investigate = "INC-2001"
    report = run_sre_workflow(incident_to_investigate)

    console.print("\n")
    console.print(Panel(
        Markdown(report),
        title="[success]📋 FINAL ROOT CAUSE ANALYSIS (RCA)[/success]",
        border_style="green",
        padding=(1, 2)
    ))

    sys.stdout.flush()
    os._exit(0)