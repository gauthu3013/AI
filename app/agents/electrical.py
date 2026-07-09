"""Electrical agent.

Analyzes the electrical deliverable (earthing calculation + power system
summary). Recomputes the earthing conductor size per the IEEE 80 / IS 3043
simplified formula and checks grid resistance and step/touch potentials
against their stated limits. Extracts the power chain capacities (utility
feed, transformers, UPS) for the digital twin.
"""

import math
import re

from . import finding
from ..parsers import as_float, load_xlsx, read_kv_sheet

DISCIPLINE = "electrical"

EARTHING_SHEET = "Earthing Calculation"
POWER_SHEET = "Power System Summary"


def analyze(filename: str, data: bytes) -> dict:
    wb = load_xlsx(data)
    findings: list[dict] = []
    extracted: dict = {"filename": filename, "transformers": [], "ups": []}

    if POWER_SHEET in wb.sheetnames:
        _analyze_power(read_kv_sheet(wb[POWER_SHEET]), filename, extracted, findings)
    else:
        findings.append(finding(
            DISCIPLINE, "error", f"Missing sheet '{POWER_SHEET}'",
            "The electrical workbook must contain the power system summary so the "
            "digital twin can model the power chain.", f"{filename}"))

    if EARTHING_SHEET in wb.sheetnames:
        _analyze_earthing(read_kv_sheet(wb[EARTHING_SHEET]), filename, findings, extracted)
    else:
        findings.append(finding(
            DISCIPLINE, "error", f"Missing sheet '{EARTHING_SHEET}'",
            "The electrical workbook must contain the earthing calculation.", f"{filename}"))

    return {"extracted": extracted, "findings": findings}


def _analyze_power(kv: dict, filename: str, extracted: dict, findings: list) -> None:
    loc = f"{filename} / {POWER_SHEET}"

    extracted["utility_feed_mw"] = as_float(kv.get("Utility Feed Capacity (MW)"))
    extracted["power_factor"] = as_float(kv.get("System Power Factor")) or 0.9

    for key, value in kv.items():
        m = re.match(r"^Transformer\s+(\S+)\s+Rating \(MVA\)$", key)
        if m:
            extracted["transformers"].append({"tag": m.group(1), "rating_mva": as_float(value)})
        m = re.match(r"^UPS\s+(\S+)\s+Rating \(kW\)$", key)
        if m:
            extracted["ups"].append({"tag": m.group(1), "rating_kw": as_float(value)})

    if extracted["utility_feed_mw"] is None:
        findings.append(finding(
            DISCIPLINE, "error", "Utility feed capacity missing",
            "'Utility Feed Capacity (MW)' was not found or is not a number.", loc))
    if not extracted["transformers"]:
        findings.append(finding(
            DISCIPLINE, "error", "No transformer ratings found",
            "Expected rows like 'Transformer TX-01 Rating (MVA)'.", loc))
    if not extracted["ups"]:
        findings.append(finding(
            DISCIPLINE, "error", "No UPS ratings found",
            "Expected rows like 'UPS UPS-A Rating (kW)'.", loc))


def _analyze_earthing(kv: dict, filename: str, findings: list, extracted: dict) -> None:
    loc = f"{filename} / {EARTHING_SHEET}"

    fault_ka = as_float(kv.get("Fault Current (kA)"))
    duration_s = as_float(kv.get("Fault Duration (s)"))
    k_const = as_float(kv.get("Material Constant k (A/mm2)"))
    stated_area = as_float(kv.get("Selected Conductor Cross-Section (mm2)"))
    soil = as_float(kv.get("Soil Resistivity (ohm-m)"))

    required_inputs = {
        "Fault Current (kA)": fault_ka,
        "Fault Duration (s)": duration_s,
        "Material Constant k (A/mm2)": k_const,
        "Selected Conductor Cross-Section (mm2)": stated_area,
        "Soil Resistivity (ohm-m)": soil,
    }
    for name, value in required_inputs.items():
        if value is None:
            findings.append(finding(
                DISCIPLINE, "error", f"Missing input: {name}",
                "This parameter is required to verify the earthing design.", loc))

    # Conductor sizing check: A = I * sqrt(t) / k  (I in amps)
    if None not in (fault_ka, duration_s, k_const, stated_area) and k_const:
        required_area = fault_ka * 1000.0 * math.sqrt(duration_s) / k_const
        extracted["earthing_required_area_mm2"] = round(required_area, 1)
        extracted["earthing_selected_area_mm2"] = stated_area
        if stated_area < required_area:
            findings.append(finding(
                DISCIPLINE, "error", "Earthing conductor undersized",
                f"Recomputed minimum cross-section is {required_area:.1f} mm2 "
                f"(I={fault_ka} kA, t={duration_s} s, k={k_const}), but the selected "
                f"conductor is only {stated_area:.0f} mm2.", loc))

    # Grid resistance check
    grid_r = as_float(kv.get("Calculated Grid Resistance (ohm)"))
    grid_r_max = as_float(kv.get("Maximum Allowed Grid Resistance (ohm)"))
    if grid_r is not None and grid_r_max is not None and grid_r > grid_r_max:
        findings.append(finding(
            DISCIPLINE, "error", "Grid resistance above the allowed limit",
            f"Calculated grid resistance is {grid_r} ohm against a maximum of "
            f"{grid_r_max} ohm.", loc))

    # Step / touch potential checks
    for kind in ("Step", "Touch"):
        calc = as_float(kv.get(f"Calculated {kind} Potential (V)"))
        limit = as_float(kv.get(f"Tolerable {kind} Potential (V)"))
        if calc is not None and limit is not None and calc > limit:
            findings.append(finding(
                DISCIPLINE, "error", f"{kind} potential exceeds tolerable limit",
                f"Calculated {kind.lower()} potential is {calc:.0f} V but the tolerable "
                f"limit is {limit:.0f} V. The earthing grid design must be revised.", loc))
