"""Monsoon-preparedness risk agents.

Each agent inspects one discipline's live twin state and returns a risk
record with exactly the five fields the dashboard shows:
  risk_level, label (affected area/equipment), predicted_problem,
  eta_minutes/eta_label, recommended_action.
"""

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def combine(asset: dict, checks: list[tuple[str, str, str]], eta_minutes: float | None = None) -> dict:
    """Fold a list of (severity, problem, action) checks into one risk record.

    Overall severity is the worst triggered check. The predicted-problem text
    joins every problem statement at that worst severity; the recommended
    action pools every triggered action (deduplicated, most relevant first)
    so the dashboard reads like the brief's example outputs.
    """
    if not checks:
        risk_level = "low"
        problem = "No monsoon-related anomalies detected"
        action = "Continue routine monitoring"
    else:
        risk_level = max(checks, key=lambda c: SEVERITY_ORDER[c[0]])[0]
        top = [c for c in checks if c[0] == risk_level]
        problem = "; ".join(dict.fromkeys(c[1] for c in top))
        actions = list(dict.fromkeys(c[2] for c in checks))
        action = ", ".join(actions[:3])
        if len(actions) > 3:
            action += ", and check the remaining flagged items"
        action = action[0].upper() + action[1:] if action else action

    if eta_minutes is not None and eta_minutes < 500:
        eta_label = f"~{round(eta_minutes)} min"
    elif eta_minutes is not None:
        eta_label = "Not imminent"
    else:
        eta_label = "N/A"

    return {
        "asset_id": asset["id"],
        "label": asset["label"],
        "discipline": asset["discipline"],
        "risk_level": risk_level,
        "predicted_problem": problem,
        "eta_minutes": round(eta_minutes) if eta_minutes is not None else None,
        "eta_label": eta_label,
        "recommended_action": action,
    }
