"""
ReturnShield Test Suite - ML Inference & Model Loader Tests
============================================================
Verifies Section 6 of the Master Build Prompt:
- Model artifact loading and schema hash verification
- Real model inference execution
- Valid output shape: 3 classes, probabilities sum to 1.0
- Sub-50ms inference latency constraint
"""
import pytest
import numpy as np
from app.model_loader import (
    load_model,
    is_model_loaded,
    predict,
    get_metadata,
    get_weight_median,
)
from shared.feature_schema import FEATURE_NAMES, SCHEMA_HASH, LABEL_MAP


@pytest.fixture(scope="module", autouse=True)
def setup_model():
    """Ensure the trained model artifact is loaded for testing."""
    success = load_model("ml/artifacts/model.pkl", "ml/artifacts/model_metadata.json")
    assert success is True, "Failed to load model artifacts"


def test_model_loaded_and_metadata_verified():
    """Check metadata fields, schema hash, and feature list."""
    assert is_model_loaded() is True
    metadata = get_metadata()
    assert metadata is not None
    assert metadata["model_version"] == "1.0.0"
    assert metadata["schema_hash"] == SCHEMA_HASH
    assert metadata["feature_names"] == FEATURE_NAMES
    assert metadata["n_features"] == 12
    assert get_weight_median() > 0.0


def test_predict_genuine_profile():
    """Test inference on a low-risk/genuine feature vector."""
    # account_age=500, orders=25, hrr=0.04, inr=0, price=1200, cat=1, reason=1, hours=36, weight=10.9, shared=0, cod=0, sale=1
    sample = [500.0, 25.0, 0.04, 0.0, 1200.0, 1.0, 1.0, 36.0, 10.9, 0.0, 0.0, 1.0]
    class_id, proba, latency_ms = predict(sample)

    assert class_id in {0, 1, 2}
    assert len(proba) == 3
    assert abs(sum(proba) - 1.0) < 1e-4
    assert latency_ms < 50.0  # Master prompt latency target (<50ms)
    assert class_id == 0  # Should be Genuine


def test_predict_suspicious_profile():
    """Test inference on a high-risk/suspicious feature vector."""
    # young account, high hrr, high inr claims, high weight discrepancy, multiple identity links
    sample = [2.0, 1.0, 0.85, 3.0, 45000.0, 1.0, 3.0, 4.0, 350.0, 4.0, 1.0, 0.0]
    class_id, proba, latency_ms = predict(sample)

    assert class_id in {0, 1, 2}
    assert len(proba) == 3
    assert abs(sum(proba) - 1.0) < 1e-4
    assert class_id == 2  # Should be Suspicious
    assert proba[2] > 0.50
