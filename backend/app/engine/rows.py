"""Crop-row detection and crop/weed separation from a vegetation mask."""

import math
from dataclasses import dataclass
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from .constants import CROP, SOIL, WEED
from .engine_types import BinaryMask, LabelMask
from .params import DEFAULT_PARAMS, ClassicalParams

# Type aliases
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]

# Point sampling for the row search
MIN_VEGETATION_PIXELS = 200
MAX_SAMPLED_POINTS = 40_000
RNG_SEED = 0  # fixed seed = reproducible results
JITTER = 0.5  # sub-pixel jitter (pixels) that removes resampling artefacts

# Angle search
COARSE_ANGLE_MIN = -90.0
COARSE_ANGLE_MAX = 90.0
ANGLE_WRAP = 180.0  # row directions repeat every 180 degrees
ANGLE_REFINE_STEP = 0.5
N_CANDIDATES = 4
MIN_CANDIDATE_SEPARATION = 15.0

# Projection profile
EDGE_MARGIN = 20  # ignore the image-edge ramps at both ends of the projection
SCORE_BLUR_SIGMA = 12.0
PROFILE_BLUR_SIGMA = 1.5
MIN_PROFILE_LENGTH = 24

# Row spacing and regularity (autocorrelation)
AUTOCORR_PROMINENCE = 0.05
MIN_LAG = 6
FIRST_PEAK_FRACTION = 0.6
EPS = 1e-9

# Row centres (lattice fit)
PEAK_DISTANCE_FRACTION = 0.6
MIN_PEAK_DISTANCE = 2
PEAK_PROMINENCE_FRACTION = 0.15
MIN_PEAKS_FOR_FIT = 2
SPACING_TOLERANCE = 0.2
LATTICE_TOLERANCE = 0.25
LATTICE_MIN_FIT = 0.8

# Choosing between candidate angles
STRONG_PERIODICITY = 0.70

# Crop / weed decision
MIN_IN_BAND_FRACTION = 0.5


@dataclass(frozen=True, eq=False)
class RowModel:
    """Geometry of the detected crop rows."""

    angle_deg: float  # direction of the cross-row axis (0 = rows run top to bottom)
    centers: FloatArray  # row centres along that axis (full-res px, from image centre)
    spacing: float  # distance between neighbouring rows, full-resolution px
    periodicity: float  # 0..1, how regular the row pattern is
    cx: float  # image centre: origin of the cross-row coordinate
    cy: float


@dataclass(frozen=True, eq=False)
class _PointCloud:
    """Vegetation pixel positions in the reduced working frame (centred)."""

    x: FloatArray
    y: FloatArray
    scale: float
    span: int  # longest possible projection length
    cx: float  # full-resolution image centre
    cy: float


@dataclass(frozen=True)
class _Rejection:
    """Why a candidate angle (or the whole search) was rejected."""

    info: dict[str, object]


@dataclass(frozen=True)
class _Lag:
    lag: int
    periodicity: float


@dataclass(frozen=True, eq=False)
class _Lattice:
    spacing: float
    centers: FloatArray  # in profile-index units


def _reject(reason: str, **details: object) -> _Rejection:
    return _Rejection({"reason": reason, **details})


def _smooth(values: FloatArray, sigma: float) -> FloatArray:
    """Gaussian-smooth a 1-D signal (keeps scipy's typing out of the callers)."""
    return np.asarray(gaussian_filter1d(values, sigma=sigma), dtype=np.float64)


def _find_peaks(
    signal: FloatArray,
    *,
    distance: float | None = None,
    prominence: float | None = None,
) -> IntArray:
    """Return the indices of the peaks in a 1-D signal."""
    result = find_peaks(signal, distance=distance, prominence=prominence)

    return np.asarray(result[0], dtype=np.intp)


def _cross_row_coordinate(
    xs: FloatArray,
    ys: FloatArray,
    cx: float,
    cy: float,
    angle_deg: float,
) -> FloatArray:
    """Signed distance of each point along the axis perpendicular to the rows."""
    angle = math.radians(angle_deg)

    return (xs - cx) * math.cos(angle) + (ys - cy) * math.sin(angle)


