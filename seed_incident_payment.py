import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding

client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

# 1. New Ticket Data (Payment Gateway / Checkout Failure)
new_ticket = {
    "ticket_id": "INC-1046",
    "document": "INC-1046: Critical - Users are unable to place orders during checkout. When submitting payment details, the checkout flow terminates with an HTTP 500 error. Downstream calls from checkoutservice to paymentservice are failing on the Charge method with gRPC errors.",
    "service": "paymentservice, checkoutservice, frontend",
    "priority": "Critical",
    "status": "Open"
}

# 2. New Runbook Data (Payment Troubleshooting Guide)
new_runbook = {
    "runbook_id": "RB-005",
    "topic": "Payment Service Authorization and Charge Failures",
    "document": "Runbook: Troubleshooting Payment Service Failures (RB-005). When checkoutservice fails to complete transactions or paymentservice throws errors: 1. Query Jaeger traces for service 'checkoutservice' and operation 'hipstershop.PaymentService/Charge' or 'paymentservice'. 2. Inspect spans for 'error=true' and check gRPC status codes (e.g., Code 13 INTERNAL or Code 3 INVALID_ARGUMENT). 3. Verify whether payment authorization feature flags (such as paymentFailure in flagd) are enabled. 4. Inspect paymentservice container logs for mock credit card validation errors or connection drops. 5. If failure is flag-induced, toggle paymentFailure to off; if container-level, restart the paymentservice deployment."
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

print("✅ Successfully seeded INC-1046 and RB-005 into Qdrant.")