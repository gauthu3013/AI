"""Process discipline risk agent.

Checks: sump/drain/dyke level and rate of rise (with an overflow ETA
extrapolated from the current rate), dewatering-pump status, discharge
pressure, flow, and critical-equipment availability — the exact parameter
set from the brief's Process table.
"""

from . import combine
from ..twin_state import LIMITS


def _eta_minutes(level_pct: float, rate_pct_min: float) -> float | None:
    if rate_pct_min <= 0.01:
        return None
    remaining = max(0.0, 100.0 - level_pct)
    return remaining / rate_pct_min


def assess(asset: dict) -> dict:
    checks: list[tuple[str, str, str]] = []
    kind = asset["kind"]
    level = asset["level_pct"]
    rate = asset["rate_of_rise_pct_min"]
    eta = _eta_minutes(level, rate)

    if level > 85 or (eta is not None and eta < 30):
        checks.append(("high", f"{kind.capitalize()} overflow predicted",
                        "start the standby pump and inspect the drainage path"))
    elif level > 60 or (eta is not None and eta < 90):
        checks.append(("medium", f"{kind.capitalize()} level rising steadily",
                        "keep the standby pump ready and monitor the level"))

    if asset["duty_pump_status"] == "trip":
        checks.append(("high", "Duty dewatering pump tripped",
                        "start the standby pump and check pump performance"))
    elif asset["duty_pump_status"] == "off" and level > 40:
        checks.append(("medium", "Duty pump not running while level is rising",
                        "start the duty or standby pump"))

    running = asset["duty_pump_status"] == "on" or asset["standby_pump_status"] == "on"
    if running and asset["pump_discharge_bar"] < LIMITS["pump_discharge_bar_min"]:
        checks.append(("medium", "Pump discharge pressure below normal — possible blockage",
                        "check pump performance and inspect for blockage"))
    if running and asset["pump_flow_m3h"] < LIMITS["pump_flow_m3h_min"]:
        checks.append(("medium", "Pump flow below normal — possible blockage",
                        "inspect the drain and pump for blockage"))

    if not asset["critical_equipment_available"]:
        checks.append(("high", "Critical dewatering equipment unavailable",
                        "restore duty pump availability immediately"))

    return combine(asset, checks, eta_minutes=eta)
