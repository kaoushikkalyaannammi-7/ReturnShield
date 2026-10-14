"""
ReturnShield Server-Sent Events Streaming
============================================
Publishes real transaction events to connected dashboard clients.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator
import redis.asyncio as aioredis
from app.redis_features import get_redis

logger = logging.getLogger(__name__)

STREAM_CHANNEL = "returnshield:events"
MAX_HISTORY = 50


async def publish_event(event_type: str, data: dict):
    """Publish an event to all SSE subscribers via Redis pub/sub."""
    try:
        r = await get_redis()
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await r.publish(STREAM_CHANNEL, message)
        # Also store in a list for reconnect history
        await r.lpush("returnshield:history", message)
        await r.ltrim("returnshield:history", 0, MAX_HISTORY - 1)
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


async def get_event_history() -> list[dict]:
    """Return recent events for reconnecting clients."""
    try:
        r = await get_redis()
        messages = await r.lrange("returnshield:history", 0, MAX_HISTORY - 1)
        return [json.loads(m) for m in reversed(messages)]
    except Exception:
        return []


async def event_generator() -> AsyncGenerator[str, None]:
    """SSE generator that subscribes to Redis pub/sub."""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(STREAM_CHANNEL)

    # Send history on connect
    history = await get_event_history()
    if history:
        yield f"event: history\ndata: {json.dumps(history)}\n\n"

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(STREAM_CHANNEL)
        await pubsub.close()
