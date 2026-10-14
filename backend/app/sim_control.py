"""
ReturnShield Simulation Controller
=====================================
Controls the Locust load generator process.
FastAPI starts/stops/configures Locust via subprocess.
"""
import asyncio
import json
import logging
import subprocess
import sys
import time
import os
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Simulation state
_sim_state = {
    "status": "stopped",  # stopped | running | paused
    "run_id": None,
    "config": {},
    "started_at": None,
    "metrics": {
        "generated": 0,
        "processed": 0,
        "failed": 0,
        "achieved_rps": 0.0,
        "latency_p50": None,
        "latency_p95": None,
        "latency_p99": None,
        "prediction_counts": {"Genuine": 0, "Mistaken": 0, "Suspicious": 0},
    },
}

_locust_process: Optional[subprocess.Popen] = None
_sim_lock = asyncio.Lock()


_latencies: list[float] = []
_start_perf_time: float = 0.0


def record_sim_transaction(predicted_label: str, total_ms: float):
    """Update live simulation metrics with each genuine processed transaction."""
    global _sim_state, _latencies, _start_perf_time
    if _sim_state.get("status") != "running":
        return

    m = _sim_state["metrics"]
    m["processed"] += 1
    m["generated"] += 1
    if predicted_label in m["prediction_counts"]:
        m["prediction_counts"][predicted_label] += 1
    else:
        m["prediction_counts"][predicted_label] = 1

    _latencies.append(total_ms)
    if len(_latencies) > 2000:
        _latencies.pop(0)

    elapsed = time.perf_counter() - _start_perf_time
    if elapsed > 0.1:
        m["achieved_rps"] = round(m["processed"] / elapsed, 2)

    if _latencies:
        sorted_lats = sorted(_latencies)
        n = len(sorted_lats)
        m["latency_p50"] = round(sorted_lats[int(n * 0.5)], 2)
        m["latency_p95"] = round(sorted_lats[min(int(n * 0.95), n - 1)], 2)
        m["latency_p99"] = round(sorted_lats[min(int(n * 0.99), n - 1)], 2)


def get_sim_state() -> dict:
    return dict(_sim_state)


async def start_simulation(config: dict) -> dict:
    global _locust_process, _sim_state, _latencies, _start_perf_time

    async with _sim_lock:
        if _sim_state["status"] in ("running", "paused"):
            return {"error": "Simulation already running. Stop it first."}

        run_id = f"run-{int(time.time())}"
        _sim_state["status"] = "running"
        _sim_state["run_id"] = run_id
        _sim_state["config"] = config
        _sim_state["started_at"] = datetime.now(timezone.utc).isoformat()
        _sim_state["metrics"] = {
            "generated": 0, "processed": 0, "failed": 0,
            "achieved_rps": 0.0, "latency_p50": None, "latency_p95": None, "latency_p99": None,
            "prediction_counts": {"Genuine": 0, "Mistaken": 0, "Suspicious": 0},
        }
        _latencies = []
        _start_perf_time = time.perf_counter()

        # Build Locust command
        backend_url = os.environ.get("BACKEND_INTERNAL_URL", "http://127.0.0.1:8000")
        locust_file = os.environ.get("LOCUST_FILE")
        if not locust_file or not os.path.exists(locust_file):
            candidates = [
                "/app/loadtest/locustfile.py",
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "loadtest", "locustfile.py")),
                "loadtest/locustfile.py",
            ]
            for c in candidates:
                if os.path.exists(c):
                    locust_file = c
                    break

        users = config.get("concurrency", 5)
        rps = config.get("target_rps", 5.0)
        duration = config.get("duration_seconds", 120)
        scenario = config.get("scenario", "mixed")

        env = {
            **os.environ,
            "RS_SCENARIO": scenario,
            "RS_PCT_GENUINE": str(config.get("scenario_pct_genuine", 60)),
            "RS_PCT_MISTAKEN": str(config.get("scenario_pct_mistaken", 25)),
            "RS_PCT_SUSPICIOUS": str(config.get("scenario_pct_suspicious", 15)),
            "RS_SEED": str(config.get("seed", 42)),
            "RS_TARGET_URL": backend_url,
        }

        cmd = [
            sys.executable, "-m", "locust",
            "-f", locust_file,
            "--headless",
            "--host", backend_url,
            f"--users={users}",
            f"--spawn-rate={min(users, 5)}",
            f"--run-time={duration}s",
        ]

        try:
            _locust_process = subprocess.Popen(
                cmd, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            logger.info(f"Locust started. PID={_locust_process.pid}, run_id={run_id}, file={locust_file}")

            # Schedule auto-stop
            asyncio.create_task(_auto_stop_after(duration + 10))

        except Exception as e:
            logger.error(f"Failed to start Locust: {e}")
            _sim_state["status"] = "stopped"
            return {"error": str(e)}

    return {"run_id": run_id, "status": "running", "config": config}


async def stop_simulation() -> dict:
    global _locust_process, _sim_state

    async with _sim_lock:
        if _locust_process and _locust_process.poll() is None:
            _locust_process.terminate()
            try:
                _locust_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _locust_process.kill()
            logger.info("Locust process terminated")

        _locust_process = None
        _sim_state["status"] = "stopped"

    return {"status": "stopped"}


async def pause_simulation() -> dict:
    """Pause: stop Locust process but preserve state."""
    global _locust_process, _sim_state

    async with _sim_lock:
        if _sim_state["status"] != "running":
            return {"error": "Not running"}

        if _locust_process and _locust_process.poll() is None:
            _locust_process.terminate()
            try:
                _locust_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _locust_process.kill()

        _locust_process = None
        _sim_state["status"] = "paused"

    return {"status": "paused"}


async def resume_simulation() -> dict:
    """Resume: restart Locust with preserved config."""
    async with _sim_lock:
        if _sim_state["status"] != "paused":
            return {"error": "Not paused"}
        _sim_state["status"] = "stopped"

    config = _sim_state["config"]
    return await start_simulation(config)



async def update_sim_metrics(update: dict):
    """Called by Locust webhook or polling to update metrics."""
    _sim_state["metrics"].update(update)


async def _auto_stop_after(seconds: int):
    """Auto-stop simulation after duration."""
    await asyncio.sleep(seconds)
    if _sim_state["status"] == "running":
        await stop_simulation()
        logger.info(f"Simulation auto-stopped after {seconds}s")


async def reset_presentation_state():
    """Reset metrics counters. Does NOT delete MongoDB records."""
    _sim_state["metrics"] = {
        "generated": 0, "processed": 0, "failed": 0,
        "achieved_rps": 0.0,
        "latency_p50": None, "latency_p95": None, "latency_p99": None,
        "prediction_counts": {"Genuine": 0, "Mistaken": 0, "Suspicious": 0},
    }
    return {"reset": True, "note": "Presentation counters reset. MongoDB audit history preserved."}
