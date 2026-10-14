"""
ReturnShield Locust Load Generator
=====================================
Sends real HTTP requests to FastAPI backend.
Scenario intent determines request construction, never sent as label.

Scenarios:
  mixed        - configurable % genuine/mistaken/suspicious
  genuine      - only genuine-profile requests
  mistaken     - only mistaken-profile requests
  suspicious   - only suspicious-profile requests
  coordinated  - multiple customers sharing device/payment method

Environment variables:
  RS_SCENARIO             - scenario name (default: mixed)
  RS_PCT_GENUINE          - % genuine in mixed mode (default: 60)
  RS_PCT_MISTAKEN         - % mistaken in mixed mode (default: 25)
  RS_PCT_SUSPICIOUS       - % suspicious in mixed mode (default: 15)
  RS_SEED                 - random seed (default: 42)
  RS_TARGET_URL           - backend URL (default: http://localhost:8000)
"""
import os
import random
import uuid
import time
import numpy as np
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner

# Configuration from environment
SCENARIO = os.environ.get("RS_SCENARIO", "mixed")
PCT_GENUINE = float(os.environ.get("RS_PCT_GENUINE", "60"))
PCT_MISTAKEN = float(os.environ.get("RS_PCT_MISTAKEN", "25"))
PCT_SUSPICIOUS = float(os.environ.get("RS_PCT_SUSPICIOUS", "15"))
SEED = int(os.environ.get("RS_SEED", "42"))

# Shared device pool for coordinated scenario
SHARED_DEVICES = [f"device-shared-{i:03d}" for i in range(5)]
SHARED_PAYMENT = [f"pay-hash-{i:03d}" for i in range(3)]

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Jaipur"]
FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sunita", "Vikram", "Neha", "Suresh", "Kavita"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Verma", "Gupta", "Joshi", "Nair"]
PRODUCTS = ["Samsung Galaxy", "Nike Shoes", "Cotton Kurti", "Air Purifier", "Python Cookbook"]


def random_name(rng):
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def make_genuine_request(rng) -> dict:
    """Construct a request with genuine-profile characteristics."""
    return {
        "customer_name": random_name(rng),
        "product_name": rng.choice(PRODUCTS),
        "city": rng.choice(CITIES),
        "account_age_days": int(rng.randint(180, 1499)),
        "total_past_orders": int(rng.randint(10, 79)),
        "historical_return_ratio": round(float(rng.uniform(0.02, 0.15)), 3),
        "past_inr_claims": 0,
        "item_price": round(float(rng.uniform(299, 15000)), 2),
        "product_category_code": int(rng.randint(1, 5)),
        "return_reason_code": int(rng.choice([1, 4, 5])),  # benign reasons
        "hours_since_delivery": round(float(rng.uniform(24, 120)), 1),
        "weight_discrepancy_grams": None,
        "is_cod_order": 0,
        "purchased_in_sale": int(rng.randint(0, 1)),
        "device_id": f"device-{uuid.uuid4().hex[:8]}",
        "customer_id": f"cust-gen-{uuid.uuid4().hex[:8]}",
    }


def make_mistaken_request(rng) -> dict:
    """Construct a request with mistaken/honest-mistake characteristics."""
    return {
        "customer_name": random_name(rng),
        "product_name": rng.choice(PRODUCTS),
        "city": rng.choice(CITIES),
        "account_age_days": int(rng.randint(30, 600)),
        "total_past_orders": int(rng.randint(3, 30)),
        "historical_return_ratio": round(float(rng.uniform(0.10, 0.35)), 3),
        "past_inr_claims": int(rng.choice([0, 0, 1])),
        "item_price": round(float(rng.uniform(500, 25000)), 2),
        "product_category_code": int(rng.randint(1, 5)),
        "return_reason_code": int(rng.choice([1, 2, 4])),
        "hours_since_delivery": round(float(rng.uniform(12, 72)), 1),
        "weight_discrepancy_grams": round(float(rng.uniform(5, 40)), 1),
        "is_cod_order": int(rng.randint(0, 1)),
        "purchased_in_sale": int(rng.randint(0, 1)),
        "device_id": f"device-{uuid.uuid4().hex[:8]}",
        "customer_id": f"cust-mis-{uuid.uuid4().hex[:8]}",
    }


