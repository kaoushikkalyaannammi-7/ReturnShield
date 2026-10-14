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

# Generator functions and shared pools
try:
    from loadtest.generators import (
        SHARED_DEVICES, SHARED_PAYMENT, CITIES, FIRST_NAMES, LAST_NAMES, PRODUCTS,
        random_name, make_genuine_request, make_mistaken_request,
        make_suspicious_request, make_coordinated_request
    )
except ImportError:
    from generators import (
        SHARED_DEVICES, SHARED_PAYMENT, CITIES, FIRST_NAMES, LAST_NAMES, PRODUCTS,
        random_name, make_genuine_request, make_mistaken_request,
        make_suspicious_request, make_coordinated_request
    )



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
