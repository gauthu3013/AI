"""Aggregates the electrical and process agents into the dashboard's risk
table: sorted worst-first, then most-urgent-first."""

from . import electrical_risk, process_risk

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def assess_all(snapshot: dict) -> list[dict]:
    rows = [electrical_risk.assess(asset) for asset in snapshot["electrical"].values()]
    rows += [process_risk.assess(asset) for asset in snapshot["process"].values()]
    rows.sort(key=lambda r: (
        -_SEVERITY_ORDER[r["risk_level"]],
        r["eta_minutes"] if r["eta_minutes"] is not None else float("inf"),
    ))
    return rows


def overall_level(rows: list[dict]) -> str:
    if not rows:
        return "low"
    return max(rows, key=lambda r: _SEVERITY_ORDER[r["risk_level"]])["risk_level"]
