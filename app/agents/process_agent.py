"""Process agent.

Analyzes the equipment list: duplicate tags, missing loads, quantity/total
consistency. Extracts the IT load (rack blocks) and the list of mechanical
tags for cross-discipline reconciliation in the digital twin.
"""

import re

from . import finding
from ..parsers import as_float, load_xlsx, read_table_sheet

DISCIPLINE = "process"

SHEET = "Equipment List"
TAG_RE = re.compile(r"^[A-Z]{2,6}-[A-Z]?\d{2,3}$")


def analyze(filename: str, data: bytes) -> dict:
    wb = load_xlsx(data)
    findings: list[dict] = []
    extracted: dict = {
        "filename": filename,
        "it_rows": [],
        "mechanical_tags": [],
        "total_it_load_kw": 0.0,
    }

    if SHEET not in wb.sheetnames:
        findings.append(finding(
            DISCIPLINE, "error", f"Missing sheet '{SHEET}'",
            "The process workbook must contain the equipment list.", filename))
        return {"extracted": extracted, "findings": findings}

    rows = read_table_sheet(wb[SHEET])
    seen: dict[str, int] = {}

    for row in rows:
        tag = str(row.get("Tag") or "").strip()
        loc = f"{filename} / {SHEET} / row {row['_row']}"
        category = str(row.get("Category") or "").strip().lower()

        if not tag:
            findings.append(finding(
                DISCIPLINE, "error", "Equipment row without a tag",
                "Every equipment list entry must carry a tag.", loc))
            continue

        if tag in seen:
            findings.append(finding(
                DISCIPLINE, "error", f"Duplicate tag '{tag}'",
                f"Tag already used on row {seen[tag]} — duplicate tags break "
                "cross-discipline traceability.", loc))
        else:
            seen[tag] = row["_row"]

        if not TAG_RE.fullmatch(tag):
            findings.append(finding(
                DISCIPLINE, "warning", f"Tag '{tag}' does not follow the project format",
                "Expected a tag like RACK-A01 or CH-01.", loc))

        qty = as_float(row.get("Quantity"))
        unit_kw = as_float(row.get("Unit Load (kW)"))
        total_kw = as_float(row.get("Total Load (kW)"))

        if category == "it":
            if unit_kw is None:
                findings.append(finding(
                    DISCIPLINE, "error", f"{tag}: unit load is missing",
                    "IT equipment entries must state the electrical load per unit — "
                    "without it the twin cannot compute the facility IT load.", loc))
            if None not in (qty, unit_kw, total_kw) and abs(qty * unit_kw - total_kw) > 0.5:
                findings.append(finding(
                    DISCIPLINE, "warning", f"{tag}: total load does not match quantity x unit load",
                    f"{qty:g} x {unit_kw:g} kW = {qty * unit_kw:g} kW, but the row states "
                    f"{total_kw:g} kW.", loc))
            row_load = total_kw if total_kw is not None else (
                qty * unit_kw if None not in (qty, unit_kw) else 0.0)
            extracted["it_rows"].append({"tag": tag, "load_kw": row_load, "row": row["_row"]})
            extracted["total_it_load_kw"] += row_load or 0.0
        elif category == "mechanical":
            extracted["mechanical_tags"].append({"tag": tag, "row": row["_row"]})

    extracted["total_it_load_kw"] = round(extracted["total_it_load_kw"], 1)
    return {"extracted": extracted, "findings": findings}
