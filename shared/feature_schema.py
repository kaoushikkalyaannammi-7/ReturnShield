"""
ReturnShield Shared Feature Schema
===================================
Single source of truth for ML features used across:
- ml/prepare_data.py
- ml/train.py
- ml/evaluate.py
- backend/app/services/inference.py
- loadtest/locustfile.py

DO NOT duplicate this list in any other module. Import from here.
"""
import hashlib
import json
from typing import Optional
from dataclasses import dataclass, field

# -----------------------------------------------------------------------
# Feature definitions - ORDER MATTERS (matches model training order)
# -----------------------------------------------------------------------

FEATURE_NAMES: list[str] = [
    "account_age_days",
    "total_past_orders",
    "historical_return_ratio",
    "past_inr_claims",
    "item_price",
    "product_category_code",
    "return_reason_code",
    "hours_since_delivery",
    "weight_discrepancy_grams",   # Nullable at inference time
    "shared_identity_links",      # Computed from Redis at inference; never trust client
    "is_cod_order",
    "purchased_in_sale",
]

N_FEATURES = len(FEATURE_NAMES)  # Must equal 12

# -----------------------------------------------------------------------
# Label mapping
# -----------------------------------------------------------------------

LABEL_MAP: dict[int, str] = {
    0: "Genuine",
    1: "Mistaken",
    2: "Suspicious",
}

LABEL_NAMES = [LABEL_MAP[i] for i in sorted(LABEL_MAP)]

# -----------------------------------------------------------------------
# Category mappings
# -----------------------------------------------------------------------

PRODUCT_CATEGORY_MAP: dict[int, str] = {
    1: "Electronics",
    2: "Fashion/Apparel",
    3: "Footwear",
    4: "Home",
    5: "Books",
}

RETURN_REASON_MAP: dict[int, str] = {
    1: "Wrong Size/Fit",
    2: "Not Working/Technical Issue",
    3: "Empty Box/Missing Item",
    4: "Physical Damage",
    5: "Changed Mind",
}

# -----------------------------------------------------------------------
# Nullable features (may be None/NaN at inference time)
# -----------------------------------------------------------------------

NULLABLE_FEATURES: set[str] = {"weight_discrepancy_grams"}

# -----------------------------------------------------------------------
# Features computed by Redis at inference (never trust client-supplied value)
# -----------------------------------------------------------------------

REDIS_COMPUTED_FEATURES: set[str] = {"shared_identity_links"}

# -----------------------------------------------------------------------
# Validation ranges
# -----------------------------------------------------------------------

FEATURE_RANGES: dict[str, dict] = {
    "account_age_days":         {"min": 0,    "max": 36500, "type": int},
    "total_past_orders":        {"min": 0,    "max": 100000,"type": int},
    "historical_return_ratio":  {"min": 0.0,  "max": 1.0,   "type": float},
    "past_inr_claims":          {"min": 0,    "max": 1000,  "type": int},
    "item_price":               {"min": 0.01, "max": 1e7,   "type": float},
    "product_category_code":    {"min": 1,    "max": 5,     "type": int, "values": [1,2,3,4,5]},
    "return_reason_code":       {"min": 1,    "max": 5,     "type": int, "values": [1,2,3,4,5]},
    "hours_since_delivery":     {"min": 0.0,  "max": 87600, "type": float},
    "weight_discrepancy_grams": {"min": 0.0,  "max": 50000, "type": float, "nullable": True},
    "shared_identity_links":    {"min": 0,    "max": 10000, "type": int},
    "is_cod_order":             {"min": 0,    "max": 1,     "type": int, "values": [0, 1]},
    "purchased_in_sale":        {"min": 0,    "max": 1,     "type": int, "values": [0, 1]},
}

# -----------------------------------------------------------------------
# UI-only metadata fields (NEVER passed to model)
# -----------------------------------------------------------------------

UI_METADATA_FIELDS: set[str] = {
    "request_id",
    "customer_name",
    "product_name",
    "city",
    "transaction_id",
}

# -----------------------------------------------------------------------
# Schema hash (computed once for artifact validation)
# -----------------------------------------------------------------------

def compute_schema_hash() -> str:
    """Deterministic hash of the feature contract for artifact validation."""
    schema_repr = json.dumps({
        "features": FEATURE_NAMES,
        "nullable": sorted(NULLABLE_FEATURES),
        "redis_computed": sorted(REDIS_COMPUTED_FEATURES),
        "label_map": {str(k): v for k, v in LABEL_MAP.items()},
    }, sort_keys=True)
    return hashlib.sha256(schema_repr.encode()).hexdigest()[:16]

SCHEMA_HASH = compute_schema_hash()


def validate_feature_vector(features: dict) -> list[str]:
    """
    Validate a feature dict against the schema.
    Returns a list of error strings (empty = valid).
    UI metadata fields are ignored.
    """
    errors = []

    for name in FEATURE_NAMES:
        if name in REDIS_COMPUTED_FEATURES:
            # Redis features are injected by backend; skip client validation
            continue

        value = features.get(name)

        if value is None:
            if name in NULLABLE_FEATURES:
                continue  # OK
            else:
                errors.append(f"Missing required feature: {name}")
                continue

        spec = FEATURE_RANGES.get(name, {})

        if "values" in spec and value not in spec["values"]:
            errors.append(f"{name}={value} not in allowed values {spec['values']}")
        elif "min" in spec and value < spec["min"]:
            errors.append(f"{name}={value} below minimum {spec['min']}")
        elif "max" in spec and value > spec["max"]:
            errors.append(f"{name}={value} above maximum {spec['max']}")

    # Check for unexpected feature keys (excluding UI metadata and redis-computed)
    allowed_keys = set(FEATURE_NAMES) | UI_METADATA_FIELDS
    extra = set(features.keys()) - allowed_keys
    if extra:
        errors.append(f"Unexpected feature keys: {sorted(extra)}")

    return errors


assert N_FEATURES == 12, f"Feature count mismatch: {N_FEATURES}"
