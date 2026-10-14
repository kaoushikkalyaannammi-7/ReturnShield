"""
ReturnShield Test Suite - Feature Schema & Contract Tests
==========================================================
Verifies Section 5 of the Master Build Prompt:
- 12 exact features in strict order
- Schema hash stability
- Category boundaries and mappings
- Nullable and Redis-computed feature contracts
"""
import pytest
from shared.feature_schema import (
    FEATURE_NAMES,
    N_FEATURES,
    LABEL_MAP,
    PRODUCT_CATEGORY_MAP,
    RETURN_REASON_MAP,
    NULLABLE_FEATURES,
    REDIS_COMPUTED_FEATURES,
    FEATURE_RANGES,
    SCHEMA_HASH,
    validate_feature_vector,
)


def test_feature_count_and_order():
    """Assert exactly 12 features in exact order specified by schema."""
    assert N_FEATURES == 12
    assert len(FEATURE_NAMES) == 12
    expected_features = [
        "account_age_days",
        "total_past_orders",
        "historical_return_ratio",
        "past_inr_claims",
        "item_price",
        "product_category_code",
        "return_reason_code",
        "hours_since_delivery",
        "weight_discrepancy_grams",
        "shared_identity_links",
        "is_cod_order",
        "purchased_in_sale",
    ]
    assert FEATURE_NAMES == expected_features


def test_schema_hash_consistency():
    """Ensure schema hash is deterministic and matches expected hash."""
    assert SCHEMA_HASH == "71b5937057f82bc0"


def test_label_mapping():
    """Verify 3-class target mapping."""
    assert LABEL_MAP[0] == "Genuine"
    assert LABEL_MAP[1] == "Mistaken"
    assert LABEL_MAP[2] == "Suspicious"
    assert len(LABEL_MAP) == 3


def test_product_category_and_return_reason_mappings():
    """Check category ranges 1..5."""
    assert len(PRODUCT_CATEGORY_MAP) == 5
    assert set(PRODUCT_CATEGORY_MAP.keys()) == {1, 2, 3, 4, 5}

    assert len(RETURN_REASON_MAP) == 5
    assert set(RETURN_REASON_MAP.keys()) == {1, 2, 3, 4, 5}


def test_nullable_and_redis_computed_spec():
    """Verify weight_discrepancy_grams is nullable and shared_identity_links is redis-computed."""
    assert NULLABLE_FEATURES == {"weight_discrepancy_grams"}
    assert REDIS_COMPUTED_FEATURES == {"shared_identity_links"}


def test_validate_feature_vector_valid():
    """Valid payload passes schema validation without errors."""
    valid_payload = {
        "account_age_days": 180,
        "total_past_orders": 12,
        "historical_return_ratio": 0.08,
        "past_inr_claims": 0,
        "item_price": 1499.0,
        "product_category_code": 1,
        "return_reason_code": 1,
        "hours_since_delivery": 48.0,
        "weight_discrepancy_grams": None,  # allowed null
        "is_cod_order": 0,
        "purchased_in_sale": 1,
    }
    errors = validate_feature_vector(valid_payload)
    assert errors == []


def test_validate_feature_vector_invalid_range():
    """Out of range inputs fail validation with descriptive errors."""
    invalid_payload = {
        "account_age_days": -10,  # below min 0
        "total_past_orders": 12,
        "historical_return_ratio": 1.5,  # above max 1.0
        "past_inr_claims": 0,
        "item_price": 0.0,  # below min 0.01
        "product_category_code": 9,  # invalid code
        "return_reason_code": 0,  # invalid code
        "hours_since_delivery": 48.0,
        "weight_discrepancy_grams": 10.0,
        "is_cod_order": 2,  # must be 0 or 1
        "purchased_in_sale": 1,
    }
    errors = validate_feature_vector(invalid_payload)
    assert len(errors) >= 5
