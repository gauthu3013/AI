"""Monsoon Twin — AI agent-assisted digital twin for monsoon preparedness in
a chemical plant (Electrical + Process disciplines).

Pipeline: simulated plant/weather data -> digital twin state -> risk agents
predict monsoon risks -> dashboard shows risk level, affected equipment,
predicted problem, ETA, and recommended action.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import control, simulator, storage
from .agents import narrator, risk
from .twin_state import RAINFALL_PRESETS, twin

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

app = FastAPI(title="Monsoon Twin", version="1.0")


@app.on_event("startup")
def _startup():
    simulator.start()


class RainfallRequest(BaseModel):
    level: str


class FaultRequest(BaseModel):
    asset_id: str
    fault_type: str


class SpeedRequest(BaseModel):
    speed: float


class PauseRequest(BaseModel):
    paused: bool


@app.get("/api/state")
def get_state():
    snapshot = twin.snapshot()
    snapshot["sim_control"] = simulator.control.snapshot()
    return snapshot


@app.get("/api/risks")
def get_risks():
    snapshot = twin.snapshot()
    rows = risk.assess_all(snapshot)
    return {
        "sim_minutes": snapshot["sim_minutes"],
        "rainfall_mm_hr": snapshot["rainfall_mm_hr"],
        "rainfall_level": snapshot["rainfall_level"],
        "overall_level": risk.overall_level(rows),
        "rows": rows,
        "briefing": narrator.briefing(snapshot["rainfall_level"], rows),
    }


@app.get("/api/history/{asset_id}")
def get_history(asset_id: str, limit: int = 60):
    if asset_id not in twin.electrical and asset_id not in twin.process:
        raise HTTPException(status_code=404, detail=f"Unknown asset '{asset_id}'")
    return {"asset_id": asset_id, "readings": storage.history(asset_id, limit)}


@app.post("/api/control/rainfall")
def post_rainfall(body: RainfallRequest):
    try:
        control.set_rainfall(body.level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "rainfall_level": body.level, "presets": list(RAINFALL_PRESETS)}


@app.post("/api/control/fault")
def post_fault(body: FaultRequest):
    try:
        control.inject_fault(body.asset_id, body.fault_type)
    except control.UnknownAsset:
        raise HTTPException(status_code=404, detail=f"Unknown asset '{body.asset_id}'")
    except control.UnknownFault:
        raise HTTPException(status_code=400, detail=f"Unknown fault '{body.fault_type}'")
    return {"ok": True}


@app.post("/api/control/speed")
def post_speed(body: SpeedRequest):
    control.set_speed(body.speed)
    return {"ok": True, "speed": simulator.control.snapshot()["speed"]}


@app.post("/api/control/pause")
def post_pause(body: PauseRequest):
    control.set_paused(body.paused)
    return {"ok": True, "paused": body.paused}


@app.post("/api/control/reset")
def post_reset():
    control.reset_all()
    return {"ok": True}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
