"""Control-room briefing agent.

If ANTHROPIC_API_KEY is set, asks Claude to write a short shift-handover
briefing from the current risk table — the kind of note a control-room
engineer would read at the top of their shift. Falls back to a rule-based
briefing otherwise, so the dashboard works fully offline.
"""

import os

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are the monsoon-preparedness control-room assistant for a chemical plant. "
    "You are given the current digital twin risk table (electrical and process "
    "assets, each with a risk level, predicted problem, ETA, and recommended "
    "action). Write a 2-4 sentence shift-handover briefing: state the overall "
    "plant risk level first, then the most urgent item(s) with their ETA if any, "
    "then the single most important action to take right now. Plain text, no "
    "markdown, no bullet points, under 70 words."
)


def briefing(rainfall_level: str, rows: list[dict]) -> dict:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return {"source": "claude", "text": _claude_briefing(rainfall_level, rows)}
        except Exception as exc:  # never let the AI layer break the dashboard
            return {"source": "rule-based",
                    "text": _rule_based_briefing(rainfall_level, rows) +
                            f" (AI briefing unavailable: {exc})"}
    return {"source": "rule-based", "text": _rule_based_briefing(rainfall_level, rows)}


def _claude_briefing(rainfall_level: str, rows: list[dict]) -> str:
    import json

    import anthropic

    client = anthropic.Anthropic()
    payload = json.dumps({"rainfall_level": rainfall_level, "risk_table": rows}, indent=2)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Current digital twin state:\n{payload}"}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def _rule_based_briefing(rainfall_level: str, rows: list[dict]) -> str:
    high = [r for r in rows if r["risk_level"] == "high"]
    medium = [r for r in rows if r["risk_level"] == "medium"]

    if not high and not medium:
        return (f"Rainfall is {rainfall_level}. All electrical and process parameters are "
                "within normal range — no monsoon-related risks detected. Continue routine monitoring.")

    if high:
        worst = min(high, key=lambda r: r["eta_minutes"] if r["eta_minutes"] is not None else float("inf"))
        eta_clause = f" in {worst['eta_label']}" if worst["eta_minutes"] is not None else ""
        return (f"Rainfall is {rainfall_level} with {len(high)} HIGH-risk item(s). "
                f"Most urgent: {worst['label']} — {worst['predicted_problem']}{eta_clause}. "
                f"Immediate action: {worst['recommended_action']}.")

    top = medium[0]
    return (f"Rainfall is {rainfall_level} with {len(medium)} item(s) at MEDIUM risk, none critical yet. "
            f"Watch {top['label']} ({top['predicted_problem']}) and {top['recommended_action'].lower()}.")