def make_suspicious_request(rng) -> dict:
    """Construct a request with suspicious-profile characteristics."""
    return {
        "customer_name": random_name(rng),
        "product_name": rng.choice(PRODUCTS),
        "city": rng.choice(CITIES),
        "account_age_days": int(rng.randint(1, 90)),
        "total_past_orders": int(rng.randint(1, 10)),
        "historical_return_ratio": round(float(rng.uniform(0.5, 0.95)), 3),
        "past_inr_claims": int(rng.choice([1, 2, 3])),
        "item_price": round(float(rng.uniform(5000, 85000)), 2),
        "product_category_code": int(rng.choice([1, 3])),  # Electronics, Footwear
        "return_reason_code": int(rng.choice([3, 2])),  # Empty box, Not working
        "hours_since_delivery": round(float(rng.uniform(1, 24)), 1),
        "weight_discrepancy_grams": round(float(rng.uniform(100, 599)), 1),
        "is_cod_order": 1,
        "purchased_in_sale": 1,
        "device_id": rng.choice(SHARED_DEVICES),  # Shared devices
        "customer_id": f"cust-sus-{uuid.uuid4().hex[:8]}",
        "payment_method_hash": rng.choice(SHARED_PAYMENT),
    }


def make_coordinated_request(rng) -> dict:
    """Multiple customers sharing device/payment identifiers."""
    device = rng.choice(SHARED_DEVICES)
    payment = rng.choice(SHARED_PAYMENT)
    return {
        "customer_name": random_name(rng),
        "product_name": rng.choice(PRODUCTS),
        "city": rng.choice(CITIES),
        "account_age_days": int(rng.randint(1, 120)),
        "total_past_orders": int(rng.randint(1, 15)),
        "historical_return_ratio": round(float(rng.uniform(0.3, 0.8)), 3),
        "past_inr_claims": int(rng.choice([0, 1, 2])),
        "item_price": round(float(rng.uniform(3000, 60000)), 2),
        "product_category_code": 1,
        "return_reason_code": 3,
        "hours_since_delivery": round(float(rng.uniform(2, 48)), 1),
        "weight_discrepancy_grams": round(float(rng.uniform(20, 200)), 1),
        "is_cod_order": 1,
        "purchased_in_sale": int(rng.randint(0, 1)),
        "device_id": device,
        "customer_id": f"cust-coord-{uuid.uuid4().hex[:6]}",
        "payment_method_hash": payment,
    }


def pick_scenario_request(rng) -> dict:
    """Pick request type based on configured scenario."""
    if SCENARIO == "genuine":
        return make_genuine_request(rng)
    elif SCENARIO == "mistaken":
        return make_mistaken_request(rng)
    elif SCENARIO == "suspicious":
        return make_suspicious_request(rng)
    elif SCENARIO == "coordinated":
        return make_coordinated_request(rng)
    else:  # mixed
        roll = rng.uniform(0, 100)
        if roll < PCT_GENUINE:
            return make_genuine_request(rng)
        elif roll < PCT_GENUINE + PCT_MISTAKEN:
            return make_mistaken_request(rng)
        else:
            return make_suspicious_request(rng)


class ReturnShieldUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        # Each user gets its own RNG seeded uniquely
        self.rng = random.Random(SEED + id(self) % 10000)

    @task
    def submit_refund(self):
        payload = pick_scenario_request(self.rng)
        idempotency_key = str(uuid.uuid4())

        with self.client.post(
            "/api/v1/refunds",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 503:
                resp.failure(f"Service unavailable: {resp.text[:100]}")
            elif resp.status_code == 422:
                resp.failure(f"Validation error: {resp.text[:200]}")
            else:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:100]}")
