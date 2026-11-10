"""
Run the classical engine over a folder of photos and save debug images.

For every photo it writes ``<name>_veg.png`` (vegetation white on black, check
this first) and, when crop rows were found, ``<name>_overlay.png``. It also
prints one JSON line of diagnostics per photo.

Run it from ``backend/``::

    python -m scripts.debug_folder my_photos debug_out
    python -m scripts.debug_folder my_photos debug_out --min-exg 0.08

The flags override ClassicalParams for this run only. Once you have settled on
values, write them in ``app/engine/params.py``.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path

from PIL import Image

from app.engine import (
    DEFAULT_PARAMS,
    ClassicalParams,
    analyze_grid,
    classical_segment_with_info,
    render_overlay,
    vegetation_mask,
)

from .common import DEFAULT_WIDTH, list_images, load_rgb

# Grid used only to report crop/weed percentages.
GRID_ROWS = 8
GRID_COLS = 8
GRID_THRESHOLD = 0.10

ROUND_DIGITS = 3


def _build_params(args: argparse.Namespace) -> ClassicalParams:
    """Start from DEFAULT_PARAMS and apply only the flags that were given."""
    d = DEFAULT_PARAMS

    return replace(
        d,
        min_exg=d.min_exg if args.min_exg is None else args.min_exg,
        min_periodicity=(
            d.min_periodicity if args.min_periodicity is None else args.min_periodicity
        ),
        band_frac=d.band_frac if args.band_frac is None else args.band_frac,
        small_frac=d.small_frac if args.small_frac is None else args.small_frac,
        use_hsv=d.use_hsv or args.use_hsv,
    )


def _rounded(record: dict[str, object]) -> dict[str, object]:
    return {
        key: round(value, ROUND_DIGITS) if isinstance(value, float) else value
        for key, value in record.items()
    }


def debug_folder(
    folder: Path,
    out_dir: Path,
    width: int = DEFAULT_WIDTH,
    params: ClassicalParams = DEFAULT_PARAMS,
) -> list[dict[str, object]]:
    """Process every photo in ``folder`` and return the diagnostics records."""
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    for path in list_images(folder):
        rgb = load_rgb(path, width)

        # Check this mask first: nothing downstream is right if it is wrong.
        veg = vegetation_mask(rgb, params)
        Image.fromarray(veg).save(out_dir / f"{path.stem}_veg.png")

        mask, info = classical_segment_with_info(rgb, params)
        record: dict[str, object] = {"file": path.name, **info}

        if mask is not None:
            overlay = render_overlay(rgb, mask)
            (out_dir / f"{path.stem}_overlay.png").write_bytes(overlay)

            grid = analyze_grid(mask, GRID_ROWS, GRID_COLS, GRID_THRESHOLD)
            record["crop_pct"] = grid.crop_pct
            record["weed_pct"] = grid.weed_pct

        records.append(record)
        print(json.dumps(_rounded(record)))

    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the classical engine on a folder of photos.",
    )
    parser.add_argument("folder", type=Path, help="folder with .jpg/.png photos")
    parser.add_argument(
        "out",
        type=Path,
        nargs="?",
        default=Path("debug_out"),
        help="output folder (default: debug_out)",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--min-exg", type=float, help="vegetation threshold floor")
    parser.add_argument("--min-periodicity", type=float, help="row regularity (0..1)")
    parser.add_argument("--band-frac", type=float, help="crop band half-width")
    parser.add_argument("--small-frac", type=float, help="smallest crop blob size")
    parser.add_argument("--use-hsv", action="store_true", help="add the HSV filter")
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        parser.error(f"not a folder: {args.folder}")

    params = _build_params(args)
    print(f"params: {json.dumps(asdict(params))}", file=sys.stderr)

    records = debug_folder(args.folder, args.out, args.width, params)

    if not records:
        print(f"no .jpg/.jpeg/.png photos found in {args.folder}", file=sys.stderr)
        return 1

    found = sum(1 for record in records if record["rows_detected"])
    print(
        f"rows found in {found} of {len(records)} photos; images in {args.out}",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
