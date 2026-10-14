"""Reviews Router - authorized analyst review actions."""
from fastapi import APIRouter, HTTPException, Header
from app.schemas.schemas import ReviewRequest
from app.database import update_review
from app.config import get_settings
from typing import Optional

router = APIRouter()

@router.post("/reviews/{transaction_id}")
async def submit_review(
    transaction_id: str,
    review: ReviewRequest,
    x_admin_key: Optional[str] = Header(None),
):
    settings = get_settings()
    if x_admin_key != settings.SIM_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    updated = await update_review(transaction_id, {
        "outcome": review.outcome,
        "reviewer_id": review.reviewer_id,
        "notes": review.notes,
    })
    if not updated:
        raise HTTPException(status_code=404, detail="Transaction not found or already reviewed")
    return {"transaction_id": transaction_id, "status": "reviewed", "outcome": review.outcome}
