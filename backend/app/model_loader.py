"""
ReturnShield Model Loader
===========================
Loads and validates the XGBoost model artifact.
Validates schema hash, feature names, and artifact integrity.
"""
import pickle
import json
import logging
from pathlib import Path
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

_model = None
_metadata = None
_weight_imputation_median: float = 10.9


def load_model(model_path: str, metadata_path: str) -> bool:
    """Load model and metadata. Returns True on success."""
    global _model, _metadata, _weight_imputation_median

    model_path = Path(model_path)
    metadata_path = Path(metadata_path)

    if not model_path.exists():
        logger.error(f"Model file not found: {model_path}")
        return False

    if not metadata_path.exists():
        logger.error(f"Model metadata not found: {metadata_path}")
        return False

    try:
        with open(model_path, "rb") as f:
            _model = pickle.load(f)
        logger.info(f"Model loaded from {model_path}")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return False

    try:
        with open(metadata_path, "r") as f:
            _metadata = json.load(f)
        _weight_imputation_median = _metadata.get("weight_imputation_median", 10.9)
        logger.info(f"Metadata loaded. Model version: {_metadata.get('model_version')}, Schema hash: {_metadata.get('schema_hash')}")
    except Exception as e:
        logger.error(f"Failed to load metadata: {e}")
        return False

    # Validate feature names
    from shared.feature_schema import FEATURE_NAMES, SCHEMA_HASH
    stored_features = _metadata.get("feature_names", [])
    if stored_features != FEATURE_NAMES:
        logger.error(f"Feature name mismatch! Stored: {stored_features}, Expected: {FEATURE_NAMES}")
        return False

    # Validate schema hash
    stored_hash = _metadata.get("schema_hash", "")
    if stored_hash != SCHEMA_HASH:
        logger.error(f"Schema hash mismatch! Stored: {stored_hash}, Current: {SCHEMA_HASH}")
        return False

    logger.info("Model artifact validation passed")
    return True


def is_model_loaded() -> bool:
    return _model is not None and _metadata is not None


def get_model():
    return _model


def get_metadata() -> Optional[dict]:
    return _metadata


def get_weight_median() -> float:
    return _weight_imputation_median


def predict(feature_vector: list) -> tuple[int, list[float], float]:
    """
    Run inference on a feature vector.
    Returns (class_id, probabilities_list, inference_ms).
    feature_vector must be in FEATURE_NAMES order.
    """
    import time
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    X = np.array(feature_vector, dtype=np.float64).reshape(1, -1)
    t0 = time.perf_counter()
    proba = _model.predict_proba(X)[0]
    inference_ms = (time.perf_counter() - t0) * 1000

    class_id = int(np.argmax(proba))
    return class_id, proba.tolist(), inference_ms
