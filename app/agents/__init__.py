"""Discipline agents for the digital-twin validation pipeline.

Each agent takes the uploaded workbook bytes and returns:
  {
    "extracted": {...},   # structured data merged into the digital twin
    "findings": [...],    # per-document validation findings
  }

Finding shape (shared across agents and the twin validator):
  {
    "discipline": "electrical" | "mechanical" | "process" | "cross-discipline",
    "severity": "error" | "warning" | "info",
    "title": short statement of the defect,
    "detail": what was found vs what was expected,
    "location": "file / sheet / row or parameter",
  }
"""


def finding(discipline: str, severity: str, title: str, detail: str, location: str) -> dict:
    return {
        "discipline": discipline,
        "severity": severity,
        "title": title,
        "detail": detail,
        "location": location,
    }
