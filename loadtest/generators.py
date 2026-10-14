"""
ReturnShield Load Test Request Generators
==========================================
Pure Python data generators for simulation scenarios.
Does NOT import locust or gevent, allowing safe use in unit tests.
"""
import uuid
import random

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
