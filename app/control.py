"""Manual override API used by the demo control panel: rainfall presets,
fault injection per asset, playback speed/pause, and scenario reset.
"""

from . import simulator, storage
from .twin_state import RAINFALL_PRESETS, twin

ELECTRICAL_FAULTS = {
    "flood": lambda a: a.update(water_level_m=0.9, humidity_pct=92.0),
    "earth_fault": lambda a: a.update(leakage_current_ma=350.0, earth_fault_alarm=True),
    "breaker_trip": lambda a: a.update(breaker_status="tripped"),
    "ups_fail": lambda a: a.update(ups_dg_available=False),
    "ir_decline": lambda a: a.update(ir_mohm=60.0, ir_trend_declining=True),
}
PROCESS_FAULTS = {
    "trip_duty_pump": lambda a: a.update(duty_pump_status="trip"),
    "block_pump": lambda a: a.update(pump_discharge_bar=1.0, pump_flow_m3h=15.0),
    "high_level": lambda a: a.update(level_pct=88.0),
}


class UnknownAsset(KeyError):
    pass


class UnknownFault(ValueError):
    pass


def set_rainfall(level: str) -> None:
    if level not in RAINFALL_PRESETS:
        raise ValueError(f"Unknown rainfall level '{level}'")
    with twin.lock():
        twin.rainfall_level = level
        twin.rainfall_mm_hr = RAINFALL_PRESETS[level]


def set_speed(speed: float) -> None:
    simulator.control.set_speed(speed)


def set_paused(paused: bool) -> None:
    simulator.control.set_paused(paused)


def inject_fault(asset_id: str, fault_type: str) -> None:
    with twin.lock():
        if asset_id in twin.electrical:
            asset = twin.electrical[asset_id]
            if fault_type == "clear":
                _reset_electrical(asset)
                return
            fn = ELECTRICAL_FAULTS.get(fault_type)
        elif asset_id in twin.process:
            asset = twin.process[asset_id]
            if fault_type == "clear":
                _reset_process(asset)
                return
            fn = PROCESS_FAULTS.get(fault_type)
        else:
            raise UnknownAsset(asset_id)

        if fn is None:
            raise UnknownFault(fault_type)
        fn(asset)


def _reset_electrical(asset: dict) -> None:
    asset.update(
        water_level_m=0.05, humidity_pct=55.0, water_ingress=False,
        motor_current_pct=62.0, breaker_status="closed", leakage_current_ma=40.0,
        earth_fault_alarm=False, ups_dg_available=True, ir_mohm=480.0,
        ir_trend_declining=False,
    )


def _reset_process(asset: dict) -> None:
    asset.update(
        level_pct=20.0, rate_of_rise_pct_min=0.05, duty_pump_status="on",
        standby_pump_status="off", pump_discharge_bar=3.2, pump_flow_m3h=85.0,
        critical_equipment_available=True,
    )


def reset_all() -> None:
    twin.reset()
    simulator.control.set_speed(10.0)
    simulator.control.set_paused(False)
    storage.reset()
