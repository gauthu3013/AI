"""The digital twin's live state: every Electrical and Process asset in the
plant, plus the shared weather signal. This module is the single source of
truth for "what the plant looks like right now" — the simulator advances it,
the risk agents read it, and the storage layer persists snapshots of it.
"""

import threading

# Physical limits used both by the simulator (to clamp values) and the risk
# agents (to judge how close to the limit a reading is).
LIMITS = {
    "water_level_m": 1.2,          # substation/MCC plinth flood height
    "humidity_pct": 85.0,          # panel room condensation risk above this
    "leakage_current_ma": 300.0,   # earth-fault alarm threshold
    "ir_mohm_min": 100.0,          # insulation resistance minimum healthy value
    "sump_level_pct": 100.0,
    "drain_level_pct": 100.0,
    "dyke_level_pct": 100.0,
    "pump_discharge_bar_min": 2.0,
    "pump_flow_m3h_min": 40.0,
}

RAINFALL_PRESETS = {
    "calm": 2.0,        # mm/hr
    "moderate": 18.0,
    "heavy": 45.0,
    "extreme": 80.0,
}


def _electrical_asset(asset_id: str, label: str) -> dict:
    return {
        "id": asset_id,
        "label": label,
        "discipline": "electrical",
        "water_level_m": 0.05,
        "humidity_pct": 55.0,
        "water_ingress": False,
        "motor_current_pct": 62.0,
        "breaker_status": "closed",       # closed | tripped
        "leakage_current_ma": 40.0,
        "earth_fault_alarm": False,
        "ups_dg_available": True,
        "ir_mohm": 480.0,
        "ir_trend_declining": False,
    }


def _process_asset(asset_id: str, label: str, kind: str) -> dict:
    base = {
        "id": asset_id,
        "label": label,
        "discipline": "process",
        "kind": kind,                     # sump | drain | dyke
        "level_pct": 20.0,
        "rate_of_rise_pct_min": 0.05,
        "duty_pump_status": "on",         # on | off | trip
        "standby_pump_status": "off",     # on | off | trip
        "pump_discharge_bar": 3.2,
        "pump_flow_m3h": 85.0,
        "critical_equipment_available": True,
    }
    base["id"] = asset_id
    base["label"] = label
    return base


class Twin:
    """Thread-safe container for the plant's live digital-twin state."""

    def __init__(self):
        # RLock: property getters/setters below acquire it, and callers
        # (simulator, control API) also wrap multi-field updates in
        # `with twin.lock():` — a plain Lock would deadlock on that nesting.
        self._lock = threading.RLock()
        self._sim_minutes = 0.0
        self._rainfall_mm_hr = RAINFALL_PRESETS["calm"]
        self._rainfall_level = "calm"
        self.electrical: dict[str, dict] = {
            "MCC-01": _electrical_asset("MCC-01", "MCC-01 (Utilities Block)"),
            "MCC-02": _electrical_asset("MCC-02", "MCC-02 (Tank Farm Area)"),
            "SUBSTN-01": _electrical_asset("SUBSTN-01", "Substation-01 (Main Incomer)"),
        }
        self.process: dict[str, dict] = {
            "SUMP-01": _process_asset("SUMP-01", "Sump-01 (Process Area Low Point)", "sump"),
            "SUMP-02": _process_asset("SUMP-02", "Sump-02 (Utilities Yard)", "sump"),
            "DRAIN-01": _process_asset("DRAIN-01", "Storm Drain-01 (Plant Perimeter)", "drain"),
            "DYKE-01": _process_asset("DYKE-01", "Tank Farm Dyke-01", "dyke"),
        }

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "sim_minutes": round(self._sim_minutes, 1),
                "rainfall_mm_hr": round(self._rainfall_mm_hr, 1),
                "rainfall_level": self._rainfall_level,
                "electrical": {k: dict(v) for k, v in self.electrical.items()},
                "process": {k: dict(v) for k, v in self.process.items()},
            }

    def lock(self):
        return self._lock

    @property
    def sim_minutes(self) -> float:
        return self._sim_minutes

    @sim_minutes.setter
    def sim_minutes(self, value: float):
        self._sim_minutes = value

    @property
    def rainfall_mm_hr(self) -> float:
        return self._rainfall_mm_hr

    @rainfall_mm_hr.setter
    def rainfall_mm_hr(self, value: float):
        self._rainfall_mm_hr = value

    @property
    def rainfall_level(self) -> str:
        return self._rainfall_level

    @rainfall_level.setter
    def rainfall_level(self, value: str):
        self._rainfall_level = value

    def reset(self):
        with self._lock:
            self._sim_minutes = 0.0
            self._rainfall_mm_hr = RAINFALL_PRESETS["calm"]
            self._rainfall_level = "calm"
            self.electrical = {
                "MCC-01": _electrical_asset("MCC-01", "MCC-01 (Utilities Block)"),
                "MCC-02": _electrical_asset("MCC-02", "MCC-02 (Tank Farm Area)"),
                "SUBSTN-01": _electrical_asset("SUBSTN-01", "Substation-01 (Main Incomer)"),
            }
            self.process = {
                "SUMP-01": _process_asset("SUMP-01", "Sump-01 (Process Area Low Point)", "sump"),
                "SUMP-02": _process_asset("SUMP-02", "Sump-02 (Utilities Yard)", "sump"),
                "DRAIN-01": _process_asset("DRAIN-01", "Storm Drain-01 (Plant Perimeter)", "drain"),
                "DYKE-01": _process_asset("DYKE-01", "Tank Farm Dyke-01", "dyke"),
            }


twin = Twin()