def _angular_gap(a: float, b: float) -> float:
    """Smallest difference between two angles that wrap at 180 degrees."""
    diff = abs(a - b)

    return min(diff, ANGLE_WRAP - diff)


def _sample_points(
    veg: BinaryMask,
    p: ClassicalParams,
) -> _PointCloud | None:
    """
    Turn the vegetation mask into a cloud of pixel positions.

    The row search works on positions (scaled, with sub-pixel jitter), not on
    a down-sampled mask: resampling a mask creates a regular column pattern
    that looks like periodic rows along the exact image axes.
    """
    height, width = veg.shape
    scale = min(1.0, p.work_width / width)

    ys, xs = np.nonzero(veg > 0)

    if len(xs) < MIN_VEGETATION_PIXELS:
        return None

    rng = np.random.default_rng(RNG_SEED)

    if len(xs) > MAX_SAMPLED_POINTS:
        selected = rng.choice(len(xs), MAX_SAMPLED_POINTS, replace=False)
        xs, ys = xs[selected], ys[selected]

    x = (xs + rng.uniform(-JITTER, JITTER, len(xs)) - (width - 1) / 2.0) * scale
    y = (ys + rng.uniform(-JITTER, JITTER, len(ys)) - (height - 1) / 2.0) * scale

    return _PointCloud(
        x=x,
        y=y,
        scale=scale,
        span=math.ceil(math.hypot(height, width) * scale),
        cx=(width - 1) / 2.0,
        cy=(height - 1) / 2.0,
    )


def _project(
    cloud: _PointCloud,
    angle: float,
) -> tuple[float, IntArray]:
    """
    Histogram the cross-row coordinate of every vegetation point.

    Returns the spikiness score of the histogram and the histogram itself.
    Rows make the projection spiky, so the score is its high-frequency
    energy. A plain sum of squares would instead favour whichever direction
    has the shortest image extent, regardless of rows.
    """
    u = _cross_row_coordinate(cloud.x, cloud.y, 0.0, 0.0, angle)

    indices = (u + cloud.span / 2.0).round().astype(np.intp)
    hist: IntArray = np.bincount(indices, minlength=cloud.span + 2)

    occupied = np.nonzero(hist)[0]
    start = int(occupied[0]) + EDGE_MARGIN
    stop = int(occupied[-1]) - EDGE_MARGIN

    if stop <= start:
        return 0.0, hist

    values = hist.astype(np.float64)
    blurred = _smooth(values, SCORE_BLUR_SIGMA)
    high_pass = values - blurred
    energy = float((high_pass[start : stop + 1] ** 2).sum()) / len(cloud.x)

    return energy, hist


def _candidate_angles(
    cloud: _PointCloud,
    p: ClassicalParams,
) -> list[float]:
    """Pick the few directions where the projection is spikiest."""
    coarse: FloatArray = np.arange(
        COARSE_ANGLE_MIN,
        COARSE_ANGLE_MAX,
        p.angle_step,
        dtype=np.float64,
    )
    scores = np.array([_project(cloud, float(a))[0] for a in coarse])

    candidates: list[float] = []

    for index in np.argsort(-scores):
        angle = float(coarse[index])

        if all(
            _angular_gap(angle, other) >= MIN_CANDIDATE_SEPARATION
            for other in candidates
        ):
            candidates.append(angle)

        if len(candidates) == N_CANDIDATES:
            break

    return candidates


def _refine_angle(
    cloud: _PointCloud,
    angle: float,
    p: ClassicalParams,
) -> float:
    """Search around a coarse angle in finer steps."""
    fine: FloatArray = np.arange(
        angle - p.angle_step,
        angle + p.angle_step + EPS,
        ANGLE_REFINE_STEP,
        dtype=np.float64,
    )
    scores = [_project(cloud, float(a))[0] for a in fine]

    return float(fine[int(np.argmax(scores))])


