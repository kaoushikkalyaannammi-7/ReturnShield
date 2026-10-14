"""
ReturnShield MongoDB Persistence Layer
========================================
Persists transaction decisions, audit trails, and review outcomes.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_db():
    global _client, _db
    settings = get_settings()
    url = settings.MONGODB_URL
    if settings.MONGODB_USER and settings.MONGODB_PASSWORD:
        url = f"mongodb://{settings.MONGODB_USER}:{settings.MONGODB_PASSWORD}@{settings.MONGODB_HOST}:{settings.MONGODB_PORT}"
    _client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
    _db = _client[settings.MONGODB_DB]
    # Create indexes
    await _db.transactions.create_index("transaction_id", unique=True)
    await _db.transactions.create_index("created_at")
    await _db.transactions.create_index("predicted_label")
    await _db.transactions.create_index("customer_id")
    await _db.transactions.create_index("device_id")
    await _db.transactions.create_index("risk_tier")
    await _db.transactions.create_index("review_status")
    logger.info(f"MongoDB connected: {settings.MONGODB_URL}/{settings.MONGODB_DB}")


async def disconnect_db():
    global _client
    if _client:
        _client.close()


async def check_mongodb_health() -> bool:
    try:
        await _db.command("ping")
        return True
    except Exception:
        return False


def get_db() -> AsyncIOMotorDatabase:
    return _db


async def persist_transaction(doc: dict) -> bool:
    """Persist a transaction document. Returns True on success."""
    try:
        doc["created_at"] = datetime.now(timezone.utc)
        doc["updated_at"] = datetime.now(timezone.utc)
        doc["review_status"] = "pending" if doc.get("risk_tier") in ["High", "Elevated"] else "not_required"
        await _db.transactions.insert_one(doc)
        return True
    except Exception as e:
        logger.error(f"Failed to persist transaction {doc.get('transaction_id')}: {e}")
        return False


async def get_transactions(
    skip: int = 0,
    limit: int = 50,
    label_filter: Optional[str] = None,
    tier_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """Get paginated transactions with optional filters."""
    query: dict[str, Any] = {}

    if label_filter:
        query["predicted_label"] = label_filter
    if tier_filter:
        query["risk_tier"] = tier_filter
    if search:
        query["$or"] = [
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"product_name": {"$regex": search, "$options": "i"}},
            {"request_id": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]

    total = await _db.transactions.count_documents(query)
    cursor = _db.transactions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return docs, total


async def get_transaction_by_id(transaction_id: str) -> Optional[dict]:
    doc = await _db.transactions.find_one({"transaction_id": transaction_id}, {"_id": 0})
    return doc


async def update_review(transaction_id: str, review: dict) -> bool:
    try:
        result = await _db.transactions.update_one(
            {"transaction_id": transaction_id},
            {"$set": {
                "review_status": "reviewed",
                "review_outcome": review["outcome"],
                "reviewer_id": review["reviewer_id"],
                "reviewer_notes": review.get("notes", ""),
                "reviewed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Failed to update review for {transaction_id}: {e}")
        return False


async def get_metrics_summary() -> dict:
    """Aggregate metrics from MongoDB."""
    try:
        pipeline = [
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "genuine": {"$sum": {"$cond": [{"$eq": ["$predicted_label", "Genuine"]}, 1, 0]}},
                "mistaken": {"$sum": {"$cond": [{"$eq": ["$predicted_label", "Mistaken"]}, 1, 0]}},
                "suspicious": {"$sum": {"$cond": [{"$eq": ["$predicted_label", "Suspicious"]}, 1, 0]}},
                "pending_review": {"$sum": {"$cond": [{"$eq": ["$review_status", "pending"]}, 1, 0]}},
                "avg_risk_score": {"$avg": "$risk_score"},
                "avg_latency": {"$avg": "$total_latency_ms"},
                "failures": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
            }}
        ]
        result = await _db.transactions.aggregate(pipeline).to_list(1)
        if result:
            r = result[0]
            total = r["total"]
            return {
                "total_processed": total,
                "genuine_count": r["genuine"],
                "mistaken_count": r["mistaken"],
                "suspicious_count": r["suspicious"],
                "pending_review": r["pending_review"],
                "avg_risk_score": round(r["avg_risk_score"] or 0, 1),
                "avg_latency_ms": round(r["avg_latency"] or 0, 1),
                "failure_rate": round(r["failures"] / max(total, 1), 4),
            }
        return {"total_processed": 0, "genuine_count": 0, "mistaken_count": 0,
                "suspicious_count": 0, "pending_review": 0, "avg_risk_score": 0,
                "avg_latency_ms": 0, "failure_rate": 0}
    except Exception as e:
        logger.error(f"Metrics aggregation error: {e}")
        return {}


async def get_metrics_timeseries(minutes: int = 60) -> list[dict]:
    """Get per-minute transaction counts for time series chart."""
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    try:
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": {
                    "minute": {"$dateToString": {
                        "format": "%Y-%m-%dT%H:%M:00Z",
                        "date": {"$dateTrunc": {"date": "$created_at", "unit": "minute"}}
                    }},
                    "label": "$predicted_label",
                },
                "count": {"$sum": 1},
                "avg_risk": {"$avg": "$risk_score"},
            }},
            {"$sort": {"_id.minute": 1}},
        ]
        results = await _db.transactions.aggregate(pipeline).to_list(10000)
        return results
    except Exception as e:
        logger.error(f"Timeseries error: {e}")
        return []
