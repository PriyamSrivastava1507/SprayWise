from dataclasses import dataclass


@dataclass(frozen=True)
class ClassicalParams:
    # Vegetation detection
    min_exg: float = 0.05
    use_hsv: bool = False
    open_kernel: int = 3
    min_area_frac: float = 1e-5

    # Row detection
    work_width: int = 400
    angle_step: float = 2.0
    min_rows: int = 3
    min_periodicity: float = 0.60

    # Crop vs weed classification
    band_frac: float = 0.30
    small_frac: float = 0.25


DEFAULT_PARAMS = ClassicalParams()
