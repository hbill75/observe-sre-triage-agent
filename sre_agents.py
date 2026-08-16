#!/usr/bin/env python3
# sre_agents.py - Orchestrates the AI SRE team to resolve open incidents

import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 0. Initialize OpenLIT FIRST (Before Any Imports)
# ==========================================
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
os.environ["OPENLIT_CAPTURE_MESSAGE_CONTENT"] = "true"

import openlit
openlit.init(
    application_name="Autonomous-SRE-Team",
    otlp_endpoint="http://localhost:4318",
    environment="development",
    capture_message_content=True
)
print("🔭 OpenLIT tracing enabled!")

# ==========================================
# 1. Imports & Bulletproof LiteLLM Monkeypatch Bridge
# ==========================================
from opentelemetry import trace
tracer = trace.get_tracer("sre.autonomous.agents")

import litellm

original_completion = litellm.completion
original_acompletion = litellm.acompletion

def patched_completion(*args, **kwargs):
    model = kwargs.get("model", args[0] if args else "unknown-model")
    messages = kwargs.get("messages", args[1] if len(args) > 1 else [])
    
    with tracer.start_as_current_span(f"llm.call.{model}") as span:
        span.set_attribute("gen_ai.system", "gemini")
        span.set_attribute("gen_ai.request.model", str(model))
        span.set_attribute("gen_ai.input.messages", str(messages))
        span.set_attribute("gen_ai.prompt", str(messages))
        
        response = original_completion(*args, **kwargs)
        
        try:
            content = response.choices[0].message.content
            span.set_attribute("gen_ai.output.messages", str(content))
            span.set_attribute("gen_ai.completion", str(content))
        except Exception:
            pass
        return response

async def patched_acompletion(*args, **kwargs):
    model = kwargs.get("model", args[0] if args else "unknown-model")
    messages = kwargs.get("messages", args[1] if len(args) > 1 else [])
    
    with tracer.start_as_current_span(f"llm.call.async.{model}") as span:
        span.set_attribute("gen_ai.system", "gemini")
        span.set_attribute("gen_ai.request.model", str(model))
        span.set_attribute("gen_ai.input.messages", str(messages))
        span.set_attribute("gen_ai.prompt", str(messages))
        
        response = await original_acompletion(*args, **kwargs)
        
        try:
            content = response.choices[0].message.content
            span.set_attribute("gen_ai.output.messages", str(content))
            span.set_attribute("gen_ai.completion", str(content))
        except Exception:
            pass
        return response

litellm.completion = patched_completion
litellm.acompletion = patched_acompletion

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

# ==========================================
# 2. Initialize Clients & Models
# ==========================================
print("🧠 Initializing Gemini 3.6 Flash...")
gemini_llm = LLM(
    model="gemini/gemini-3.6-flash", 
    api_key=os.environ.get("GEMINI_API_KEY")
)

print("🔌 Connecting to Qdrant & Initializing Embedding Model...")
qdrant = QdrantClient(url="http://localhost:6333")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# ==========================================
# 3. Define Custom Tools
# ==========================================
@tool("Fetch Open Incident Tickets")
def fetch_tickets_tool() -> str:
    """Fetch all open incident tickets from the database."""
    records, _ = qdrant.scroll(collection_name="tickets", limit=5, with_payload=True)
    open_tickets = []
    for r in records:
        if r.payload.get("status") == "Open":
            open_tickets.append(f"Ticket ID: {r.payload.get('ticket_id')} | Impacted Services: {r.payload.get('service')} | Description: {r.payload.get('document')}")
    return "\n".join(open_tickets) if open_tickets else "No open tickets found."

@tool("Search SRE Runbooks")
def search_runbooks_tool(query: str) -> str:
    """Search the SRE runbooks database for troubleshooting steps related to a specific service or error."""
    query_vector = list(embedding_model.embed([query]))[0].tolist()
    results = qdrant.query_points(
        collection_name="runbooks",
        query=query_vector,
        limit=1
    )
    return results.points[0].payload.get("document", "No document found.") if results.points else "No relevant runbook found."

# ==========================================
# 4. Define Agents & Tasks
# ==========================================
dispatcher = Agent(
    role="Incident Dispatcher",
    goal="Identify the highest priority open ticket and extract the names of the failing microservices.",
    backstory="You are a seasoned IT Operations Dispatcher monitoring incoming alerts.",
    tools=[fetch_tickets_tool],
    llm=gemini_llm,
    verbose=True
)

troubleshooter = Agent(
    role="SRE Troubleshooter",
    goal="Diagnose the root cause of service failures by reading runbooks and analyzing live Jaeger telemetry.",
    backstory="You are an elite Site Reliability Engineer (SRE).",
    tools=[search_runbooks_tool],
    mcps=[{"command": "python", "args": ["mcp_server.py"]}],
    llm=gemini_llm,
    verbose=True
)

triage_task = Task(
    description="Fetch the open incident tickets. Identify the ticket containing 'Urgent' or 'High' priority HTTP 500 errors. Extract the exact name of the impacted service(s).",
    expected_output="Ticket ID and exact names of impacted services.",
    agent=dispatcher
)

rca_task = Task(
    description="Search SRE runbooks and use 'analyze_service_traces' to write a final Root Cause Analysis (RCA) report.",
    expected_output="Professional Root Cause Analysis (RCA) report.",
    agent=troubleshooter
)

# ==========================================
# 5. Form Crew & Execute with Tracing Wrapper
# ==========================================
sre_crew = Crew(
    agents=[dispatcher, troubleshooter],
    tasks=[triage_task, rca_task],
    process=Process.sequential,
    verbose=True
)

@openlit.trace
def execute_sre_workflow():
    with tracer.start_as_current_span("crewai.reasoning_chain") as parent_span:
        parent_span.set_attribute("crew.agents", "Incident Dispatcher, SRE Troubleshooter")
        result = sre_crew.kickoff()
        parent_span.set_attribute("gen_ai.completion", str(result))
        return result

if __name__ == "__main__":
    print("🚀 Initiating Autonomous SRE Incident Response...")
    result = execute_sre_workflow()
    
    print("\n==================================================")
    print("🎯 FINAL ROOT CAUSE ANALYSIS REPORT")
    print("==================================================")
    print(result)