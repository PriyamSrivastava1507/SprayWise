# SprayWise backend

FastAPI service for crop/weed analysis and spot-spraying savings. Layers:
`api/` (controllers) → `services/` → `repositories/` → SQLite, plus `clients/`
(photo storage, ML model) and `engine/` (pure classical CV, no app imports).

## Run it

```bash
cd backend
uv sync                      # Python 3.10+
cp .env.example .env         # defaults work as they are
uv run uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs> for the interactive API. The first start
creates `data/spraywise.db` and `data/media/`.

Docker: `docker build -t spraywise-backend . && docker run -p 8000:8000 -v spraywise-data:/app/data spraywise-backend`

## Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `SEGMENTATION_BACKEND` | `fake` | `fake` demo mask · `unavailable` ML reports off · `hf` real model |
| `HF_MODEL_ID` / `HF_TOKEN` | – | Hub id or local folder of the SegFormer model (hf only) |
| `DATABASE_URL` | `sqlite:///./data/spraywise.db` | |
| `STORAGE_DIR` | `./data/media` | photos and overlays |
| `EVALUATION_DIR` | `./data/evaluation` | JSON written by `scripts/evaluate.py` |
| `MAX_UPLOAD_MB` | `10` | larger uploads get 413 |
| `WORKING_WIDTH` | `1024` | photos are shrunk to this width |
| `PRESSURE_LOW_MAX` / `PRESSURE_HIGH_MIN` | `5` / `15` | weed % limits for Low / Medium / High |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | CORS, JSON list |
| `LOG_LEVEL` | `INFO` | |

## Endpoints (base `/api/v1`)

| | |
|---|---|
| `GET /health` | database + model status |
| `POST /analyze` | multipart: `file`, `mode` (classical/ml/compare), `field_id` or `field_name`, `area_ha`, `dose_l_per_ha`, `price_per_l`, `grid_rows`, `grid_cols`, `cell_threshold` → 201 scan |
| `GET /scans`, `GET /scans/{id}`, `DELETE /scans/{id}` | history (`field_id`, `limit`, `offset`) |
| `GET/POST /fields`, `GET /fields/{id}`, `GET /fields/{id}/trend?method=` | fields and weed trend |
| `POST /scans/{id}/recalculate?save=` | JSON `area_ha`, `dose_l_per_ha`, `price_per_l`, `grid_rows`, `grid_cols`, `cell_threshold` → the scan recalculated from its saved masks; `save=false` previews, `save=true` updates it (409 if it has no saved mask) |
| `GET /scans/{id}/export/csv\|pdf?method=` | downloads |
| `GET /evaluation` | stored metrics, `null` when not evaluated yet |
| `GET /media/...` | original photos and overlays (outside `/api/v1`) |

**Conventions the frontend can rely on**

- Errors are always `{"error": {"code", "message"}}` (`invalid_image` 422, `file_too_large` 413, `not_found` 404, `model_unavailable` 503, `validation_error` 422, `conflict` 409, `internal_error` 500). Every response has an `X-Request-ID` header.
- A scan has one result per method. Look at each result's `status`: `ok`, `rows_not_detected` (see `status_detail`), `model_unavailable`, `failed`. When it is not `ok`, the numbers are `null`; the `savings` object is always present (`blanket_litres`, `spot_litres`, `saved_litres`, `blanket_cost`, `spot_cost`, `saved_cost`, `saved_pct`).
- `overlay_url` is the finished picture (crop green, weeds red). `mask_url` is a greyscale PNG the same size as the photo whose pixel values are the classes (0 soil, 1 crop, 2 weed), for drawing layers separately. Both are `null` when the result is not `ok`.
- `/health` also returns `pressure_thresholds` (`low_max`, `high_min`), the weed % limits behind Low / Medium / High.
- Percentages are 0–100; grid densities and `cell_threshold` are fractions 0–1. Times are UTC ISO 8601 ending in `Z`.
- `model_id == "fake-demo-model"` means the ML result is a placeholder: show it as a demo.
- In `compare` mode, a failing method never hides the other: the response is 201 with both results.
- `ml` mode with no model is a 503; `compare` returns the classical result and marks ML `model_unavailable`.

## Several ML models

Set `ML_MODELS` (a JSON list) and `DEFAULT_ML_MODEL` in `.env`:

```
ML_MODELS=[{"key":"cwfid","label":"ML (CWFID)","path":"./models/segformer-cwfid"},{"key":"we3ds","label":"ML (WE3DS)","path":"./models/segformer-we3ds"}]
DEFAULT_ML_MODEL=cwfid
```

- Each model loads on its own: one that fails is reported offline (with the
  reason in `/health` and `/models`) and the others keep working.
- `POST /analyze` takes `models=cwfid,we3ds`. `ml` mode runs the chosen models
  (the default model if none); `compare` runs classical plus the chosen models.
  With several runs, one that fails is marked in its result and the rest are
  returned (201). `ml` mode where none of the chosen models works is 503.
- Results carry `model_key` and `model_label`. Exports take `?model=`
  (`scan_7_ml-we3ds.pdf`), the trend takes `?model=` (default model if empty).
- `GET /models` lists the models; `/health` has them under `models`.
- Model folders hold `*.safetensors`, which the root `.gitignore` excludes:
  share them outside git, or with `git add -f`, Git LFS or the Hugging Face Hub.
- Without `ML_MODELS` everything works as before, with one model under the key
  `default`.

Evaluate each model on each test set and name the files
`<variant>__<test-set>.json`; `/evaluation` lists them all:

```bash
python -m scripts.evaluate ../test-dataset/images ../test-dataset/masks --model we3ds \
    --dataset "CWFID shared test set" --out data/evaluation/ml-we3ds__cwfid-test.json
```

A training report from the ML team goes in `data/evaluation/training_<key>.json`.

Database: results gained `model_key`. A database made by an older version is
rebuilt automatically at startup when it has no scans; if it has scans, the
app stops with a message (delete `data/spraywise.db` and `data/media/`).

## When the real ML model arrives

```bash
uv add torch transformers
RUN_ML_TESTS=1 HF_MODEL_ID=<id-or-folder> uv run pytest tests/contracts   # mask format check
# then in .env:  SEGMENTATION_BACKEND=hf   HF_MODEL_ID=...
```

If the model fails to load the app still starts, ML reports unavailable, and
`/health` says why.

## Evaluation

```bash
uv run python -m scripts.evaluate ../test-dataset/images ../test-dataset/masks \
    --dataset "CWFID shared test set" --out data/evaluation/classical.json
```

Read `rows_detected_rate` together with the metrics: images where the classical
method finds no crop rows are counted separately, never as correct. For the ML
method call `scripts.evaluate.evaluate()` with the client's `predict`, and save
as `data/evaluation/ml.json`. Evaluation results are git-ignored.

## Tests

```bash
uv run pytest            # ML tests are skipped unless RUN_ML_TESTS=1 and torch is installed
```
