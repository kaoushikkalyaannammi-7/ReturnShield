"""
ReturnShield Test Suite - Risk Policy & Decision Engine Tests
==============================================================
Verifies Section 7 of the Master Build Prompt:
- Separation of Model Prediction vs Behavioral Evidence vs Policy Decision
- Weighted formula: base_score = 100 * (P(Suspicious) + w * P(Mistaken))
- Documented overlay increments
- Strict clamping to [0, 100]
- Tier assignments: Low, Elevated, High
- Top factors generation and safety disclaimer
"""
import pytest
from app.risk_policy import calculate_risk_score, get_top_factors, POLICY_VERSION


def test_pure_genuine_low_risk():
    """High P(Genuine) with zero behavioral red flags yields Low tier routine processing."""
    behavioral = {
        "recent_requests_1h": 0,
        "shared_identity_links": 0,
        "shared_device_accounts": 0,
        "repeated_attempts": 0,
    }
    score, tier, action = calculate_risk_score(
        p_genuine=0.98,
        p_mistaken=0.01,
        p_suspicious=0.01,
        behavioral=behavioral,
    )
    assert 0.0 <= score < 35.0
    assert tier == "Low"
    assert action == "Routine processing"


def test_suspicious_high_risk():
    """High P(Suspicious) yields High tier human review."""
    behavioral = {
        "recent_requests_1h": 1,
        "shared_identity_links": 0,
        "shared_device_accounts": 0,
        "repeated_attempts": 0,
    }
    score, tier, action = calculate_risk_score(
        p_genuine=0.05,
        p_mistaken=0.10,
        p_suspicious=0.85,
        behavioral=behavioral,
    )
    assert score >= 65.0
    assert tier == "High"
    assert action == "Human review"


def test_elevated_tier_with_behavioral_overlay():
    """Genuine model prediction with heavy identity links and velocity pushes score into Elevated/High tier."""
    behavioral = {
        "recent_requests_1h": 4,         # +10
        "shared_identity_links": 3,      # +12
        "shared_device_accounts": 3,     # +8
        "repeated_attempts": 1,
    }
    # base_score = 100 * (0.05 + 0.3 * 0.20) = 100 * 0.11 = 11.0
    # overlay = 10 + 12 + 8 = 30.0
    # total score = 41.0 -> Elevated
    score, tier, action = calculate_risk_score(
        p_genuine=0.75,
        p_mistaken=0.20,
        p_suspicious=0.05,
        behavioral=behavioral,
    )
    assert 35.0 <= score < 65.0
    assert tier == "Elevated"
    assert action == "Additional verification"


def test_risk_score_clamping():
    """Verify that score never exceeds 100 even with extreme inputs."""
    behavioral = {
        "recent_requests_1h": 10,
        "shared_identity_links": 10,
        "shared_device_accounts": 10,
        "repeated_attempts": 10,
    }
    score, tier, action = calculate_risk_score(
        p_genuine=0.0,
        p_mistaken=0.5,
        p_suspicious=0.9,
        behavioral=behavioral,
    )
    assert score == 100.0
    assert tier == "High"


def test_top_factors_includes_disclaimer_and_signals():
    """Verify top factors lists key behavioral signals and includes mandatory disclaimer."""
    feature_snapshot = {
        "weight_discrepancy_grams": 250.0,
        "shared_identity_links": 2,
        "historical_return_ratio": 0.45,
        "past_inr_claims": 2,
    }
    behavioral = {
        "recent_requests_1h": 4,
        "shared_device_accounts": 2,
    }
    factors = get_top_factors(feature_snapshot, behavioral, class_id=2)
    assert len(factors) > 0

    factor_names = [f["factor"] for f in factors]
    assert "weight_discrepancy_grams" in factor_names
    assert "shared_identity_links" in factor_names
    assert "note" in factor_names  # policy disclaimer
    disclaimer = next(f for f in factors if f["factor"] == "note")
    assert "disclaimer" in disclaimer["source"]
