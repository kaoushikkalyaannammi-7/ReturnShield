"""
ReturnShield Pydantic Request/Response Schemas
"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator, model_validator
import uuid


# -----------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------

class RefundRequest(BaseModel):
    """Incoming refund request from client."""
    # UI metadata (excluded from ML features)
    customer_name: str = Field(..., min_length=1, max_length=200)
    product_name: str = Field(..., min_length=1, max_length=300)
    city: str = Field(..., min_length=1, max_length=100)

    # ML features (client-supplied; shared_identity_links computed by backend)
    account_age_days: int = Field(..., ge=0, le=36500)
    total_past_orders: int = Field(..., ge=0, le=100000)
    historical_return_ratio: float = Field(..., ge=0.0, le=1.0)
    past_inr_claims: int = Field(..., ge=0, le=1000)
    item_price: float = Field(..., gt=0.0, le=1e7)
    product_category_code: int = Field(..., ge=1, le=5)
    return_reason_code: int = Field(..., ge=1, le=5)
    hours_since_delivery: float = Field(..., ge=0.0, le=87600)
    weight_discrepancy_grams: Optional[float] = Field(None, ge=0.0, le=50000)
    # NOTE: shared_identity_links is NOT accepted from client - computed by Redis
    is_cod_order: int = Field(..., ge=0, le=1)
    purchased_in_sale: int = Field(..., ge=0, le=1)

    # Optional identifiers for behavioral tracking
    device_id: Optional[str] = Field(None, max_length=200)
    customer_id: Optional[str] = Field(None, max_length=200)
    payment_method_hash: Optional[str] = Field(None, max_length=200)

    class Config:
        json_schema_extra = {
            "example": {
                "customer_name": "Rahul Sharma",
                "product_name": "Samsung Galaxy S24",
                "city": "Mumbai",
                "account_age_days": 180,
                "total_past_orders": 12,
                "historical_return_ratio": 0.08,
                "past_inr_claims": 0,
                "item_price": 74999.0,
                "product_category_code": 1,
                "return_reason_code": 3,
                "hours_since_delivery": 6.5,
                "weight_discrepancy_grams": None,
                "is_cod_order": 0,
                "purchased_in_sale": 1,
                "device_id": "device-abc123",
                "customer_id": "cust-xyz789",
            }
        }


class ReviewRequest(BaseModel):
    """Analyst review action for a transaction."""
    reviewer_id: str = Field(..., min_length=1, max_length=100)
    outcome: str = Field(..., pattern="^(confirmed_genuine|confirmed_fraud|escalated|cleared)$")
    notes: Optional[str] = Field(None, max_length=2000)


class SimulationConfig(BaseModel):
    """Simulation configuration patch."""
    target_rps: Optional[float] = Field(None, gt=0, le=50)
    concurrency: Optional[int] = Field(None, ge=1, le=20)
    duration_seconds: Optional[int] = Field(None, ge=10, le=3600)
    scenario: Optional[str] = Field(None, pattern="^(mixed|genuine|mistaken|suspicious|coordinated)$")
    scenario_pct_genuine: Optional[float] = Field(None, ge=0, le=100)
    scenario_pct_mistaken: Optional[float] = Field(None, ge=0, le=100)
    scenario_pct_suspicious: Optional[float] = Field(None, ge=0, le=100)
    seed: Optional[int] = None


class SimulationStartRequest(BaseModel):
    """Start simulation request."""
    target_rps: float = Field(5.0, gt=0, le=50)
    concurrency: int = Field(5, ge=1, le=20)
    duration_seconds: int = Field(120, ge=10, le=3600)
    scenario: str = Field("mixed", pattern="^(mixed|genuine|mistaken|suspicious|coordinated)$")
    scenario_pct_genuine: float = Field(60.0, ge=0, le=100)
    scenario_pct_mistaken: float = Field(25.0, ge=0, le=100)
    scenario_pct_suspicious: float = Field(15.0, ge=0, le=100)
    seed: Optional[int] = None

    @model_validator(mode="after")
    def validate_scenario_pcts(self):
        if self.scenario == "mixed":
            total = self.scenario_pct_genuine + self.scenario_pct_mistaken + self.scenario_pct_suspicious
            if abs(total - 100.0) > 0.5:
                raise ValueError(f"Scenario percentages must sum to 100, got {total}")
        return self


# -----------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------

class PredictionResult(BaseModel):
    class_id: int
    label: str
    probabilities: dict[str, float]
    model_version: str


class RiskResult(BaseModel):
    score: float
    tier: str
    policy_version: str
    recommended_action: str


class BehavioralEvidence(BaseModel):
    recent_requests_1h: int = 0
    recent_requests_24h: int = 0
    recent_amount_24h: float = 0.0
    repeated_attempts: int = 0
    shared_device_accounts: int = 0
    shared_identity_links: int = 0
    time_since_last_request_seconds: Optional[float] = None
    behavioral_feature_version: str = "1.0"


class LatencyInfo(BaseModel):
    inference_ms: float
    total_ms: float


class RefundResponse(BaseModel):
    transaction_id: str
    request_id: str
    prediction: PredictionResult
    risk: RiskResult
    behavioral_evidence: BehavioralEvidence
    feature_snapshot: dict[str, Any]
    top_factors: list[dict]
    latency_ms: LatencyInfo
    status: str
    created_at: datetime


class TransactionSummary(BaseModel):
    transaction_id: str
    request_id: str
    customer_name: str
    product_name: str
    city: str
    item_price: float
    predicted_label: str
    risk_score: float
    risk_tier: str
    recommended_action: str
    review_status: str
    processing_ms: float
    created_at: datetime


class MetricsSummary(BaseModel):
    total_processed: int
    genuine_count: int
    mistaken_count: int
    suspicious_count: int
    pending_review: int
    avg_risk_score: float
    avg_latency_ms: float
    failure_rate: float
    observed_rps: float


class ModelInfo(BaseModel):
    model_version: str
    schema_hash: str
    feature_names: list[str]
    label_map: dict[str, str]
    training_timestamp: Optional[str]
    evaluation_summary: Optional[dict]
    warnings: list[str]


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    ready: bool
    model_loaded: bool
    redis_connected: bool
    mongodb_connected: bool
    details: dict[str, str]
