#!/usr/bin/env python3
# seed_qdrant.py - Populates Qdrant with payment incident tickets and SRE runbooks

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
        "INC-1042: Urgent - Customers are reporting that the Astronomy Shop frontend is hanging, and some are seeing HTTP 500 errors when clicking on specific items. The recommendation module seems to be timing out.",
        "INC-1044: Info - Routine database backup completed successfully.",
        "INC-1046: Critical - Users are unable to place orders during checkout. When submitting payment details, the checkout flow terminates with an HTTP 500 error. Downstream calls from checkoutservice to paymentservice are failing on the Charge method with gRPC errors."
    ]
    
    ticket_metadata = [
        {"ticket_id": "INC-1042", "priority": "High", "status": "Open", "service": "frontend, recommendation"},
        {"ticket_id": "INC-1044", "priority": "Low", "status": "Closed", "service": "database"},
        {"ticket_id": "INC-1046", "priority": "Critical", "status": "Open", "service": "paymentservice, checkoutservice, frontend"}
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
        "Runbook: Troubleshooting Recommendation Service Cache (RB-001). If the recommendation service experiences high latency or throws HTTP 500s, the root cause is often a failure to reach the Valkey cache. Check the Jaeger trace to see if the span for the recommendation service contains downstream failures.",
        "Runbook: General Trace Analysis (RB-003). When troubleshooting microservices, always start by retrieving the traces for the impacted service from Jaeger. Look at the duration of the spans to find the bottleneck, and check the status.code to identify where the failure originated.",
        "Runbook: Troubleshooting Payment Service Failures (RB-005). When checkoutservice fails to complete transactions or paymentservice throws errors: 1. Query Jaeger traces for service 'checkoutservice' and operation 'hipstershop.PaymentService/Charge' or 'paymentservice'. 2. Inspect spans for 'error=true' and check gRPC status codes (e.g., Code 13 INTERNAL or Code 3 INVALID_ARGUMENT). 3. Verify whether payment authorization feature flags (such as paymentFailure in flagd) are enabled. 4. Inspect paymentservice container logs for mock credit card validation errors or connection drops. 5. If failure is flag-induced, toggle paymentFailure to off; if container-level, restart the paymentservice deployment."
    ]

    runbook_metadata = [
        {"runbook_id": "RB-001", "topic": "Recommendation Cache Failures"},
        {"runbook_id": "RB-003", "topic": "General Trace Analysis"},
        {"runbook_id": "RB-005", "topic": "Payment Service Authorization and Charge Failures"}
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

    print("✅ Successfully seeded Qdrant with tickets and runbooks (including INC-1046 / RB-005)!")

if __name__ == "__main__":
    seed_database()