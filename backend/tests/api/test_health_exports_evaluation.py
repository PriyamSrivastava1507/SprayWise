import csv
import io
import json

from tests.api.test_analyze_endpoint import error_of, post

API = "/api/v1"


# ---------------------------------------------------------------- health

def test_health_fake_model(client):
    body = client.get(f"{API}/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["model"] == {
        "backend": "fake", "model_id": "fake-demo-model", "ready": True, "detail": None,
    }


def test_health_unavailable_model_explains_why(make_client):
    body = make_client("unavailable").get(f"{API}/health").json()
    assert body["status"] == "ok"  # classical still works
    assert body["model"]["ready"] is False and body["model"]["detail"]


# ---------------------------------------------------------------- CSV

def test_csv_export(client):
    scan = post(client, {"grid_rows": "4", "grid_cols": "5"}).json()
    response = client.get(f"{API}/scans/{scan['id']}/export/csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert f"scan_{scan['id']}_classical.csv" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["row", "col", "weed_density", "spray"]
    assert len(rows) == 1 + 4 * 5
    sprayed = {tuple(c) for c in scan["results"][0]["spray_cells"]}
    for r, c, density, spray in rows[1:]:
        assert 0 <= float(density) <= 1
        assert int(spray) == int((int(r), int(c)) in sprayed)


def test_export_picks_requested_method(client):
    scan = post(client, {"mode": "compare"}).json()
    ml = client.get(f"{API}/scans/{scan['id']}/export/csv", params={"method": "ml"})
    assert "_ml-default.csv" in ml.headers["content-disposition"]
    default = client.get(f"{API}/scans/{scan['id']}/export/csv")
    assert "_classical.csv" in default.headers["content-disposition"]  # first ok result


def test_export_errors(make_client, client):
    assert client.get(f"{API}/scans/999/export/csv").status_code == 404
    scan = post(client).json()  # classical only
    response = client.get(f"{API}/scans/{scan['id']}/export/csv", params={"method": "ml"})
    assert response.status_code == 404
    assert error_of(response)["message"] == "No successful result for that method or model."
    assert client.get(f"{API}/scans/{scan['id']}/export/csv", params={"method": "x"}).status_code == 422

    unavailable = make_client("unavailable")
    ml_only = post(unavailable, {"mode": "compare"}).json()
    assert unavailable.get(f"{API}/scans/{ml_only['id']}/export/csv", params={"method": "ml"}).status_code == 404


# ---------------------------------------------------------------- PDF

def test_pdf_export(client):
    scan = post(client, {"field_name": "A <b>&</b> field", "mode": "compare"}).json()
    for method in ("classical", "ml"):
        response = client.get(f"{API}/scans/{scan['id']}/export/pdf", params={"method": method})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF") and len(response.content) > 2000
        expected = "classical" if method == "classical" else "ml-default"
        assert f"scan_{scan['id']}_{expected}.pdf" in response.headers["content-disposition"]


def test_pdf_survives_missing_image_file(client):
    scan = post(client).json()
    client.delete(f"{API}/scans/{scan['id']}")  # scan gone
    assert client.get(f"{API}/scans/{scan['id']}/export/pdf").status_code == 404

    scan = post(client).json()
    import os
    root = client.app.state.settings.storage_dir
    for d, _, files in os.walk(root):
        for f in files:
            os.remove(os.path.join(d, f))
    response = client.get(f"{API}/scans/{scan['id']}/export/pdf")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")


# ---------------------------------------------------------------- evaluation

def test_evaluation_missing_files_are_null(make_client, tmp_path):
    client = make_client(evaluation_dir=str(tmp_path / "none"))
    body = client.get(f"{API}/evaluation").json()
    assert body["classical"] is None and body["ml"] is None and body["ml_training_report"] is None
    assert body["entries"] == [] and body["training_reports"] == {}
    assert body["models"] == [{"key": "default", "label": "ML segmentation"}]


def test_evaluation_reads_files(make_client, tmp_path):
    folder = tmp_path / "eval"
    folder.mkdir()
    (folder / "classical.json").write_text(json.dumps({"method": "classical", "n_images": 20}))
    (folder / "ml.json").write_text("{not json")  # corrupt -> null, not a crash
    client = make_client(evaluation_dir=str(folder))
    body = client.get(f"{API}/evaluation").json()
    assert body["classical"]["n_images"] == 20
    assert body["ml"] is None and body["ml_training_report"] is None


# ---------------------------------------------------------------- additions

def test_health_reports_pressure_thresholds(make_client):
    body = make_client(pressure_low_max=4, pressure_high_min=12).get(f"{API}/health").json()
    assert body["pressure_thresholds"] == {"low_max": 4.0, "high_min": 12.0}


def test_mask_is_served_and_matches_photo(client):
    from io import BytesIO

    import numpy as np
    from PIL import Image

    scan = post(client, {"mode": "ml"}).json()
    result = scan["results"][0]
    mask = np.asarray(Image.open(BytesIO(client.get(result["mask_url"]).content)))
    assert mask.shape == (scan["height"], scan["width"])
    assert set(np.unique(mask)) <= {0, 1, 2}
    weed_pct = (mask == 2).mean() * 100
    assert abs(weed_pct - result["weed_pct"]) < 0.01


def test_savings_has_litres_and_cost(client):
    scan = post(client, {"mode": "ml", "area_ha": "2.5", "dose_l_per_ha": "2", "price_per_l": "450"}).json()
    s = scan["results"][0]["savings"]
    assert s["blanket_litres"] == 5.0
    assert abs(s["spot_litres"] + s["saved_litres"] - 5.0) < 0.011
    assert abs(s["saved_cost"] - (s["blanket_cost"] - s["spot_cost"])) < 0.011


def test_not_ok_result_has_time_but_no_mask(make_client):
    client = make_client("unavailable")
    ml = next(r for r in post(client, {"mode": "compare"}).json()["results"] if r["method"] == "ml")
    assert ml["mask_url"] is None and ml["processing_ms"] is not None
    assert ml["savings"] == {k: None for k in ml["savings"]}


def test_old_database_gets_mask_column(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text

    from app.core import database

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE scan_results (id INTEGER PRIMARY KEY, scan_id INTEGER)"))
    monkeypatch.setattr(database, "engine", engine)
    database._add_missing_columns()
    assert "mask_key" in {c["name"] for c in inspect(engine).get_columns("scan_results")}
