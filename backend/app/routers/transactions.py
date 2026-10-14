"""Transactions Router."""
from fastapi import APIRouter, Query
from typing import Optional
from app.database import get_transactions, get_transaction_by_id
from fastapi import HTTPException

router = APIRouter()

@router.get("/transactions")
async def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    label: Optional[str] = Query(None, description="Filter by label: Genuine, Mistaken, Suspicious"),
    tier: Optional[str] = Query(None, description="Filter by tier: Low, Elevated, High"),
    search: Optional[str] = Query(None, description="Search customer, product, city, request_id"),
):
    docs, total = await get_transactions(
        skip=skip, limit=limit,
        label_filter=label, tier_filter=tier, search=search,
    )
    return {"transactions": docs, "total": total, "skip": skip, "limit": limit}


@router.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    doc = await get_transaction_by_id(transaction_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return doc
