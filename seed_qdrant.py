#!/usr/bin/env python3
# seed_qdrant.py - Populates the Qdrant vector database with incident tickets and SRE runbooks

import uuid
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding

def seed_database():
    print("🔌 Connecting to local Qdrant instance...")
    client = QdrantClient(url="http://localhost:6333")

    print("🧠 Initializing FastEmbed Model (BAAI/bge-small-en-v1.5)...")
    # We instantiate FastEmbed directly. This is stable and won't break with Qdrant API changes.
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # ==========================================
    # 1. Seed Incident Tickets
    # ==========================================
    print("🎫 Seeding Incident Tickets...")
    
    if client.collection_exists(collection_name="tickets"):
        client.delete_collection(collection_name="tickets")

    # The BAAI/bge-small model outputs vectors with exactly 384 dimensions
    client.create_collection(
        collection_name="tickets",
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )

    tickets = [
        "INC-1042: Urgent - Customers are reporting that the Astronomy Shop frontend is hanging, and some are seeing HTTP 500 errors when clicking on specific items. The recommendation module seems to be timing out.",
        "INC-1043: Alert - High latency detected in the Product Catalog service. Upstream services are experiencing gRPC deadline exceeded errors.",
        "INC-1044: Info - Routine database backup completed successfully."
    ]
    
    ticket_metadata = [
        {"ticket_id": "INC-1042", "priority": "High", "status": "Open", "service": "frontend, recommendation"},
        {"ticket_id": "INC-1043", "priority": "Medium", "status": "Open", "service": "productcatalog"},
        {"ticket_id": "INC-1044", "priority": "Low", "status": "Closed", "service": "database"}
    ]

    # Generate the embeddings manually
    ticket_embeddings = list(embedding_model.embed(tickets))

    # Construct the database points
    ticket_points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={"document": doc, **meta}
        )
        for doc, meta, embedding in zip(tickets, ticket_metadata, ticket_embeddings)
    ]

    # Upsert using the core Qdrant API
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
        "Runbook: Troubleshooting Recommendation Service Cache. If the recommendation service experiences high latency or throws HTTP 500s, the root cause is often a failure to reach the Valkey (formerly Redis) cache. Check the Jaeger trace to see if the span for the recommendation service contains downstream failures. If so, verify if a feature flag or network policy is blocking cache access.",
        "Runbook: Product Catalog Latency. If the Product Catalog service is throwing gRPC errors or causing cascading latency, query the Jaeger traces for the 'productcatalog' service. Look for spans with the 'error=true' attribute. This is commonly caused by upstream dependencies timing out or simulated failure feature flags being toggled on.",
        "Runbook: General Trace Analysis. When troubleshooting microservices, always start by retrieving the traces for the impacted service from Jaeger. Look at the 'duration' of the spans to find the bottleneck, and check the 'status.code' to identify where the failure originated."
    ]

    runbook_metadata = [
        {"runbook_id": "RB-001", "topic": "Recommendation Cache Failures"},
        {"runbook_id": "RB-002", "topic": "Product Catalog Errors"},
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

    print("✅ Successfully seeded Qdrant with tickets and runbooks!")

if __name__ == "__main__":
    seed_database()