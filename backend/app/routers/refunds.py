"""Refunds Router - core transaction processing endpoint."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import time
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.schemas.schemas import RefundRequest, RefundResponse
from app.model_loader import is_model_loaded, predict, get_metadata, get_weight_median
from app.redis_features import (
    compute_behavioral_features, update_behavioral_state,
    check_idempotency, set_idempotency, persist_behavioral_snapshot
)
from app.risk_policy import calculate_risk_score, get_top_factors, POLICY_VERSION
from app.database import persist_transaction
from app.streaming import publish_event
from shared.feature_schema import FEATURE_NAMES, LABEL_MAP

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/refunds", response_model=RefundResponse)
async def submit_refund(
    request: RefundRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Submit a refund request for ML-assisted risk assessment.

    Processing flow:
    1. Validate payload (Pydantic)
    2. Check idempotency key
    3. Compute Redis behavioral features (authoritative)
    4. Build model feature vector from shared schema
    5. Run XGBoost inference
    6. Apply versioned risk policy
    7. Persist to MongoDB
    8. Publish SSE event
    9. Return structured response
    """
    request_start = time.perf_counter()

    # 1. Model readiness check
    if not is_model_loaded():
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Check /api/v1/ready for service status."
        )

    # 2. Idempotency check
    if idempotency_key:
        cached = await check_idempotency(idempotency_key)
        if cached:
            logger.info(f"Idempotent response for key {idempotency_key}")
            return cached

    # 3. Generate transaction ID
    transaction_id = str(uuid.uuid4())
    request_id = f"REF-{int(time.time() * 1000) % 100000:05d}"

    # 4. Compute Redis behavioral features (AUTHORITATIVE - never trust client)
    customer_id = request.customer_id or f"cust-{hash(request.customer_name) % 1000000:06d}"
    device_id = request.device_id
    payment_hash = request.payment_method_hash

    behavioral = await compute_behavioral_features(
        customer_id=customer_id,
        device_id=device_id,
        item_price=request.item_price,
        payment_method_hash=payment_hash,
    )

    # 5. Build model feature vector in exact schema order
    weight_median = get_weight_median()
    weight_disc = request.weight_discrepancy_grams
    weight_disc_imputed = weight_disc if weight_disc is not None else weight_median

    feature_values = [
        float(request.account_age_days),
        float(request.total_past_orders),
        float(request.historical_return_ratio),
        float(request.past_inr_claims),
        float(request.item_price),
        float(request.product_category_code),
        float(request.return_reason_code),
        float(request.hours_since_delivery),
        float(weight_disc_imputed),                    # nullable, imputed
        float(behavioral["shared_identity_links"]),    # Redis-computed, authoritative
        float(request.is_cod_order),
        float(request.purchased_in_sale),
    ]

    assert len(feature_values) == len(FEATURE_NAMES), "Feature vector length mismatch"

    feature_snapshot = {name: val for name, val in zip(FEATURE_NAMES, feature_values)}
    feature_snapshot["weight_discrepancy_grams_original"] = weight_disc  # Preserve null indicator

    # 6. Run inference
    class_id, proba, inference_ms = predict(feature_values)
    predicted_label = LABEL_MAP[class_id]
    metadata = get_metadata()

    # 7. Apply risk policy (separate from prediction)
    risk_score, risk_tier, recommended_action = calculate_risk_score(
        p_genuine=proba[0],
        p_mistaken=proba[1],
        p_suspicious=proba[2],
        behavioral=behavioral,
    )

    # 8. Get top factors
    top_factors = get_top_factors(feature_snapshot, behavioral, class_id)

    total_ms = (time.perf_counter() - request_start) * 1000

    # 9. Update behavioral state AFTER computing features for this request
    repeated_attempts = await update_behavioral_state(
        customer_id=customer_id,
        device_id=device_id,
        item_price=request.item_price,
        payment_method_hash=payment_hash,
        transaction_id=transaction_id,
    )
    behavioral["repeated_attempts"] = repeated_attempts

    # 10. Persist to MongoDB
    doc = {
        "transaction_id": transaction_id,
        "request_id": request_id,
        "customer_name": request.customer_name,
        "product_name": request.product_name,
        "city": request.city,
        "customer_id": customer_id,
        "device_id": device_id,
        "item_price": request.item_price,
        "product_category_code": request.product_category_code,
        "return_reason_code": request.return_reason_code,
        "is_cod_order": request.is_cod_order,
        "purchased_in_sale": request.purchased_in_sale,
        "feature_snapshot": feature_snapshot,
        "behavioral_evidence": behavioral,
        "predicted_class_id": class_id,
        "predicted_label": predicted_label,
        "probabilities": {LABEL_MAP[i]: round(p, 4) for i, p in enumerate(proba)},
        "model_version": metadata.get("model_version", "unknown"),
        "schema_hash": metadata.get("schema_hash", "unknown"),
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "recommended_action": recommended_action,
        "policy_version": POLICY_VERSION,
        "inference_latency_ms": round(inference_ms, 2),
        "total_latency_ms": round(total_ms, 2),
        "status": "processed",
        "weight_discrepancy_was_null": weight_disc is None,
    }

    persisted = await persist_transaction(doc)
    if not persisted:
        raise HTTPException(status_code=500, detail="Failed to persist transaction. Request not committed.")

    # Store idempotency
    response_data = {
        "transaction_id": transaction_id,
        "request_id": request_id,
        "prediction": {
            "class_id": class_id,
            "label": predicted_label,
            "probabilities": {LABEL_MAP[i]: round(p, 4) for i, p in enumerate(proba)},
            "model_version": metadata.get("model_version", "unknown"),
        },
        "risk": {
            "score": risk_score,
            "tier": risk_tier,
            "policy_version": POLICY_VERSION,
            "recommended_action": recommended_action,
        },
        "behavioral_evidence": behavioral,
        "feature_snapshot": feature_snapshot,
        "top_factors": top_factors,
        "latency_ms": {
            "inference_ms": round(inference_ms, 2),
            "total_ms": round(total_ms, 2),
        },
        "status": "processed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if idempotency_key:
        await set_idempotency(idempotency_key, response_data)

    # Publish SSE event
    await publish_event("transaction", {
        "transaction_id": transaction_id,
        "request_id": request_id,
        "customer_name": request.customer_name,
        "product_name": request.product_name,
        "city": request.city,
        "item_price": request.item_price,
        "predicted_label": predicted_label,
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "recommended_action": recommended_action,
        "inference_ms": round(inference_ms, 2),
        "total_ms": round(total_ms, 2),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(
        f"Transaction {transaction_id}: label={predicted_label}, score={risk_score}, "
        f"tier={risk_tier}, inference={inference_ms:.1f}ms, total={total_ms:.1f}ms"
    )

    return response_data
