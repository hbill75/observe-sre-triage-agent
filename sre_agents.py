#!/usr/bin/env python3
# sre_agents.py - Orchestrates the AI SRE team to resolve open incidents

import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

# Load API keys from .env
load_dotenv()

# ==========================================
# 1. Initialize Clients & Models
# ==========================================
print("🔌 Connecting to Qdrant & Initializing Embedding Model...")
qdrant = QdrantClient(url="http://localhost:6333")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# Initialize the Gemini LLM
print("🧠 Initializing Gemini 3.6 Flash...")
gemini_llm = LLM(
    model="gemini/gemini-3.6-flash", 
    api_key=os.environ.get("GEMINI_API_KEY")
)

# Initialize OpenLIT Tracing
try:
    import openlit
    openlit.init(
        application_name="Autonomous-SRE-Team",
        otlp_endpoint="http://localhost:4318"
    )
    print("🔭 OpenLIT tracing enabled!")
except ImportError:
    pass

# ==========================================
# 2. Define Custom Tools for the Agents
# ==========================================
@tool("Fetch Open Incident Tickets")
def fetch_tickets_tool() -> str:
    """Fetch all open incident tickets from the database."""
    records, _ = qdrant.scroll(collection_name="tickets", limit=5, with_payload=True)
    open_tickets = []
    for r in records:
        if r.payload.get("status") == "Open":
            open_tickets.append(f"Ticket ID: {r.payload.get('ticket_id')} | Impacted Services: {r.payload.get('service')} | Description: {r.payload.get('document')}")
    
    if not open_tickets:
        return "No open tickets found."
    return "\n".join(open_tickets)

@tool("Search SRE Runbooks")
def search_runbooks_tool(query: str) -> str:
    """Search the SRE runbooks database for troubleshooting steps related to a specific service or error."""
    # 1. Generate the vector
    query_vector = list(embedding_model.embed([query]))[0].tolist()
    
    # 2. The architecturally correct Qdrant SDK method
    results = qdrant.query_points(
        collection_name="runbooks",
        query=query_vector,
        limit=1
    )
    
    if results.points:
        return results.points[0].payload.get("document", "No document found.")
    return "No relevant runbook found for this query."

# ==========================================
# 3. Define the AI Agents
# ==========================================
dispatcher = Agent(
    role="Incident Dispatcher",
    goal="Identify the highest priority open ticket and extract the names of the failing microservices.",
    backstory="You are a seasoned IT Operations Dispatcher. You monitor incoming alerts, quickly grasp which system is failing, and hand off exact service names to the engineering team.",
    tools=[fetch_tickets_tool],
    llm=gemini_llm,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
    max_execution_time=60
)

troubleshooter = Agent(
    role="SRE Troubleshooter",
    goal="Diagnose the root cause of service failures by reading runbooks and analyzing live Jaeger telemetry.",
    backstory="You are an elite Site Reliability Engineer (SRE). You never guess. When handed a failing service, you immediately search the runbooks for known issues, then use the trace analysis tool to inspect live telemetry to confirm the exact bottleneck.",
    tools=[search_runbooks_tool],
    # ---------------------------------------------------------
    # THE PROPER MCP INTEGRATION:
    # CrewAI will automatically launch mcp_server.py as a 
    # separate process and fetch its tools dynamically via stdio!
    # ---------------------------------------------------------
    mcps=[
        {
            "command": "python",
            "args": ["mcp_server.py"]
        }
    ],
    llm=gemini_llm,
    verbose=True,
    allow_delegation=False,
    max_iter=7,
    max_execution_time=120
)

# ==========================================
# 4. Define the Tasks
# ==========================================
triage_task = Task(
    description="Fetch the open incident tickets. Identify the ticket containing 'Urgent' or 'High' priority HTTP 500 errors. Extract the exact name of the impacted service(s) from the ticket payload.",
    expected_output="A brief summary containing the Ticket ID and the exact names of the impacted services to be investigated.",
    agent=dispatcher
)

rca_task = Task(
    description=(
        "Using the impacted service names identified by the Dispatcher, complete these two steps: "
        "1. Search the SRE runbooks for troubleshooting instructions regarding those services. "
        "2. Use the 'analyze_service_traces' tool on the impacted services to find the actual errors or latency in the live telemetry. "
        "Write a final Root Cause Analysis (RCA) report based ONLY on what the trace tool returns."
    ),
    expected_output="A professional Root Cause Analysis (RCA) report detailing the failing service, the exact error counts or latency observed in the traces, and the recommended fix from the runbook.",
    agent=troubleshooter
)

# ==========================================
# 5. Form the Crew and Execute!
# ==========================================
sre_crew = Crew(
    agents=[dispatcher, troubleshooter],
    tasks=[triage_task, rca_task],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    print("🚀 Initiating Autonomous SRE Incident Response...")
    result = sre_crew.kickoff()
    
    print("\n==================================================")
    print("🎯 FINAL ROOT CAUSE ANALYSIS REPORT")
    print("==================================================")
    print(result)