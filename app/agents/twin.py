"""Digital twin builder and end-to-end design validator.

Merges the structured data extracted by the three discipline agents into a
single facility model (power chain + cooling chain) and validates the design
across disciplines:

  - Power chain: IT load <= UPS capacity <= transformer capacity <= utility feed
  - Cooling chain: heat load <= installed cooling capacity, with N+1 redundancy
  - Tag reconciliation: every mechanical item in the equipment list must have a
    data sheet, and vice versa
"""

from . import finding

DISCIPLINE = "cross-discipline"

# Mechanical/electrical auxiliary demand (cooling plant, pumps, lighting) as a
# fraction of IT load — a standard early-design assumption for the twin.
AUX_LOAD_FACTOR = 0.30


def build(electrical: dict | None, mechanical: dict | None, process: dict | None) -> dict:
    findings: list[dict] = []
    twin: dict = {"power_chain": None, "cooling_chain": None, "assumptions": {
        "aux_load_factor": AUX_LOAD_FACTOR,
        "heat_load_equals_it_load": True,
    }}

    it_load_kw = (process or {}).get("total_it_load_kw") or 0.0

    if electrical:
        twin["power_chain"] = _power_chain(electrical, it_load_kw, findings, bool(process))
    if mechanical:
        twin["cooling_chain"] = _cooling_chain(mechanical, it_load_kw, findings, bool(process))
    if mechanical and process:
        _reconcile_tags(mechanical, process, findings)

    return {"twin": twin, "findings": findings}


def _power_chain(electrical: dict, it_load_kw: float, findings: list, have_process: bool) -> dict:
    pf = electrical.get("power_factor") or 0.9
    utility_kw = (electrical.get("utility_feed_mw") or 0.0) * 1000.0
    transformer_kw = sum((t["rating_mva"] or 0.0) * 1000.0 * pf for t in electrical["transformers"])
    ups_kw = sum(u["rating_kw"] or 0.0 for u in electrical["ups"])
    facility_load_kw = it_load_kw * (1 + AUX_LOAD_FACTOR)

    chain = {
        "utility_kw": round(utility_kw, 1),
        "transformer_kw": round(transformer_kw, 1),
        "ups_kw": round(ups_kw, 1),
        "it_load_kw": round(it_load_kw, 1),
        "facility_load_kw": round(facility_load_kw, 1),
        "transformers": electrical["transformers"],
        "ups": electrical["ups"],
    }

    if not have_process:
        return chain

    if ups_kw and it_load_kw > ups_kw:
        findings.append(finding(
            DISCIPLINE, "error", "IT load exceeds UPS capacity",
            f"The equipment list totals {it_load_kw:.0f} kW of IT load, but the "
            f"installed UPS capacity from the electrical deliverable is only "
            f"{ups_kw:.0f} kW. The critical power path is undersized.",
            "Equipment List vs Power System Summary"))
    if transformer_kw and facility_load_kw > transformer_kw:
        findings.append(finding(
            DISCIPLINE, "error", "Facility load exceeds transformer capacity",
            f"IT load plus {AUX_LOAD_FACTOR:.0%} auxiliaries is "
            f"{facility_load_kw:.0f} kW, above the usable transformer capacity of "
            f"{transformer_kw:.0f} kW (at PF {pf}).",
            "Equipment List vs Power System Summary"))
    if utility_kw and transformer_kw > utility_kw:
        findings.append(finding(
            DISCIPLINE, "warning", "Transformer capacity exceeds the utility feed",
            f"Installed transformation ({transformer_kw:.0f} kW) is larger than the "
            f"utility feed ({utility_kw:.0f} kW) — confirm the intended diversity.",
            "Power System Summary"))
    return chain


def _cooling_chain(mechanical: dict, it_load_kw: float, findings: list, have_process: bool) -> dict:
    chillers = [e for e in mechanical["equipment"]
                if e["capacity_kw"] and "chiller" in e["type"].lower()]
    capacity_kw = sum(c["capacity_kw"] for c in chillers)
    largest_kw = max((c["capacity_kw"] for c in chillers), default=0.0)
    heat_load_kw = it_load_kw  # design assumption: IT load is rejected as heat

    chain = {
        "heat_load_kw": round(heat_load_kw, 1),
        "cooling_capacity_kw": round(capacity_kw, 1),
        "n_plus_1_capacity_kw": round(capacity_kw - largest_kw, 1),
        "chillers": chillers,
    }

    if not have_process:
        return chain

    if capacity_kw and heat_load_kw > capacity_kw:
        findings.append(finding(
            DISCIPLINE, "error", "Heat load exceeds installed cooling capacity",
            f"The IT heat load is {heat_load_kw:.0f} kW, but the chillers on the "
            f"mechanical data sheets total only {capacity_kw:.0f} kW.",
            "Equipment List vs Cooling Equipment data sheets"))
    elif capacity_kw and heat_load_kw > capacity_kw - largest_kw:
        findings.append(finding(
            DISCIPLINE, "error", "N+1 cooling redundancy is violated",
            f"Losing the largest chiller ({largest_kw:.0f} kW) drops capacity to "
            f"{capacity_kw - largest_kw:.0f} kW, below the {heat_load_kw:.0f} kW heat "
            "load. A single chiller failure would overheat the facility.",
            "Cooling Equipment data sheets"))
    return chain


def _reconcile_tags(mechanical: dict, process: dict, findings: list) -> None:
    datasheet_tags = {e["tag"] for e in mechanical["equipment"]}
    list_tags = {m["tag"] for m in process["mechanical_tags"]}

    for missing in sorted(list_tags - datasheet_tags):
        findings.append(finding(
            DISCIPLINE, "error", f"{missing}: listed but has no data sheet",
            f"'{missing}' appears in the process equipment list but there is no "
            "matching mechanical data sheet — the item cannot be validated.",
            "Equipment List vs Cooling Equipment data sheets"))
    for orphan in sorted(datasheet_tags - list_tags):
        findings.append(finding(
            DISCIPLINE, "warning", f"{orphan}: data sheet without an equipment list entry",
            f"'{orphan}' has a mechanical data sheet but is missing from the process "
            "equipment list.", "Cooling Equipment data sheets vs Equipment List"))
