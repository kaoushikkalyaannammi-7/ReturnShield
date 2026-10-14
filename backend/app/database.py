"""
ReturnShield MongoDB Persistence Layer
========================================
Persists transaction decisions, audit trails, and review outcomes.
Supports real MongoDB motor client with resilient in-memory fallback.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None
_fallback_transactions: list[dict] = []


async def connect_db():
    global _client, _db
    settings = get_settings()
    url = settings.MONGODB_URL
    if settings.MONGODB_USER and settings.MONGODB_PASSWORD:
        url = f"mongodb://{settings.MONGODB_USER}:{settings.MONGODB_PASSWORD}@{settings.MONGODB_HOST}:{settings.MONGODB_PORT}"
    try:
        _client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=2000)
        # Verify server reachability before creating indexes
        await _client.admin.command("ping")
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
    except Exception as e:
        logger.warning(f"MongoDB connection failed (running in fallback persistence mode): {e}")
        _db = None


async def disconnect_db():
    global _client, _db
    if _client:
        _client.close()
    _db = None


async def check_mongodb_health() -> bool:
    if _client is None or _db is None:
        return False
    try:
        await _client.admin.command("ping")
        return True
    except Exception:
        return False


def get_db() -> Optional[AsyncIOMotorDatabase]:
    return _db


async def persist_transaction(doc: dict) -> bool:
    """Persist a transaction document. Returns True on success."""
    doc["created_at"] = datetime.now(timezone.utc)
    doc["updated_at"] = datetime.now(timezone.utc)
    doc["review_status"] = "pending" if doc.get("risk_tier") in ["High", "Elevated"] else "not_required"

    if _db is not None:
        try:
            await _db.transactions.insert_one(doc)
            return True
        except Exception as e:
            logger.error(f"Failed to persist transaction to MongoDB {doc.get('transaction_id')}: {e}")
            _fallback_transactions.append(dict(doc))
            return True
    else:
        _fallback_transactions.append(dict(doc))
        return True


async def get_transactions(
    skip: int = 0,
    limit: int = 50,
    label_filter: Optional[str] = None,
    tier_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """Get paginated transactions with optional filters."""
    if _db is not None:
        try:
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
        except Exception as e:
            logger.error(f"MongoDB query failed, falling back to memory store: {e}")

    # Fallback in-memory query
    filtered = list(_fallback_transactions)
    if label_filter:
        filtered = [d for d in filtered if d.get("predicted_label") == label_filter]
    if tier_filter:
        filtered = [d for d in filtered if d.get("risk_tier") == tier_filter]
    if search:
        s = search.lower()
        filtered = [
            d for d in filtered
            if s in str(d.get("customer_name", "")).lower()
            or s in str(d.get("product_name", "")).lower()
            or s in str(d.get("request_id", "")).lower()
            or s in str(d.get("city", "")).lower()
        ]

    total = len(filtered)
    filtered.sort(key=lambda d: d.get("created_at", datetime.min), reverse=True)
    res = [dict(d) for d in filtered[skip:skip + limit]]
    for d in res:
        d.pop("_id", None)
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        if isinstance(d.get("updated_at"), datetime):
            d["updated_at"] = d["updated_at"].isoformat()
    return res, total


async def get_transaction_by_id(transaction_id: str) -> Optional[dict]:
    if _db is not None:
        try:
            doc = await _db.transactions.find_one({"transaction_id": transaction_id}, {"_id": 0})
            if doc:
                return doc
        except Exception as e:
            logger.error(f"MongoDB find failed: {e}")

    for d in _fallback_transactions:
        if d.get("transaction_id") == transaction_id:
            res = dict(d)
            res.pop("_id", None)
            if isinstance(res.get("created_at"), datetime):
                res["created_at"] = res["created_at"].isoformat()
            if isinstance(res.get("updated_at"), datetime):
                res["updated_at"] = res["updated_at"].isoformat()
            return res
    return None


async def update_review(transaction_id: str, review: dict) -> bool:
    if _db is not None:
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
            if result.modified_count > 0:
                return True
        except Exception as e:
            logger.error(f"Failed to update review for {transaction_id}: {e}")

    for d in _fallback_transactions:
        if d.get("transaction_id") == transaction_id:
            d["review_status"] = "reviewed"
            d["review_outcome"] = review["outcome"]
            d["reviewer_id"] = review["reviewer_id"]
            d["reviewer_notes"] = review.get("notes", "")
            d["reviewed_at"] = datetime.now(timezone.utc)
            d["updated_at"] = datetime.now(timezone.utc)
            return True
    return False


async def get_metrics_summary() -> dict:
    """Aggregate metrics from MongoDB with fallback."""
    if _db is not None:
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
        except Exception as e:
            logger.error(f"MongoDB metrics aggregation error: {e}")

    # Fallback computation
    total = len(_fallback_transactions)
    if total == 0:
        return {
            "total_processed": 0, "genuine_count": 0, "mistaken_count": 0,
            "suspicious_count": 0, "pending_review": 0, "avg_risk_score": 0.0,
            "avg_latency_ms": 0.0, "failure_rate": 0.0
        }
    gen = sum(1 for d in _fallback_transactions if d.get("predicted_label") == "Genuine")
    mis = sum(1 for d in _fallback_transactions if d.get("predicted_label") == "Mistaken")
    sus = sum(1 for d in _fallback_transactions if d.get("predicted_label") == "Suspicious")
    pending = sum(1 for d in _fallback_transactions if d.get("review_status") == "pending")
    avg_score = sum(d.get("risk_score", 0) for d in _fallback_transactions) / total
    avg_lat = sum(d.get("total_latency_ms", 0) for d in _fallback_transactions) / total
    return {
        "total_processed": total,
        "genuine_count": gen,
        "mistaken_count": mis,
        "suspicious_count": sus,
        "pending_review": pending,
        "avg_risk_score": round(avg_score, 1),
        "avg_latency_ms": round(avg_lat, 1),
        "failure_rate": 0.0,
    }


async def get_metrics_timeseries(minutes: int = 60) -> list[dict]:
    """Get per-minute transaction counts for time series chart."""
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    if _db is not None:
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
            logger.error(f"MongoDB timeseries error: {e}")

    # Fallback computation
    from collections import defaultdict
    groups = defaultdict(lambda: {"count": 0, "scores": []})
    for d in _fallback_transactions:
        created = d.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except Exception:
                continue
        if isinstance(created, datetime) and created >= since:
            minute_str = created.strftime("%Y-%m-%dT%H:%M:00Z")
            label = d.get("predicted_label", "Unknown")
            key = (minute_str, label)
            groups[key]["count"] += 1
            groups[key]["scores"].append(d.get("risk_score", 0))

    res = []
    for (minute, label), val in sorted(groups.items()):
        avg_r = sum(val["scores"]) / len(val["scores"]) if val["scores"] else 0
        res.append({
            "_id": {"minute": minute, "label": label},
            "count": val["count"],
            "avg_risk": round(avg_r, 1)
        })
    return res
