"""Simulation Router."""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from app.schemas.schemas import SimulationStartRequest, SimulationConfig
from app.sim_control import (
    start_simulation, stop_simulation, pause_simulation,
    resume_simulation, get_sim_state, reset_presentation_state
)
from app.config import get_settings

router = APIRouter()


def require_admin(x_admin_key: Optional[str] = Header(None)):
    settings = get_settings()
    if x_admin_key != settings.SIM_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.get("/simulation/status")
async def sim_status():
    return get_sim_state()

@router.get("/simulation/metrics")
async def sim_metrics():
    state = get_sim_state()
    return {"run_id": state.get("run_id"), "status": state.get("status"), "metrics": state.get("metrics", {})}

@router.post("/simulation/start")
async def sim_start(config: SimulationStartRequest, x_admin_key: Optional[str] = Header(None)):
    require_admin(x_admin_key)
    result = await start_simulation(config.model_dump())
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result

@router.post("/simulation/stop")
async def sim_stop(x_admin_key: Optional[str] = Header(None)):
    require_admin(x_admin_key)
    return await stop_simulation()

@router.post("/simulation/pause")
async def sim_pause(x_admin_key: Optional[str] = Header(None)):
    require_admin(x_admin_key)
    result = await pause_simulation()
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result

@router.post("/simulation/resume")
async def sim_resume(x_admin_key: Optional[str] = Header(None)):
    require_admin(x_admin_key)
    result = await resume_simulation()
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result

@router.patch("/simulation/config")
async def sim_config_update(config: SimulationConfig, x_admin_key: Optional[str] = Header(None)):
    require_admin(x_admin_key)
    state = get_sim_state()
    if state["status"] == "stopped":
        raise HTTPException(status_code=409, detail="Simulation not running")
    # Config updates apply to next run
    state["config"].update({k: v for k, v in config.model_dump().items() if v is not None})
    return {"status": "config_updated", "config": state["config"]}

@router.post("/simulation/reset")
async def sim_reset(x_admin_key: Optional[str] = Header(None)):
    require_admin(x_admin_key)
    return await reset_presentation_state()
