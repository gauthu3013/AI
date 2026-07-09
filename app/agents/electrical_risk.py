"""Electrical discipline risk agent.

Checks: water level near substation/MCC, panel-room humidity, water-ingress
status, leakage current / earth-fault alarm, breaker status, UPS/DG
availability, and insulation-resistance trend — the exact parameter set from
the brief's Electrical table.
"""

from . import combine
from ..twin_state import LIMITS


def assess(asset: dict) -> dict:
    checks: list[tuple[str, str, str]] = []

    water_level = asset["water_level_m"]
    if asset["water_ingress"] or water_level > 0.7:
        checks.append(("high", "Water ingress risk near the MCC/substation",
                        "inspect water ingress and cable-entry sealing"))
    elif water_level > 0.35:
        checks.append(("medium", "Water level rising near the MCC/substation",
                        "monitor drainage around the MCC plinth"))

    humidity = asset["humidity_pct"]
    if humidity > LIMITS["humidity_pct"]:
        checks.append(("high", "Panel-room humidity above the configured limit",
                        "check panel space-heater operation"))
    elif humidity > 70:
        checks.append(("medium", "Panel-room humidity trending up",
                        "check panel space-heater operation"))

    if asset["earth_fault_alarm"]:
        checks.append(("high", "Earth-fault / leakage-current alarm active",
                        "test insulation resistance and inspect the earthing system"))

    if asset["ir_mohm"] < LIMITS["ir_mohm_min"]:
        checks.append(("high", "Insulation resistance below the healthy minimum",
                        "test insulation resistance"))
    elif asset["ir_trend_declining"]:
        checks.append(("medium", "Insulation-resistance trend declining",
                        "test insulation resistance"))

    if asset["motor_current_pct"] > 130:
        checks.append(("high", "Motor current well above normal — likely overload",
                        "check outdoor motor current and vibration"))
    elif asset["motor_current_pct"] > 115:
        checks.append(("medium", "Motor current above normal",
                        "check outdoor motor current and vibration"))

    if asset["breaker_status"] == "tripped":
        checks.append(("high", "Critical breaker tripped — equipment unavailable",
                        "inspect the breaker and restore critical supply"))

    if not asset["ups_dg_available"]:
        checks.append(("medium", "Emergency power (UPS/DG) not available",
                        "verify UPS/DG readiness"))

    return combine(asset, checks)
