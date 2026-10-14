"""ReturnShield Backend Configuration"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ReturnShield"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "changeme-in-production"

    # MongoDB
    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB: str = "returnshield"
    MONGODB_USER: str = ""
    MONGODB_PASSWORD: str = ""

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "returnshield_redis_secret"
    REDIS_DB: int = 0

    # Model artifacts
    MODEL_PATH: str = "/app/ml/artifacts/model.pkl"
    MODEL_METADATA_PATH: str = "/app/ml/artifacts/model_metadata.json"
    SCHEMA_HASH_EXPECTED: str = ""  # If set, validate against artifact

    # Risk policy
    POLICY_VERSION: str = "1.0.0"
    RISK_SCORE_W_MISTAKEN: float = 0.3  # Weight for P(Mistaken) in base score
    RISK_LOW_THRESHOLD: float = 35.0
    RISK_HIGH_THRESHOLD: float = 65.0

    # Simulation caps
    SIM_MAX_RPS: int = 50
    SIM_MAX_USERS: int = 20
    SIM_MAX_DURATION_SECONDS: int = 3600
    SIM_ADMIN_KEY: str = "sim-admin-key-changeme"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://frontend:5173"]

    # Redis TTLs
    BEHAVIORAL_WINDOW_SECONDS: int = 86400  # 24h
    IDEMPOTENCY_TTL_SECONDS: int = 3600     # 1h

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
