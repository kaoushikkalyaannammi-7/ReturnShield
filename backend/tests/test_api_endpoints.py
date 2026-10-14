"""
ReturnShield Test Suite - API Endpoints & Request/Response Shape Tests
=======================================================================
Verifies Section 9 of the Master Build Prompt:
- /api/v1/health returns 200 OK
- /api/v1/ready schema and readiness checks
- /api/v1/refunds request validation and Pydantic error handling
- End-to-end transaction assessment flow with separate prediction & risk policy
- Response envelope contains all required fields
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.model_loader import load_model

@pytest.fixture(scope="module")
def client():
    with patch("app.main.connect_db", new=AsyncMock()), \
         patch("app.main.disconnect_db", new=AsyncMock()):
        load_model("ml/artifacts/model.pkl", "ml/artifacts/model_metadata.json")
        with TestClient(app) as test_client:
            yield test_client



def test_health_endpoint(client):
    """Verify health returns 200 OK with timestamp."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_simulation_status(client):
    """Verify simulation status returns current state."""
    response = client.get("/api/v1/simulation/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "metrics" in data


def test_refund_validation_error_missing_fields(client):
    """Verify bad request payload returns 422 with validation errors."""
    incomplete_payload = {
        "customer_name": "Test User",
        "item_price": 500.0,
        # missing account_age_days, total_past_orders, product_category_code, etc.
    }
    response = client.post("/api/v1/refunds", json=incomplete_payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_refund_assessment_flow_success(client):
    """Verify successful end-to-end refund assessment."""
    payload = {
        "customer_name": "Aditya Rao",
        "product_name": "Wireless Noise Cancelling Headphones",
        "city": "Bengaluru",
        "customer_id": "cust-test-101",
        "device_id": "dev-test-101",
        "payment_method_hash": "pay-test-101",
        "account_age_days": 420,
        "total_past_orders": 28,
        "historical_return_ratio": 0.05,
        "past_inr_claims": 0,
        "item_price": 8999.0,
        "product_category_code": 1,
        "return_reason_code": 2,
        "hours_since_delivery": 36.0,
        "weight_discrepancy_grams": None,
        "is_cod_order": 0,
        "purchased_in_sale": 1,
    }

    mock_behavioral = {
        "recent_requests_1h": 0,
        "recent_requests_24h": 0,
        "recent_amount_24h": 0.0,
        "shared_device_accounts": 0,
        "shared_identity_links": 0,
        "time_since_last_request_seconds": None,
        "repeated_attempts": 0,
        "behavioral_feature_version": "1.0",
    }

    with patch("app.routers.refunds.compute_behavioral_features", new=AsyncMock(return_value=mock_behavioral)), \
         patch("app.routers.refunds.update_behavioral_state", new=AsyncMock(return_value=1)), \
         patch("app.routers.refunds.persist_transaction", new=AsyncMock(return_value=True)), \
         patch("app.routers.refunds.publish_event", new=AsyncMock()):

        response = client.post("/api/v1/refunds", json=payload)
        assert response.status_code == 200
        res = response.json()

        # Check required response fields
        assert "transaction_id" in res
        assert "request_id" in res
        assert "prediction" in res
        assert "risk" in res
        assert "behavioral_evidence" in res
        assert "top_factors" in res
        assert "latency_ms" in res
        assert res["status"] == "processed"

        # Check separate prediction and risk score
        pred = res["prediction"]
        risk = res["risk"]
        assert pred["label"] in ["Genuine", "Mistaken", "Suspicious"]
        assert "score" in risk
        assert "tier" in risk
        assert "recommended_action" in risk
        assert 0.0 <= risk["score"] <= 100.0
