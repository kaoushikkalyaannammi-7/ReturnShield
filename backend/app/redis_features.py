"""
ReturnShield Redis Behavioral Engine
=======================================
Computes real-time behavioral signals using Redis.
All counters are authoritative - client values are never trusted.

Key prefixes:
  rs:req:{customer_id}    - sorted set of request timestamps (24h window)
  rs:amt:{customer_id}    - sorted set of amounts with timestamps
  rs:dev:{device_id}      - set of customer_ids using this device
  rs:idn:{customer_id}    - set of linked identity keys
  rs:idem:{idem_key}      - idempotency record
  rs:attempt:{customer_id}:{product}  - repeated attempt counter
"""
import time
import json
import logging
import asyncio
from typing import Optional
import redis.asyncio as aioredis
from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
    return _redis_client


async def check_redis_health() -> bool:
    try:
        r = await get_redis()
        res = await asyncio.wait_for(r.ping(), timeout=2.0)
        return res is True or res == "PONG"
    except Exception:
        return False


WINDOW_1H = 3600
WINDOW_24H = 86400


async def compute_behavioral_features(
    customer_id: str,
    device_id: Optional[str],
    item_price: float,
    payment_method_hash: Optional[str] = None,
) -> dict:
    """
    Compute all behavioral signals for a refund request.
    Returns a dict with all behavioral fields including shared_identity_links.
    This is the AUTHORITATIVE source for shared_identity_links.
    """
    r = await get_redis()
    now = time.time()
    settings = get_settings()

    customer_key = f"rs:req:{customer_id}"
    amount_key = f"rs:amt:{customer_id}"

    # Trim expired entries atomically
    pipe = r.pipeline()
    pipe.zremrangebyscore(customer_key, 0, now - WINDOW_24H)
    pipe.zremrangebyscore(amount_key, 0, now - WINDOW_24H)
    await pipe.execute()

    # Count requests in windows
    pipe = r.pipeline()
    pipe.zcount(customer_key, now - WINDOW_1H, "+inf")
    pipe.zcount(customer_key, now - WINDOW_24H, "+inf")
    pipe.zrangebyscore(amount_key, now - WINDOW_24H, "+inf", withscores=True)
    pipe.zrevrangebyscore(customer_key, "+inf", "-inf", start=0, count=1, withscores=True)
    results = await pipe.execute()

    recent_requests_1h = int(results[0])
    recent_requests_24h = int(results[1])
    amount_entries = results[2]  # [(member, score)] where member is the amount
    last_request_entries = results[3]

    recent_amount_24h = sum(float(m) for m, _s in amount_entries)

    # Time since last request
    time_since_last = None
    if last_request_entries:
        last_ts = float(last_request_entries[0][1])
        time_since_last = now - last_ts

    # Shared device accounts
    shared_device_accounts = 0
    if device_id:
        device_key = f"rs:dev:{device_id}"
        shared_device_accounts = max(0, await r.scard(device_key) - 1)  # exclude self

    # Shared identity links (authoritative value for model feature)
    identity_key = f"rs:idn:{customer_id}"
    shared_identity_links = await r.scard(identity_key)

    # Payment method linking
    if payment_method_hash:
        pay_key = f"rs:pay:{payment_method_hash}"
        pay_customers = await r.smembers(pay_key)
        if customer_id not in pay_customers:
            # New linked accounts count as identity links
            shared_identity_links = max(shared_identity_links, len(pay_customers))

    return {
        "recent_requests_1h": recent_requests_1h,
        "recent_requests_24h": recent_requests_24h,
        "recent_amount_24h": recent_amount_24h,
        "shared_device_accounts": shared_device_accounts,
        "shared_identity_links": int(shared_identity_links),
        "time_since_last_request_seconds": time_since_last,
        "repeated_attempts": 0,  # Updated in update_behavioral_state
        "behavioral_feature_version": "1.0",
    }


async def update_behavioral_state(
    customer_id: str,
    device_id: Optional[str],
    item_price: float,
    payment_method_hash: Optional[str],
    transaction_id: str,
) -> int:
    """
    Record this transaction in Redis behavioral state.
    Returns repeated_attempts count for this customer.
    """
    r = await get_redis()
    now = time.time()
    settings = get_settings()
    ttl = settings.BEHAVIORAL_WINDOW_SECONDS

    pipe = r.pipeline()

    # Record request timestamp
    customer_key = f"rs:req:{customer_id}"
    pipe.zadd(customer_key, {transaction_id: now})
    pipe.expire(customer_key, ttl)

    # Record amount
    amount_key = f"rs:amt:{customer_id}"
    pipe.zadd(amount_key, {f"{item_price}:{transaction_id}": now})
    pipe.expire(amount_key, ttl)

    # Device tracking
    if device_id:
        device_key = f"rs:dev:{device_id}"
        pipe.sadd(device_key, customer_id)
        pipe.expire(device_key, ttl)

        # Link all accounts sharing this device as identity links
        existing_accounts = await r.smembers(device_key)
        for other_cust in existing_accounts:
            if other_cust != customer_id:
                pipe.sadd(f"rs:idn:{customer_id}", other_cust)
                pipe.sadd(f"rs:idn:{other_cust}", customer_id)
                pipe.expire(f"rs:idn:{customer_id}", ttl)
                pipe.expire(f"rs:idn:{other_cust}", ttl)

    # Payment method linking
    if payment_method_hash:
        pay_key = f"rs:pay:{payment_method_hash}"
        existing_pay = await r.smembers(pay_key)
        for other_cust in existing_pay:
            if other_cust != customer_id:
                pipe.sadd(f"rs:idn:{customer_id}", other_cust)
                pipe.sadd(f"rs:idn:{other_cust}", customer_id)
        pipe.sadd(pay_key, customer_id)
        pipe.expire(pay_key, ttl)

    await pipe.execute()

    # Repeated attempt count
    attempt_key = f"rs:attempt:{customer_id}"
    attempts = await r.incr(attempt_key)
    await r.expire(attempt_key, WINDOW_24H)

    return int(attempts)


async def check_idempotency(idempotency_key: str) -> Optional[dict]:
    """Check if this idempotency key was already processed. Returns stored result or None."""
    r = await get_redis()
    idem_key = f"rs:idem:{idempotency_key}"
    value = await r.get(idem_key)
    if value:
        return json.loads(value)
    return None


async def set_idempotency(idempotency_key: str, result: dict, ttl: int = 3600):
    """Store idempotency result."""
    r = await get_redis()
    idem_key = f"rs:idem:{idempotency_key}"
    await r.setex(idem_key, ttl, json.dumps(result))


async def persist_behavioral_snapshot(transaction_id: str, snapshot: dict, ttl: int = 86400):
    """Store the exact behavioral snapshot used for this decision."""
    r = await get_redis()
    key = f"rs:snap:{transaction_id}"
    await r.setex(key, ttl, json.dumps(snapshot))
