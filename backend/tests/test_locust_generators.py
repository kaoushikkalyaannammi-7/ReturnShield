"""
ReturnShield Test Suite - Load Generator & Scenario Tests
===========================================================
Verifies Section 11 of the Master Build Prompt:
- Locust scenarios construct valid request payloads
- Requests NEVER include target_label (leakage prevention)
- Schema matches required fields
- Values adhere to realistic domain distributions
"""
import random
from loadtest.generators import (
    make_genuine_request,
    make_mistaken_request,
    make_suspicious_request,
)
from shared.feature_schema import FEATURE_NAMES


def test_genuine_generator():
    """Verify genuine request generator output."""
    rng = random.Random(42)
    req = make_genuine_request(rng)

    assert "target_label" not in req
    assert req["account_age_days"] >= 180
    assert req["historical_return_ratio"] < 0.20
    assert req["past_inr_claims"] == 0
    assert "customer_name" in req
    assert "item_price" in req


def test_mistaken_generator():
    """Verify mistaken request generator output."""
    rng = random.Random(42)
    req = make_mistaken_request(rng)

    assert "target_label" not in req
    assert "customer_name" in req
    assert req["product_category_code"] in [1, 2, 3, 4, 5]
    assert req["return_reason_code"] in [1, 2, 3, 4, 5]


def test_suspicious_generator():
    """Verify suspicious request generator output."""
    rng = random.Random(42)
    req = make_suspicious_request(rng)

    assert "target_label" not in req
    assert "customer_name" in req
    assert req["account_age_days"] <= 60
    assert req["historical_return_ratio"] > 0.40
