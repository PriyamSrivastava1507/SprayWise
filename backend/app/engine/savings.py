"""Spot-spraying savings and weed-pressure level."""

from typing import Literal, TypedDict

PressureLevel = Literal["Low", "Medium", "High"]


class Savings(TypedDict):
    blanket_cost: float
    spot_cost: float
    saved_litres: float
    saved_pct: float


def compute_savings(
    area_ha: float,
    dose_l_per_ha: float,
    price_per_l: float,
    spray_fraction: float,
) -> Savings:
    """
    Compare blanket spraying with spot spraying.

    Blanket spraying treats the whole field; spot spraying treats only the
    flagged fraction of it. Cost is assumed to scale with that fraction
    (nozzle overlap and equipment limits are ignored).
    """
    blanket_litres = area_ha * dose_l_per_ha
    blanket_cost = blanket_litres * price_per_l
    spot_cost = blanket_cost * spray_fraction

    return {
        "blanket_cost": round(blanket_cost, 2),
        "spot_cost": round(spot_cost, 2),
        "saved_litres": round(blanket_litres * (1.0 - spray_fraction), 2),
        "saved_pct": round((1.0 - spray_fraction) * 100.0, 2),
    }


def pressure_level(
    weed_pct: float,
    low_max: float,
    high_min: float,
) -> PressureLevel:
    """
    Classify weed cover (share of the image, in percent).

    The thresholds are adjustable placeholders, not agronomic standards.
    """
    if weed_pct < low_max:
        return "Low"

    if weed_pct >= high_min:
        return "High"

    return "Medium"
