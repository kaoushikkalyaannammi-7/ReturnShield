"""
ReturnShield FastAPI Backend
==============================
Entry point for the ReturnShield API service.
"""
import sys
import os
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from app.config import get_settings
from app.database import connect_db, disconnect_db, check_mongodb_health
from app.redis_features import check_redis_health
from app.model_loader import load_model, is_model_loaded, get_metadata
from app.schemas.schemas import HealthResponse, ReadinessResponse
from app.routers import refunds, transactions, metrics_router, simulation, reviews

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info("ReturnShield API starting up")

    # Connect MongoDB
    try:
        await connect_db()
        logger.info("MongoDB connected")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")

    # Load model (fails gracefully - reported in /ready)
    model_loaded = load_model(settings.MODEL_PATH, settings.MODEL_METADATA_PATH)
    if model_loaded:
        logger.info("Model loaded successfully")
    else:
        logger.warning("Model NOT loaded - /ready will report degraded")

    yield

    # Shutdown
    await disconnect_db()
    logger.info("ReturnShield API shut down")


settings = get_settings()

app = FastAPI(
    title="ReturnShield API",
    description="ML-assisted refund risk monitoring platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------
# Health / Readiness
# -----------------------------------------------------------------------

@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc)}


@app.get("/api/v1/ready", response_model=ReadinessResponse, tags=["Health"])
async def readiness():
    model_ok = is_model_loaded()
    redis_ok = await check_redis_health()
    mongo_ok = await check_mongodb_health()

    ready = model_ok and redis_ok and mongo_ok

    return {
        "ready": ready,
        "model_loaded": model_ok,
        "redis_connected": redis_ok,
        "mongodb_connected": mongo_ok,
        "details": {
            "model": "loaded" if model_ok else "NOT LOADED - inference unavailable",
            "redis": "connected" if redis_ok else "NOT CONNECTED - behavioral engine unavailable",
            "mongodb": "connected" if mongo_ok else "NOT CONNECTED - persistence unavailable",
        }
    }


@app.get("/api/v1/model/info", tags=["Model"])
async def model_info():
    if not is_model_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")
    metadata = get_metadata()
    return {
        "model_version": metadata.get("model_version"),
        "schema_hash": metadata.get("schema_hash"),
        "feature_names": metadata.get("feature_names"),
        "label_map": metadata.get("label_map"),
        "training_timestamp": metadata.get("training_timestamp"),
        "evaluation_summary": metadata.get("evaluation", {}).get("classification_report"),
        "warnings": metadata.get("warnings", []),
    }


# -----------------------------------------------------------------------
# Include routers
# -----------------------------------------------------------------------

app.include_router(refunds.router, prefix="/api/v1", tags=["Refunds"])
app.include_router(transactions.router, prefix="/api/v1", tags=["Transactions"])
app.include_router(metrics_router.router, prefix="/api/v1", tags=["Metrics"])
app.include_router(simulation.router, prefix="/api/v1", tags=["Simulation"])
app.include_router(reviews.router, prefix="/api/v1", tags=["Reviews"])


# -----------------------------------------------------------------------
# SSE Events stream
# -----------------------------------------------------------------------

@app.get("/api/v1/events", tags=["Events"])
async def events_stream():
    from app.streaming import event_generator
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
