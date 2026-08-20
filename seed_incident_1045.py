import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding

client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# 1. New Ticket Data
new_ticket = {
    "ticket_id": "INC-1045",
    "document": "INC-1045: Critical - Users are unable to load product pages or complete checkout. Calls to the Product Catalog service are failing with gRPC errors, causing cascading 500 errors across frontend and cart verification.",
    "service": "productcatalogservice, frontend, checkoutservice",
    "priority": "Critical",
    "status": "Open"
}

# 2. New Runbook Data
new_runbook = {
    "runbook_id": "RB-004",
    "topic": "Product Catalog Service Failures",
    "document": "Runbook: Troubleshooting Product Catalog Service Failures (RB-004). When productcatalogservice throws errors or causes cascading failures to frontend and checkout: 1. Query Jaeger traces for 'productcatalogservice' and 'frontend'. 2. Check for spans with 'error=true' or gRPC status codes other than 0 (OK). 3. Identify if the service is rejecting GetProduct or ListProducts calls directly. 4. Check for downstream database locks or service configuration errors."
}

# 3. Generate Embeddings & Upsert to Qdrant
ticket_vector = list(embedding_model.embed([new_ticket["document"]]))[0].tolist()
client.upsert(
    collection_name="tickets",
    points=[
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=ticket_vector,
            payload=new_ticket
        )
    ]
)

runbook_vector = list(embedding_model.embed([new_runbook["document"]]))[0].tolist()
client.upsert(
    collection_name="runbooks",
    points=[
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=runbook_vector,
            payload=new_runbook
        )
    ]
)

print("✅ Successfully seeded INC-1045 and RB-004 into Qdrant.")