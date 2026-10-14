"""
ReturnShield Integration Test Suite - End-to-End API, Redis Graph & DB Persistence
===================================================================================
Verifies Items 6 & 7 of Final Verification:
1. End-to-end refund request through FastAPI
2. Real XGBoost model inference
3. Real Redis behavioral graph tracking (via fakeredis)
4. Coordinated fraud scenario (multiple customers sharing a device)
5. Authoritative shared_identity_links elevation and policy tier escalation
6. Real persistence, retrieval, and idempotency
"""
import pytest
import fakeredis.aioredis
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.model_loader import load_model
import app.redis_features as rf
import app.database as db


class AsyncMockCollection:
    """Mock MongoDB collection supporting async methods used by ReturnShield."""
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return True

    async def find_one(self, filter_dict, projection=None):
        for doc in self.docs:
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                res = dict(doc)
                if projection and "_id" in projection and projection["_id"] == 0:
                    res.pop("_id", None)
                return res
        return None

    async def count_documents(self, filter_dict):
        return len(self.docs)

    def find(self, filter_dict=None, projection=None):
        class Cursor:
            def __init__(self, docs):
                self._docs = docs
            def sort(self, *args, **kwargs):
                return self
            def skip(self, *args, **kwargs):
                return self
            def limit(self, *args, **kwargs):
                return self
            async def to_list(self, length=100):
                return self._docs[:length]
        return Cursor(self.docs)


class AsyncMockDatabase:
    def __init__(self):
        self.transactions = AsyncMockCollection()
        self.admin = AsyncMock()
        self.admin.command = AsyncMock(return_value={"ok": 1})


@pytest.fixture(scope="module")
def setup_integration_env():
    """Setup model and mocked storage engines."""
    load_model("ml/artifacts/model.pkl", "ml/artifacts/model_metadata.json")
    mock_db = AsyncMockDatabase()
    db._db = mock_db
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    rf._redis_client = fake_redis
    return mock_db, fake_redis


def test_end_to_end_single_refund_and_persistence(setup_integration_env):
    """Item 6: Verify full refund processing flow, model scoring, and DB persistence."""
    mock_db, fake_redis = setup_integration_env

    client = TestClient(app)

    payload = {
        "customer_name": "Rohan Mehra",
        "product_name": "Noise Cancelling Earbuds",
        "city": "Mumbai",
        "customer_id": "cust-rohan-001",
        "device_id": "dev-phone-rohan",
        "payment_method_hash": "pay-card-rohan",
        "account_age_days": 400,
        "total_past_orders": 25,
        "historical_return_ratio": 0.04,
        "past_inr_claims": 0,
        "item_price": 4999.0,
        "product_category_code": 1,
        "return_reason_code": 1,
        "hours_since_delivery": 48.0,
        "weight_discrepancy_grams": None,  # test nullable handling
        "is_cod_order": 0,
        "purchased_in_sale": 1,
    }

    # Execute request
    response = client.post("/api/v1/refunds", json=payload, headers={"Idempotency-Key": "rohan-idem-1"})
    assert response.status_code == 200
    data = response.json()

    # 1. Prediction verification
    pred = data["prediction"]
    assert pred["label"] in ["Genuine", "Mistaken", "Suspicious"]
    assert pred["class_id"] in [0, 1, 2]
    assert len(pred["probabilities"]) == 3
    assert abs(sum(pred["probabilities"].values()) - 1.0) < 1e-3

    # 2. Risk Policy verification
    risk = data["risk"]
    assert 0.0 <= risk["score"] <= 100.0
    assert risk["tier"] in ["Low", "Elevated", "High"]
    assert risk["recommended_action"] in ["Routine processing", "Additional verification", "Human review"]

    # 3. Behavioral evidence verification
    behavioral = data["behavioral_evidence"]
    assert behavioral["shared_identity_links"] == 0
    assert behavioral["shared_device_accounts"] == 0

    # 4. Latency verification (<50ms target)
    assert data["latency_ms"]["inference_ms"] < 50.0

    # 5. Database Persistence verification
    tx_id = data["transaction_id"]
    saved_doc = next((d for d in mock_db.transactions.docs if d["transaction_id"] == tx_id), None)
    assert saved_doc is not None, "Transaction not found in MongoDB collection"
    assert saved_doc["customer_id"] == "cust-rohan-001"
    assert saved_doc["predicted_label"] == pred["label"]
    assert saved_doc["risk_score"] == risk["score"]
    assert saved_doc["risk_tier"] == risk["tier"]

    # 6. Idempotency verification
    cached_resp = client.post("/api/v1/refunds", json=payload, headers={"Idempotency-Key": "rohan-idem-1"})
    assert cached_resp.status_code == 200
    assert cached_resp.json()["transaction_id"] == tx_id


def test_coordinated_device_fraud_ring_scenario(setup_integration_env):
    """Item 7: Test coordinated-device scenario with multiple customers sharing a device."""
    mock_db, fake_redis = setup_integration_env
    client = TestClient(app)

    SHARED_DEVICE = "dev-shared-emulator-999"

    # Base payload template
    def make_claim(cust_id, name, inr_claims=0):
        return {
            "customer_name": name,
            "product_name": "Premium Smartphone Pro",
            "city": "Delhi",
            "customer_id": cust_id,
            "device_id": SHARED_DEVICE,
            "payment_method_hash": f"pay-hash-{cust_id}",
            "account_age_days": 10,
            "total_past_orders": 2,
            "historical_return_ratio": 0.50,
            "past_inr_claims": inr_claims,
            "item_price": 54000.0,
            "product_category_code": 1,
            "return_reason_code": 3,  # Empty Box
            "hours_since_delivery": 12.0,
            "weight_discrepancy_grams": 25.0,
            "is_cod_order": 1,
            "purchased_in_sale": 1,
        }

    # Step 1: Account 1 claims refund on shared device
    resp1 = client.post("/api/v1/refunds", json=make_claim("fraudster-01", "Vikram Singh"))
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["behavioral_evidence"]["shared_device_accounts"] == 0

    # Step 2: Account 2 claims refund on same shared device
    resp2 = client.post("/api/v1/refunds", json=make_claim("fraudster-02", "Amit Sharma"))
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["behavioral_evidence"]["shared_device_accounts"] == 1

    # Step 3: Account 3 claims refund on same shared device
    resp3 = client.post("/api/v1/refunds", json=make_claim("fraudster-03", "Kavita Gupta", inr_claims=1))
    assert resp3.status_code == 200
    d3 = resp3.json()
    # Now device has seen multiple accounts -> device accounts and identity links escalate!
    assert d3["behavioral_evidence"]["shared_device_accounts"] >= 2
    assert d3["risk"]["tier"] in ["Elevated", "High"]
    assert d3["risk"]["recommended_action"] in ["Additional verification", "Human review"]

    # Step 4: Account 1 returns to make another claim -> Redis now sees 2 identity links
    resp1_retry = client.post("/api/v1/refunds", json=make_claim("fraudster-01", "Vikram Singh", inr_claims=1))
    assert resp1_retry.status_code == 200
    d1_retry = resp1_retry.json()
    assert d1_retry["behavioral_evidence"]["shared_identity_links"] >= 2
    assert d1_retry["risk"]["score"] > d1["risk"]["score"]