def _find_lag(
    profile: FloatArray,
    angle: float,
    p: ClassicalParams,
) -> _Lag | _Rejection:
    """
    Find the row spacing and regularity from the profile's autocorrelation.

    The first strong autocorrelation peak gives the spacing (in profile
    units) and its height is the periodicity.
    """
    centred = profile - profile.mean()
    full: FloatArray = np.correlate(centred, centred, mode="full")
    autocorr = full[len(centred) - 1 :] / (centred @ centred + EPS)

    found = _find_peaks(
        autocorr[: len(centred) // 2],
        prominence=AUTOCORR_PROMINENCE,
    )
    peaks = found[found >= MIN_LAG]

    if len(peaks) == 0:
        return _reject("no_periodicity", angle=angle)

    heights = autocorr[peaks]

    # A peak that is not positive means no real periodicity. Without this
    # guard the threshold below can exceed every peak and `strong` is empty.
    if heights.max() <= 0:
        return _reject("no_periodicity", angle=angle)

    # The first strong peak is the spacing (this skips small noise bumps).
    strong = np.nonzero(heights >= FIRST_PEAK_FRACTION * heights.max())[0]
    lag = int(peaks[strong[0]])
    periodicity = float(autocorr[lag])

    if periodicity < p.min_periodicity:
        return _reject(
            "weak_periodicity",
            periodicity=round(periodicity, 3),
            angle=angle,
        )

    return _Lag(lag=lag, periodicity=periodicity)


def _fit_lattice(
    profile: FloatArray,
    lag: int,
    angle: float,
    p: ClassicalParams,
) -> _Lattice | _Rejection:
    """
    Fit a regular lattice through the profile's row peaks.

    Fitting ``centre = origin + k * spacing`` fills in rows that are sparse
    or missing, and rejects patterns whose peaks do not sit on a lattice.
    """
    peaks = _find_peaks(
        profile,
        distance=max(MIN_PEAK_DISTANCE, int(PEAK_DISTANCE_FRACTION * lag)),
        prominence=PEAK_PROMINENCE_FRACTION * float(profile.max()),
    )

    if len(peaks) < max(p.min_rows, MIN_PEAKS_FOR_FIT):
        return _reject("too_few_peaks", n_peaks=len(peaks), angle=angle)

    positions = peaks.astype(np.float64)
    rough_step = float(np.median(positions[1:] - positions[:-1]))
    index = ((positions - positions[0]) / rough_step).round()

    # Least-squares line through (index, position): slope = spacing.
    index_centred = index - index.mean()
    variance = float(index_centred @ index_centred)
    step = (
        float(index_centred @ (positions - positions.mean())) / variance
        if variance > 0
        else 0.0
    )
    origin = float(positions.mean()) - step * float(index.mean())

    if step <= 0 or abs(step - rough_step) / rough_step > SPACING_TOLERANCE:
        step, origin = rough_step, float(positions[0])

    on_lattice = np.abs(positions - (origin + index * step)) / step < LATTICE_TOLERANCE

    if float(on_lattice.mean()) < LATTICE_MIN_FIT:
        # Peaks are not on a regular lattice: not crop rows.
        return _reject("irregular_peaks", angle=angle)

    first = math.floor(-origin / step) - 1
    last = math.ceil((len(profile) - 1 - origin) / step) + 2
    ks: FloatArray = np.arange(first, last, dtype=np.float64)

    lattice = origin + ks * step
    lattice = lattice[(lattice >= -step / 2) & (lattice <= len(profile) - 1 + step / 2)]

    if len(lattice) < p.min_rows:
        return _reject("too_few_rows_in_lattice", angle=angle)

    return _Lattice(spacing=step, centers=lattice)


def _analyze_angle(
    cloud: _PointCloud,
    angle: float,
    p: ClassicalParams,
) -> RowModel | _Rejection:
    """Validate one candidate angle and build a row model from it."""
    _, hist = _project(cloud, angle)

    occupied = np.nonzero(hist)[0]
    low, high = int(occupied[0]), int(occupied[-1])
    profile = _smooth(
        hist[low : high + 1].astype(np.float64),
        PROFILE_BLUR_SIGMA,
    )

    if len(profile) < MIN_PROFILE_LENGTH:
        return _reject("profile_too_short")

    lag = _find_lag(profile, angle, p)
    if isinstance(lag, _Rejection):
        return lag

    lattice = _fit_lattice(profile, lag.lag, angle, p)
    if isinstance(lattice, _Rejection):
        return lattice

    # Back to the projection axis (reduced frame), then to full resolution.
    centers_small = lattice.centers + low - cloud.span / 2.0

    return RowModel(
        angle_deg=angle,
        centers=np.sort(centers_small / cloud.scale),
        spacing=lattice.spacing / cloud.scale,
        periodicity=lag.periodicity,
        cx=cloud.cx,
        cy=cloud.cy,
    )


def _select_model(models: list[RowModel]) -> RowModel:
    """
    Choose between several valid row models.

    A grid of plants also looks periodic ACROSS the rows, so several
    candidates can pass. Among clearly regular ones we keep the widest
    spacing (in-row plants sit closer together than the rows themselves);
    weakly regular candidates only win if nothing better exists.
    """
    strong = [m for m in models if m.periodicity >= STRONG_PERIODICITY]

    if strong:
        return max(strong, key=lambda m: m.spacing)

    return max(models, key=lambda m: m.periodicity)


def estimate_rows(
    veg: BinaryMask,
    p: ClassicalParams = DEFAULT_PARAMS,
    diag: dict[str, object] | None = None,
) -> RowModel | None:
    """
    Find crop-row direction, spacing and centres from a vegetation mask.

    Returns a RowModel, or None when no regular rows are found. If a dict is
    passed as ``diag``, the reason for a None result is stored in
    ``diag["reason"]`` (useful for tuning).
    """
    cloud = _sample_points(veg, p)

    if cloud is None:
        if diag is not None:
            diag.update(reason="too_little_vegetation")
        return None

    models: list[RowModel] = []
    first_rejection: _Rejection | None = None

    for coarse_angle in _candidate_angles(cloud, p):
        angle = _refine_angle(cloud, coarse_angle, p)
        result = _analyze_angle(cloud, angle, p)

        if isinstance(result, _Rejection):
            if first_rejection is None:
                first_rejection = result
        else:
            models.append(result)

    if not models:
        if diag is not None:
            diag.update(
                first_rejection.info
                if first_rejection is not None
                else {"reason": "no_candidate"},
            )
        return None

    return _select_model(models)


def split_crop_weed(
    veg: BinaryMask,
    model: RowModel,
    p: ClassicalParams = DEFAULT_PARAMS,
) -> LabelMask:
    """
    Label each vegetation blob as crop or weed.

    Works from geometry only (each pixel's distance to the nearest row
    centre), so no image is rotated and there are no interpolation artefacts.

    Returns:
        uint8 mask: 0 soil, 1 crop, 2 weed

    """
    foreground = veg > 0
    ys, xs = np.nonzero(foreground)

    if len(xs) == 0:
        return np.zeros(veg.shape, dtype=np.uint8)

    u = _cross_row_coordinate(
        xs.astype(np.float64),
        ys.astype(np.float64),
        model.cx,
        model.cy,
        model.angle_deg,
    )

    # Distance from each pixel to the nearest row centre.
    centers = model.centers
    right = centers.searchsorted(u).clip(0, len(centers) - 1)
    left = (right - 1).clip(0, len(centers) - 1)
    distance = np.minimum(
        np.abs(u - centers[left]),
        np.abs(u - centers[right]),
    )
    in_band = distance <= p.band_frac * model.spacing

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        foreground.astype(np.uint8),
        connectivity=8,
    )
    labels = cast("NDArray[np.int32]", labels)
    stats = cast("NDArray[np.int32]", stats)

    pixel_labels = labels[ys, xs]
    total = np.bincount(pixel_labels, minlength=count).astype(np.float64)
    in_band_count = np.bincount(
        pixel_labels,
        weights=in_band.astype(np.float64),
        minlength=count,
    )

    # A blob that lies mostly inside a row band is a crop candidate.
    blob_in_band = (in_band_count / np.maximum(total, 1)) >= MIN_IN_BAND_FRACTION
    blob_in_band[0] = False  # label 0 is the background

    area = stats[:, cv2.CC_STAT_AREA].astype(np.float64)
    reference = float(np.median(area[blob_in_band])) if blob_in_band.any() else 0.0

    # Big in-band blobs are crop; everything else is weed.
    classes = np.full(count, WEED, dtype=np.uint8)
    classes[0] = SOIL
    classes[blob_in_band & (area >= p.small_frac * reference)] = CROP

    return classes[labels]
