"""Executive summary agent.

If ANTHROPIC_API_KEY is available, asks Claude to write an engineering
review summary of the twin state and findings. Falls back to a rule-based
summary otherwise, so the demo works fully offline.
"""

import json
import os

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are the lead design reviewer for a data center / AI factory project. "
    "You are given the digital twin state (power and cooling chains) and the "
    "validation findings produced by discipline agents. Write a short executive "
    "summary for the engineering manager: overall verdict first, then the "
    "critical issues in order of severity with concrete numbers, then the "
    "recommended next actions. Plain text, no markdown headings, under 180 words."
)


def summarize(twin: dict, findings: list[dict]) -> dict:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return {"source": "claude", "text": _claude_summary(twin, findings)}
        except Exception as exc:  # never let the AI layer break the dashboard
            fallback = _rule_based_summary(twin, findings)
            return {"source": "rule-based",
                    "text": fallback + f"\n(AI summary unavailable: {exc})"}
    return {"source": "rule-based", "text": _rule_based_summary(twin, findings)}


def _claude_summary(twin: dict, findings: list[dict]) -> str:
    import anthropic

    client = anthropic.Anthropic()
    payload = json.dumps({"twin": twin, "findings": findings}, indent=2)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Review this design validation run:\n{payload}"}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def _rule_based_summary(twin: dict, findings: list[dict]) -> str:
    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    cross = [f for f in errors if f["discipline"] == "cross-discipline"]

    if not errors and not warnings:
        verdict = "Design validation PASSED — no issues found across the three disciplines."
    elif not errors:
        verdict = f"Design validation passed with {len(warnings)} warning(s) to review."
    else:
        verdict = (f"Design validation FAILED — {len(errors)} error(s) and "
                   f"{len(warnings)} warning(s) across the deliverables.")

    lines = [verdict]
    if cross:
        lines.append("End-to-end issues found by the digital twin:")
        lines += [f"  - {f['title']}" for f in cross[:4]]
    discipline_errors = [f for f in errors if f["discipline"] != "cross-discipline"]
    if discipline_errors:
        lines.append("Document-level errors:")
        lines += [f"  - [{f['discipline']}] {f['title']}" for f in discipline_errors[:5]]
    if errors:
        lines.append("Recommended action: resolve the red items above and re-upload the "
                     "corrected deliverables before design freeze.")
    return "\n".join(lines)
