"""Mechanical agent.

Analyzes the cooling equipment data sheets: mandatory fields, tag format,
design vs operating conditions. Extracts chiller/CRAH capacities and
redundancy roles for the digital twin's cooling chain.
"""

import re

from . import finding
from ..parsers import as_float, load_xlsx, read_table_sheet

DISCIPLINE = "mechanical"

SHEET = "Cooling Equipment"
TAG_RE = re.compile(r"^[A-Z]{2,6}-\d{2,3}$")

MANDATORY = [
    "Rated Cooling Capacity (kW)",
    "Design Temp (C)",
    "Operating Temp (C)",
    "Design Pressure (bar)",
    "Operating Pressure (bar)",
]


def analyze(filename: str, data: bytes) -> dict:
    wb = load_xlsx(data)
    findings: list[dict] = []
    extracted: dict = {"filename": filename, "equipment": []}

    if SHEET not in wb.sheetnames:
        findings.append(finding(
            DISCIPLINE, "error", f"Missing sheet '{SHEET}'",
            "The mechanical workbook must contain the cooling equipment data sheets.",
            filename))
        return {"extracted": extracted, "findings": findings}

    rows = read_table_sheet(wb[SHEET])
    if not rows:
        findings.append(finding(
            DISCIPLINE, "error", "No equipment rows found",
            f"Sheet '{SHEET}' has a header but no data rows.", f"{filename} / {SHEET}"))

    for row in rows:
        tag = str(row.get("Tag") or "").strip()
        loc = f"{filename} / {SHEET} / row {row['_row']}"

        if not tag:
            findings.append(finding(
                DISCIPLINE, "error", "Equipment row without a tag",
                "Every data sheet row must carry an equipment tag.", loc))
            continue
        if not TAG_RE.fullmatch(tag):
            findings.append(finding(
                DISCIPLINE, "warning", f"Tag '{tag}' does not follow the project format",
                "Expected a tag like CH-01 or CRAH-03 (letters, dash, number).", loc))

        for field in MANDATORY:
            if as_float(row.get(field)) is None:
                findings.append(finding(
                    DISCIPLINE, "error", f"{tag}: mandatory field '{field}' is missing",
                    "The data sheet is incomplete — this value is required for design "
                    "validation.", loc))

        d_temp, o_temp = as_float(row.get("Design Temp (C)")), as_float(row.get("Operating Temp (C)"))
        if d_temp is not None and o_temp is not None and d_temp < o_temp:
            findings.append(finding(
                DISCIPLINE, "error", f"{tag}: design temperature below operating temperature",
                f"Design temp {d_temp} C must be greater than or equal to operating temp "
                f"{o_temp} C.", loc))

        d_p, o_p = as_float(row.get("Design Pressure (bar)")), as_float(row.get("Operating Pressure (bar)"))
        if d_p is not None and o_p is not None and d_p < o_p:
            findings.append(finding(
                DISCIPLINE, "error", f"{tag}: design pressure below operating pressure",
                f"Design pressure {d_p} bar must be greater than or equal to operating "
                f"pressure {o_p} bar.", loc))

        extracted["equipment"].append({
            "tag": tag,
            "type": str(row.get("Equipment") or "").strip(),
            "capacity_kw": as_float(row.get("Rated Cooling Capacity (kW)")),
            "redundancy_role": str(row.get("Redundancy Role") or "").strip(),
            "row": row["_row"],
        })

    return {"extracted": extracted, "findings": findings}
