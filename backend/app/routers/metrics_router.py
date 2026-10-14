"""Metrics Router."""
from fastapi import APIRouter, Query
from app.database import get_metrics_summary, get_metrics_timeseries
from app.sim_control import get_sim_state

router = APIRouter()

@router.get("/metrics/summary")
async def metrics_summary():
    summary = await get_metrics_summary()
    sim = get_sim_state()
    summary["simulator_state"] = sim["status"]
    summary["sim_metrics"] = sim.get("metrics", {})
    return summary

@router.get("/metrics/timeseries")
async def metrics_timeseries(minutes: int = Query(60, ge=5, le=1440)):
    series = await get_metrics_timeseries(minutes=minutes)
    return {"series": series, "window_minutes": minutes}
