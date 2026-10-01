# Autonomous SRE Incident Triage Agent: Graph-Orchestrated Telemetry Reasoning & Vector Runbook Verification

A containerized reference implementation and hands-on laboratory demonstrating autonomous Site Reliability Engineering (SRE) incident triage built with **LangGraph**, **Google Gemini**, **OpenTelemetry**, **Jaeger**, **Qdrant**, and **OpenLIT**.

This project demonstrates how autonomous agents can ingest telemetry from microservice architectures, prune diagnostic paths using deterministic vector runbooks, correlate distributed traces across cascading boundaries, and isolate root causes to dramatically reduce **Mean Time to Resolution (MTTR)**.

---

## Why Build This Lab?

We have all stared down alert storms during an outage—tracing cascading errors across microservices while jumping between dashboards, logs, and stale wiki pages. 

This repository is a self-contained, hands-on testbed designed to experiment with a better workflow: **What happens when you give an agentic AI direct access to OpenTelemetry distributed traces and deterministic operational runbooks?**

Feel free to spin this up locally, generate real microservice failure streams, and inspect the implementation:

* **Real Distributed Architecture:** Runs Jaeger's canonical **HotROD** ride-sharing application (`frontend`, `customer`, `driver`, `route`) inside a lightweight local Kind cluster.
* **No Hallucinated SOPs:** Rather than letting an LLM guess remediation steps, the agent retrieves real Markdown runbooks from a local Qdrant vector database to guide its troubleshooting path.
* **Real Trace Telemetry:** Queries local Jaeger instances using OpenTelemetry semantic conventions to catch cascading HTTP 404s, unhandled 500s, and Redis storage contention.
* **Observing the Observer:** Instruments the triage agent itself using OpenLIT, capturing LLM token costs, step durations, and reasoning traces into ClickHouse.
* **Zero Cloud Lock-in:** Built entirely on open-source standards (OTel, OTLP, Jaeger, Qdrant, ClickHouse, Kind) so you can run, break, and inspect everything locally.

---

## Executive Summary & Value Proposition

Modern distributed microservice architectures produce millions of spans per second, overwhelming on-call engineers with alert storms, opaque service dependencies, and uncoordinated dashboards.

Traditional troubleshooting relies on tribal knowledge, static playbooks, and manual trace inspection. Autonomous triage agents solve this by pairing **probabilistic large language models (LLMs)** with **deterministic operational constraints (RAG & Observability Pipelines)**:

* **Vendor-Neutral OpenTelemetry Core:** Telemetry collection is standardized on pure OpenTelemetry semantic conventions and OTLP export pipelines rather than proprietary vendor SDKs.
* **Deterministic Guardrails Over Hallucination:** Instead of allowing unconstrained LLM queries, the Dispatcher agent queries domain-specific Standard Operating Procedures (SOPs) stored in a Qdrant vector database (`RB-010`), ensuring investigations follow enterprise-approved diagnostic sequences.
* **Causal Graph Correlation:** The agent identifies cascading failure states—such as an upstream HTTP 500 error at the `frontend` dispatch boundary triggered by an unhandled downstream 404 from the `customer` service and concurrent Redis mutex contention in `driver`.
* **Autonomous Hypothesis Correction:** When initial ticket context misidentifies affected services, the Troubleshooter agent cross-references live Jaeger traces to self-correct the investigation scope.
* **Agent Observability Built-In:** The agent runtime is self-instrumented via OpenLIT, exporting LLM tokens, step durations, and tool calls as standard OTel traces for governance, auditability, and cost accounting.

---

## Architecture & Workflow

The architecture decouples operational knowledge (vector database), service telemetry (distributed tracing), and persistent agent governance (AI observability):

```mermaid
flowchart TD
    subgraph Persistent_Observability ["Persistent Observability (Docker / OrbStack)"]
        OL["OpenLIT Server<br>Port 3000 UI / 4318 OTLP"]
        CH[("ClickHouse DB<br>Traces & Metrics")]
        OL --- CH
    end

    subgraph Agent_Runtime ["Agent Runtime (LangGraph)"]
        AG["Dispatcher & Troubleshooter Nodes<br>Google Gemini 3.8 Flash"]
        OL_SDK["OpenLIT SDK"]
        AG --- OL_SDK
        OL_SDK -->|"Agent Telemetry (Port 4318)"| OL
    end

    subgraph Ephemeral_Cluster ["Ephemeral Kind Cluster (sre-demo)"]
        QD[("Qdrant Vector DB<br>Tickets & Runbooks")]
        HR["HotROD Microservices<br>(frontend, customer, driver, route)"]
        JG["Jaeger Standalone<br>Workload Traces"]
        HR -->|"Distributed Traces (OTLP)"| JG
    end

    AG -->|"Vector RAG (Port 6333)"| QD
    AG -->|"Trace Analysis (Port 16686)"| JG