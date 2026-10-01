#!/usr/bin/env python3
# seed_qdrant.py - Seeds Qdrant with HotROD tickets and SRE runbooks

import uuid
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding

def seed_database():
    print("🔌 Connecting to local Qdrant instance...")
    client = QdrantClient(url="http://localhost:6333", check_compatibility=False)

    print("🧠 Initializing FastEmbed Model (BAAI/bge-small-en-v1.5)...")
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # ==========================================
    # 1. Seed Incident Tickets
    # ==========================================
    print("🎫 Seeding Incident Tickets...")
    
    if client.collection_exists(collection_name="tickets"):
        client.delete_collection(collection_name="tickets")

    client.create_collection(
        collection_name="tickets",
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )

    tickets = [
        "INC-1090: Info - Daily PostgreSQL automated database snapshot completed without error.",
        "INC-2001: Critical - Ride requests are failing for specific customers with HTTP 500 errors. Frontend dispatch calls to customer and route services are failing or timing out.",
        "INC-2002: Alert - Elevated latency observed across driver service dispatch pool during peak shift rotation."
    ]
    
    ticket_metadata = [
        {"ticket_id": "INC-1090", "priority": "Low", "status": "Closed", "service": "database"},
        {"ticket_id": "INC-2001", "priority": "Critical", "status": "Open", "service": "frontend, customer, route"},
        {"ticket_id": "INC-2002", "priority": "Medium", "status": "Open", "service": "driver"}
    ]

    ticket_embeddings = list(embedding_model.embed(tickets))

    ticket_points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={"document": doc, **meta}
        )
        for doc, meta, embedding in zip(tickets, ticket_metadata, ticket_embeddings)
    ]

    client.upsert(collection_name="tickets", points=ticket_points)

    # ==========================================
    # 2. Seed SRE Runbooks
    # ==========================================
    print("📚 Seeding SRE Runbooks...")
    
    if client.collection_exists(collection_name="runbooks"):
        client.delete_collection(collection_name="runbooks")

    client.create_collection(
        collection_name="runbooks",
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )

    runbooks = [
        "Runbook: Driver Pool Mutex & Contention (RB-009). When driver service latency spikes under heavy concurrent requests, check Jaeger traces for the 'driver' service. Look for lock contention or worker queue exhaustion on FindNearest operations.",
        "Runbook: Troubleshooting HotROD Customer Dispatch Failures (RB-010). When frontend /dispatch requests return HTTP 500 or throw exceptions: 1. Query Jaeger traces for the 'frontend' and 'customer' services. 2. Look for spans with 'error=true' or HTTP 500 status codes. 3. Check customer ID resolution in the customer service. If the customer ID is invalid or cannot be found in the database, customer lookup terminates immediately. 4. Verify downstream route calculation RPCs between frontend and route services. 5. If failure is an invalid customer ID, validate input upstream; if network-related, verify Kubernetes pod communication.",
        "Runbook: General Trace Analysis (RB-003). When troubleshooting microservices, always start by retrieving the traces for the impacted service from Jaeger. Look at the duration of the spans to find the bottleneck, and check the status.code to identify where the failure originated."
    ]

    runbook_metadata = [
        {"runbook_id": "RB-009", "topic": "Driver Mutex Contention"},
        {"runbook_id": "RB-010", "topic": "HotROD Customer Dispatch Failures"},
        {"runbook_id": "RB-003", "topic": "General Trace Analysis"}
    ]

    runbook_embeddings = list(embedding_model.embed(runbooks))

    runbook_points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={"document": doc, **meta}
        )
        for doc, meta, embedding in zip(runbooks, runbook_metadata, runbook_embeddings)
    ]

    client.upsert(collection_name="runbooks", points=runbook_points)

    print("✅ Successfully seeded Qdrant with HotROD tickets and runbooks (INC-2001 / RB-010)!")

if __name__ == "__main__":
    seed_database()