import os
import time
import sys
import json
import logging
import warnings
import urllib.parse
import urllib.request
from typing import TypedDict, List, Any
from dotenv import load_dotenv

# 1. Target ONLY the cosmetic Google SDK logger (preserves all real Python warnings)
logging.getLogger("google.genai").setLevel(logging.ERROR)

from qdrant_client import QdrantClient
from fastembed import TextEmbedding

# 3. LangChain & LangGraph Imports
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

# 4. Rich Terminal Formatting Imports
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.theme import Theme

# 5. Traceloop Auto-Instrumentation
from traceloop.sdk import Traceloop

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    print("❌ Error: GEMINI_API_KEY is not set.")
    sys.exit(1)

Traceloop.init(
    app_name="Autonomous-SRE-Team",
    api_endpoint="http://127.0.0.1:4318",
    disable_batch=True
)

# LLM Initialization
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

def get_text_content(content: Any) -> str:
    """Helper to convert string or list-based message content into a clean string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif hasattr(item, "text"):
                text_parts.append(item.text)
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)
    return str(content)

# =====================================================================
# 3. Diagnostic Functions (Qdrant Knowledgebase & Jaeger Traces)
# =====================================================================
def query_qdrant(query: str, collection: str = "runbooks") -> str:
    """Searches Qdrant for incident runbooks or historical tickets."""
    try:
        client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
        embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        query_vector = list(embedding_model.embed([query]))[0].tolist()

        response = client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=3
        )
        points = response.points
        if not points:
            return f"No relevant records found in collection '{collection}' for query: {query}"

        formatted = []
        for hit in points:
            formatted.append(f"--- Score: {hit.score:.3f} ---\n{json.dumps(hit.payload, indent=2)}")
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Error querying Qdrant: {str(e)}"

def query_jaeger(service: str, limit: int = 5, lookback_seconds: int = 120) -> str:
    """Queries Jaeger strictly for traces captured within the lookback window."""
    try:
        # Calculate lookback in microseconds for Jaeger API
        end_time_us = int(time.time() * 1_000_000)
        start_time_us = end_time_us - (lookback_seconds * 1_000_000)

        params = urllib.parse.urlencode({
            "service": service,
            "limit": limit,
            "start": start_time_us,
            "end": end_time_us
        })
        url = f"http://localhost:16686/api/traces?{params}"
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
                
                sanitized_tags = [
                    t for t in raw_tags 
                    if not t.get("key", "").startswith("demo.")
                ]
                
                if duration_ms > 1000 or any(t.get("key") == "error" for t in raw_tags):
                    summary.append(
                        f"Trace ID: {trace_id} | Span: {op_name} | "
                        f"Duration: {duration_ms:.2f}ms | Tags: {json.dumps(sanitized_tags)}"
                    )
        
        return "\n".join(summary[:10]) if summary else f"All {len(traces)} traces in the last {lookback_seconds}s executed within normal thresholds."
    except Exception as e:
        return f"Error querying Jaeger: {str(e)}"

# =====================================================================
# 4. State Definition & LangGraph Agent Nodes
# =====================================================================
class SREState(TypedDict):
    incident_id: str
    impacted_services: List[str]
    triage_summary: str
    telemetry_findings: str
    final_rca_report: str

def dispatcher_node(state: SREState) -> dict:
    """Triage alert context and retrieve runbook guidelines from Qdrant[cite: 3]."""
    incident_id = state["incident_id"]
    print(f"📋 [Dispatcher Node] Triaging incident {incident_id}...")

    ticket_context = query_qdrant(query=f"Incident {incident_id}", collection="tickets")
    runbook_context = query_qdrant(query=f"Troubleshooting guidelines for {incident_id}", collection="runbooks")

    prompt = [
        SystemMessage(content=(
            "You are an elite SRE dispatcher specializing in incident categorization and runbook alignment[cite: 3]. "
            "Analyze the ticket context and runbook guidelines to identify impacted microservices and triage the issue."
        )),
        HumanMessage(content=(
            f"Incident ID: {incident_id}\n\n"
            f"Ticket Context from Qdrant:\n{ticket_context}\n\n"
            f"Runbook Context from Qdrant:\n{runbook_context}\n\n"
            "Instructions:\n"
            "1. List all affected service names (e.g., 'frontend', 'recommendation', 'productcatalogservice', 'checkoutservice')[cite: 3, 4].\n"
            "2. Summarize observed symptoms.\n"
            "3. State the recommended runbook troubleshooting steps."
        ))
    ]
    
    raw_response = llm.invoke(prompt)
    triage_text = get_text_content(raw_response.content)
    
    known_services = [
        "frontend", "recommendation", "productcatalogservice", 
        "checkoutservice", "cartservice", "paymentservice", "emailservice"
    ]
    detected_services = [svc for svc in known_services if svc in triage_text.lower()]
    if not detected_services:
        detected_services = ["frontend"]

    return {
        "impacted_services": detected_services,
        "triage_summary": triage_text
    }

def troubleshooter_node(state: SREState) -> dict:
    """Investigate Jaeger traces and generate the final RCA report[cite: 3]."""
    incident_id = state["incident_id"]
    triage_summary = state["triage_summary"]
    services = state["impacted_services"]
    
    print(f"🔍 [Troubleshooter Node] Analyzing Jaeger traces for: {', '.join(services)}...")

    telemetry_dump = []
    for svc in services:
        traces = query_jaeger(service=svc, limit=5)
        telemetry_dump.append(f"=== Service: {svc} ===\n{traces}")
    telemetry_str = "\n\n".join(telemetry_dump)

    prompt = [
        SystemMessage(content=(
            "You are a senior Site Reliability Engineer specializing in distributed tracing and microservice root cause analysis[cite: 3]. "
            "Synthesize an incident Root Cause Analysis (RCA) report formatted in Markdown with the following sections:\n"
            "- Executive Summary\n"
            "- Telemetry Analysis (include trace IDs, latency metrics, and error spans)\n"
            "- Root Cause Identification\n"
            "- Immediate & Long-term Action Items"
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

# =====================================================================
# 5. Build and Compile the Workflow
# =====================================================================
workflow = StateGraph(SREState)
workflow.add_node("dispatcher", dispatcher_node)
workflow.add_node("troubleshooter", troubleshooter_node)

workflow.add_edge(START, "dispatcher")
workflow.add_edge("dispatcher", "troubleshooter")
workflow.add_edge("troubleshooter", END)

sre_graph = workflow.compile()

# =====================================================================
# 6. Execution Entry Point
# =====================================================================
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.theme import Theme

# Custom terminal color theme matching agent roles
custom_theme = Theme({
    "dispatcher": "bold cyan",
    "troubleshooter": "bold magenta",
    "tool": "bold yellow",
    "success": "bold green",
    "incident": "bold red"
})
console = Console(theme=custom_theme)

def run_sre_workflow(incident_id: str) -> str:
    console.print(Panel(
        f"[incident]🔥 Active SRE Investigation Initialized[/incident]\n[bold white]Incident Target:[/bold white] {incident_id}",
        border_style="red",
        expand=False
    ))
    
    Traceloop.set_association_properties({
        "session_id": incident_id,
        "incident_id": incident_id,
        "user_id": "sre-operator"
    })

    initial_state: SREState = {
        "incident_id": incident_id,
        "impacted_services": [],
        "triage_summary": "",
        "telemetry_findings": "",
        "final_rca_report": ""
    }

    final_report = ""

    # Stream state updates node-by-node as they finish execution
    for update in sre_graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_output in update.items():
            if node_name == "dispatcher":
                services = ", ".join(node_output.get("impacted_services", []))
                console.print(Panel(
                    Markdown(node_output["triage_summary"]),
                    title=f"[dispatcher]🤖 Agent: Incident Dispatcher[/dispatcher] | Services Flagged: [yellow]{services}[/yellow]",
                    subtitle="[dim]Qdrant Triage Complete[/dim]",
                    border_style="cyan"
                ))

            elif node_name == "troubleshooter":
                final_report = node_output["final_rca_report"]
                console.print(Panel(
                    "[bold green]✓ Jaeger Traces Parsed & Synthesized[/bold green]\n[dim]Telemetry matched against runbook constraints.[/dim]",
                    title="[troubleshooter]🔍 Agent: SRE Troubleshooter[/troubleshooter]",
                    border_style="magenta"
                ))

    return final_report

if __name__ == "__main__":
    incident_to_investigate = "INC-1045"
    report = run_sre_workflow(incident_to_investigate)

    console.print("\n")
    console.print(Panel(
        Markdown(report),
        title="[success]📋 FINAL ROOT CAUSE ANALYSIS (RCA)[/success]",
        border_style="green",
        padding=(1, 2)
    ))