"""Background monsoon-scenario simulator.

Advances the digital twin's physical state on a fixed real-time tick. Manual
fault injection (see control.py) mutates asset fields directly; the
simulator's physics then continues to evolve on top of whatever state it
finds — an injected flood recedes naturally once rainfall drops back down,
and an injected pump trip keeps raising the sump level until the pump is
manually restored.
"""

import random
import threading
import time
import traceback

from . import storage
from .twin_state import LIMITS, twin

TICK_SECONDS = 2.0
PUMP_CAPACITY_PCT_MIN = 0.9  # level-percent per minute one running pump removes

# Per-asset exposure multipliers so identical rainfall affects assets
# differently (a tank-farm MCC floods faster than a well-drained substation).
ELECTRICAL_EXPOSURE = {"MCC-01": 0.5, "MCC-02": 1.3, "SUBSTN-01": 0.35}
PROCESS_EXPOSURE = {"SUMP-01": 1.2, "SUMP-02": 0.8, "DRAIN-01": 1.0, "DYKE-01": 0.6}


class SimulatorControl:
    """Demo pacing controls: playback speed and pause, kept separate from
    plant state so resetting the scenario doesn't require touching this."""

    def __init__(self):
        self._lock = threading.Lock()
        self.speed = 10.0  # simulated minutes advanced per tick
        self.paused = False

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self.speed = max(0.0, min(speed, 200.0))

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self.paused = paused

    def snapshot(self) -> dict:
        with self._lock:
            return {"speed": self.speed, "paused": self.paused}


control = SimulatorControl()


def _step_electrical(asset: dict, rainfall_mm_hr: float, dt_min: float) -> None:
    # Tuned so calm/moderate rain stays flat (drainage keeps up) and only
    # heavy/extreme rain causes a climb, fastest for high-exposure assets —
    # see the worked example in the module docstring's design notes.
    exposure = ELECTRICAL_EXPOSURE.get(asset["id"], 0.5)
    inflow = rainfall_mm_hr * 0.001 * exposure
    drainage = 0.03
    asset["water_level_m"] = min(2.0, max(0.0, asset["water_level_m"] + (inflow - drainage) * dt_min))
    asset["water_ingress"] = asset["water_level_m"] > 0.5

    humidity_target = min(99.0, 50 + rainfall_mm_hr * 0.55 + (25 if asset["water_ingress"] else 0))
    asset["humidity_pct"] += (humidity_target - asset["humidity_pct"]) * min(0.15 * dt_min, 1.0)

    asset["motor_current_pct"] = max(35.0, min(140.0,
        asset["motor_current_pct"] + random.uniform(-1.0, 1.0) * dt_min))

    moist_stress = asset["water_ingress"] and asset["humidity_pct"] > LIMITS["humidity_pct"]
    if moist_stress:
        asset["leakage_current_ma"] += 6.0 * dt_min
    else:
        asset["leakage_current_ma"] = max(30.0, asset["leakage_current_ma"] - 2.0 * dt_min)
    asset["earth_fault_alarm"] = asset["leakage_current_ma"] > LIMITS["leakage_current_ma"]

    if moist_stress:
        asset["ir_mohm"] = max(5.0, asset["ir_mohm"] - 4.0 * dt_min)
        asset["ir_trend_declining"] = True
    else:
        asset["ir_trend_declining"] = False

    if (asset["earth_fault_alarm"] and asset["breaker_status"] == "closed"
            and random.random() < 0.02 * dt_min):
        asset["breaker_status"] = "tripped"


def _step_process(asset: dict, rainfall_mm_hr: float, dt_min: float) -> None:
    exposure = PROCESS_EXPOSURE.get(asset["id"], 1.0)
    inflow = rainfall_mm_hr * 0.045 * exposure

    outflow = 0.0
    if asset["duty_pump_status"] == "on":
        outflow += PUMP_CAPACITY_PCT_MIN
    if asset["standby_pump_status"] == "on":
        outflow += PUMP_CAPACITY_PCT_MIN * 0.9

    rate = inflow - outflow
    asset["rate_of_rise_pct_min"] = rate
    asset["level_pct"] = max(0.0, min(130.0, asset["level_pct"] + rate * dt_min))

    running_pumps = (asset["duty_pump_status"] == "on") + (asset["standby_pump_status"] == "on")
    asset["pump_flow_m3h"] = 95.0 * running_pumps
    asset["pump_discharge_bar"] = 3.4 if running_pumps else 0.0
    asset["critical_equipment_available"] = asset["duty_pump_status"] != "trip"


def _tick() -> None:
    snap = control.snapshot()
    if snap["paused"] or snap["speed"] <= 0:
        return
    dt_min = (TICK_SECONDS / 60.0) * snap["speed"]
    with twin.lock():
        twin.sim_minutes = twin.sim_minutes + dt_min
        rainfall = twin.rainfall_mm_hr
        for asset in twin.electrical.values():
            _step_electrical(asset, rainfall, dt_min)
        for asset in twin.process.values():
            _step_process(asset, rainfall, dt_min)
    storage.record_snapshot(twin.snapshot())


def _loop() -> None:
    while True:
        time.sleep(TICK_SECONDS)
        try:
            _tick()
        except Exception:
            # A bad tick should never take the simulator thread down.
            traceback.print_exc()


def start() -> None:
    threading.Thread(target=_loop, daemon=True).start()
