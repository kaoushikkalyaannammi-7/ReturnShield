"""
ReturnShield Risk Policy v1.0
================================
Converts model probabilities + behavioral evidence into a risk score and
recommended action. Keeps model prediction and policy decision SEPARATE.

Risk Score = base_score + behavioral_overlay, clamped to [0, 100].
base_score = 100 * (P(Suspicious) + w * P(Mistaken))
w = RISK_SCORE_W_MISTAKEN (default 0.3)

Behavioral overlay increments (documented, bounded):
  +10 if recent_requests_1h >= 3
  +8  if recent_requests_1h >= 5
  +12 if shared_identity_links >= 2
  +8  if shared_device_accounts >= 3
  +10 if repeated_attempts >= 3

Tiers:
  [0, 35)   -> Low    -> Routine processing
  [35, 65)  -> Elevated -> Additional verification
  [65, 100] -> High   -> Human review

Policy version: 1.0.0
"""
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

POLICY_VERSION = "1.0.0"


def calculate_risk_score(
    p_genuine: float,
    p_mistaken: float,
    p_suspicious: float,
    behavioral: dict,
) -> tuple[float, str, str]:
    """
    Calculate risk score, tier, and recommended action.

    Returns:
        (score: float 0-100, tier: str, recommended_action: str)
    """
    settings = get_settings()
    w = settings.RISK_SCORE_W_MISTAKEN

    # Base score from model probabilities
    base_score = 100.0 * (p_suspicious + w * p_mistaken)

    # Behavioral overlay (each increment is documented and bounded)
    overlay = 0.0

    recent_1h = behavioral.get("recent_requests_1h", 0)
    if recent_1h >= 5:
        overlay += 18.0  # Absorbs both increments
    elif recent_1h >= 3:
        overlay += 10.0

    shared_id = behavioral.get("shared_identity_links", 0)
    if shared_id >= 2:
        overlay += 12.0

    shared_dev = behavioral.get("shared_device_accounts", 0)
    if shared_dev >= 3:
        overlay += 8.0

    attempts = behavioral.get("repeated_attempts", 0)
    if attempts >= 3:
        overlay += 10.0

    # Clamp to [0, 100]
    score = min(100.0, max(0.0, base_score + overlay))
    score = round(score, 1)

    # Tier classification
    low_thresh = settings.RISK_LOW_THRESHOLD
    high_thresh = settings.RISK_HIGH_THRESHOLD

    if score < low_thresh:
        tier = "Low"
        action = "Routine processing"
    elif score < high_thresh:
        tier = "Elevated"
        action = "Additional verification"
    else:
        tier = "High"
        action = "Human review"

    return score, tier, action


def get_top_factors(feature_snapshot: dict, behavioral: dict, class_id: int) -> list[dict]:
    """
    Return top contributing factors for the analyst view.
    Based on domain knowledge and behavioral signals.
    NOT a substitute for SHAP - labeled accordingly.
    """
    factors = []

    # Model features that are domain-significant for Suspicious
    if class_id == 2:
        weight = feature_snapshot.get("weight_discrepancy_grams")
        if weight is not None and weight > 50:
            factors.append({
                "factor": "weight_discrepancy_grams",
                "value": weight,
                "note": "High weight discrepancy detected",
                "source": "model_feature",
            })

        shared = feature_snapshot.get("shared_identity_links", 0)
        if shared > 0:
            factors.append({
                "factor": "shared_identity_links",
                "value": shared,
                "note": f"{shared} accounts share identity signals with this customer",
                "source": "redis_behavioral",
            })

        hrr = feature_snapshot.get("historical_return_ratio", 0)
        if hrr > 0.4:
            factors.append({
                "factor": "historical_return_ratio",
                "value": hrr,
                "note": "Elevated historical return rate",
                "source": "model_feature",
            })

        past_inr = feature_snapshot.get("past_inr_claims", 0)
        if past_inr > 0:
            factors.append({
                "factor": "past_inr_claims",
                "value": past_inr,
                "note": f"Previous INR/empty-box claims on record",
                "source": "model_feature",
            })

    # Behavioral signals regardless of class
    recent_1h = behavioral.get("recent_requests_1h", 0)
    if recent_1h >= 3:
        factors.append({
            "factor": "recent_requests_1h",
            "value": recent_1h,
            "note": f"{recent_1h} refund requests in last 1 hour",
            "source": "redis_behavioral",
        })

    shared_dev = behavioral.get("shared_device_accounts", 0)
    if shared_dev >= 2:
        factors.append({
            "factor": "shared_device_accounts",
            "value": shared_dev,
            "note": f"Device shared with {shared_dev} other accounts",
            "source": "redis_behavioral",
        })

    factors.append({
        "factor": "note",
        "value": None,
        "note": "Factors are domain-based signals, not SHAP explanations. They indicate elevated concern, not proof of abuse.",
        "source": "policy_disclaimer",
    })

    return factors[:8]  # Limit display
