"""Two ML models side by side (ML_MODELS). Fake models need no torch: the
first marks the right half of the vegetation as weed, the second the left."""

import json
import os

import pytest

from tests.api.test_analyze_endpoint import error_of, post

API = "/api/v1"
TWO = [
    {"key": "cwfid", "label": "ML (CWFID)", "backend": "fake"},
    {"key": "we3ds", "label": "ML (WE3DS)", "backend": "fake"},
]


@pytest.fixture
def two(make_client):
    return make_client(ml_models=TWO, default_ml_model="cwfid")


def results(scan):
    return {(r["method"], r["model_key"]): r for r in scan["results"]}


def test_health_and_models_list(two):
    body = two.get(f"{API}/health").json()
    assert [(m["key"], m["label"], m["default"], m["ready"]) for m in body["models"]] == [
        ("cwfid", "ML (CWFID)", True, True), ("we3ds", "ML (WE3DS)", False, True)]
    assert body["model"]["ready"] is True  # the default model, for older clients
    assert [m["key"] for m in two.get(f"{API}/models").json()] == ["cwfid", "we3ds"]


def test_ml_with_both_models(two):
    response = post(two, {"mode": "ml", "models": "cwfid,we3ds"})
    assert response.status_code == 201
    r = results(response.json())
    assert set(r) == {("ml", "cwfid"), ("ml", "we3ds")}
    assert r[("ml", "cwfid")]["model_label"] == "ML (CWFID)"
    assert r[("ml", "cwfid")]["weed_pct"] != r[("ml", "we3ds")]["weed_pct"]  # different models, different masks
    assert r[("ml", "cwfid")]["mask_url"] != r[("ml", "we3ds")]["mask_url"]


def test_default_model_when_none_chosen(two):
    scan = post(two, {"mode": "ml"}).json()
    assert [(r["model_key"], r["model_label"]) for r in scan["results"]] == [("cwfid", "ML (CWFID)")]


def test_compare_runs_classical_and_chosen_models(two):
    scan = post(two, {"mode": "compare", "models": "we3ds,cwfid"}).json()
    assert [(r["method"], r["model_key"]) for r in scan["results"]] == [
        ("classical", None), ("ml", "we3ds"), ("ml", "cwfid")]
    assert scan["results"][0]["model_label"] is None


def test_blank_and_repeated_keys(two):
    scan = post(two, {"mode": "ml", "models": " we3ds, ,we3ds "}).json()
    assert [r["model_key"] for r in scan["results"]] == ["we3ds"]
    assert post(two, {"mode": "ml", "models": ""}).json()["results"][0]["model_key"] == "cwfid"


def test_unknown_model_is_validation_error(two):
    response = post(two, {"mode": "ml", "models": "cwfid,nope"})
    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "validation_error" and "nope" in error["message"] and "we3ds" in error["message"]


def test_one_model_offline(make_client):
    client = make_client(ml_models=[TWO[0], {"key": "off", "label": "Offline", "backend": "unavailable"}])
    partial = post(client, {"mode": "ml", "models": "cwfid,off"})
    assert partial.status_code == 201
    r = results(partial.json())
    assert r[("ml", "cwfid")]["status"] == "ok"
    assert r[("ml", "off")]["status"] == "model_unavailable" and r[("ml", "off")]["status_detail"]
    only_off = post(client, {"mode": "ml", "models": "off"})
    assert only_off.status_code == 503 and "Offline" in error_of(only_off)["message"]
    health = client.get(f"{API}/health").json()
    assert [m["ready"] for m in health["models"]] == [True, False]


def test_model_that_cannot_load_does_not_stop_the_other(make_client):
    client = make_client(ml_models=[{"key": "broken", "label": "Broken", "backend": "hf", "path": "/no/such/model"}, TWO[1]],
                         default_ml_model="we3ds")
    models = {m["key"]: m for m in client.get(f"{API}/models").json()}
    assert models["broken"]["ready"] is False and models["broken"]["detail"]
    assert models["we3ds"]["ready"] is True
    assert post(client, {"mode": "ml"}).json()["results"][0]["status"] == "ok"


def test_exports_per_model(two):
    scan = post(two, {"mode": "compare", "models": "cwfid,we3ds"}).json()
    sid = scan["id"]
    csv = two.get(f"{API}/scans/{sid}/export/csv", params={"method": "ml", "model": "we3ds"})
    assert csv.status_code == 200 and f"scan_{sid}_ml-we3ds.csv" in csv.headers["content-disposition"]
    pdf = two.get(f"{API}/scans/{sid}/export/pdf", params={"model": "cwfid"})
    assert pdf.content.startswith(b"%PDF") and f"scan_{sid}_ml-cwfid.pdf" in pdf.headers["content-disposition"]
    assert two.get(f"{API}/scans/{sid}/export/csv", params={"model": "nope"}).status_code == 404


def test_trend_per_model(two):
    field = post(two, {"mode": "ml", "models": "cwfid,we3ds", "field_name": "N"}).json()["field"]["id"]
    post(two, {"mode": "ml", "models": "we3ds", "field_name": "N"})
    we3ds = two.get(f"{API}/fields/{field}/trend", params={"method": "ml", "model": "we3ds"}).json()
    cwfid = two.get(f"{API}/fields/{field}/trend", params={"method": "ml"}).json()  # default model
    assert len(we3ds["points"]) == 2 and we3ds["model_label"] == "ML (WE3DS)"
    assert len(cwfid["points"]) == 1 and cwfid["model_key"] == "cwfid"
    bad = two.get(f"{API}/fields/{field}/trend", params={"method": "ml", "model": "nope"})
    assert bad.status_code == 422 and error_of(bad)["code"] == "validation_error"
    classical = two.get(f"{API}/fields/{field}/trend").json()
    assert classical["model_key"] is None


def test_recalculate_all_models(two):
    scan = post(two, {"mode": "ml", "models": "cwfid,we3ds"}).json()
    body = {"area_ha": 1, "dose_l_per_ha": 2, "price_per_l": 10, "grid_rows": 3, "grid_cols": 3, "cell_threshold": 0.2}
    out = two.post(f"{API}/scans/{scan['id']}/recalculate", json=body).json()
    assert all(len(r["grid"]) == 3 and r["model_label"] for r in out["results"])


def test_delete_removes_every_models_files(two):
    root = two.app.state.settings.storage_dir
    count = lambda: sum(len(f) for _, _, f in os.walk(root))  # noqa: E731
    scan = post(two, {"mode": "compare", "models": "cwfid,we3ds"}).json()
    assert count() == 1 + 3 * 2  # original + overlay and mask per successful result
    two.delete(f"{API}/scans/{scan['id']}")
    assert count() == 0


def test_evaluation_per_model_and_test_set(make_client, tmp_path):
    folder = tmp_path / "eval"
    folder.mkdir()
    write = lambda name, data: (folder / name).write_text(json.dumps(data))  # noqa: E731
    write("classical__cwfid-test.json", {"method": "classical", "dataset": "CWFID test", "n_images": 20, "n_evaluated": 0})
    write("ml-we3ds__cwfid-test.json", {"method": "ml", "dataset": "CWFID test", "n_images": 20, "n_evaluated": 20})
    write("ml-we3ds__we3ds-test.json", {"method": "ml", "n_images": 30, "n_evaluated": 30})
    write("training_we3ds.json", {"val_miou": 0.71})
    write("ml-cwfid__broken.json", "not a dict")
    client = make_client(ml_models=TWO, evaluation_dir=str(folder))
    body = client.get(f"{API}/evaluation").json()
    got = {(e["variant"], e["dataset"], e["label"]) for e in body["entries"]}
    assert got == {
        ("classical", "CWFID test", "Classical"),
        ("ml-we3ds", "CWFID test", "ML (WE3DS)"),
        ("ml-we3ds", "we3ds-test", "ML (WE3DS)"),  # no dataset inside: the file name is used
    }
    assert body["training_reports"] == {"we3ds": {"val_miou": 0.71}}
    assert [m["key"] for m in body["models"]] == ["cwfid", "we3ds"]


def test_settings_validation():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(ml_models=[TWO[0], TWO[0]])
    with pytest.raises(ValueError):
        Settings(ml_models=TWO, default_ml_model="missing")
    with pytest.raises(ValueError):
        Settings(ml_models=[{"key": "Bad Key", "label": "x"}])
    assert Settings(ml_models=TWO).default_model_key() == "cwfid"
    assert Settings().model_specs()[0].key == "default"  # older single-model settings still work


def test_outdated_database_is_rebuilt_only_when_empty(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text

    from app.core import database

    def old_db(name, with_scan):
        engine = create_engine(f"sqlite:///{tmp_path / name}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE scans (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE scan_results (id INTEGER PRIMARY KEY, scan_id INTEGER, method VARCHAR)"))
            if with_scan:
                conn.execute(text("INSERT INTO scans (id) VALUES (1)"))
        return engine

    empty = old_db("empty.db", False)
    monkeypatch.setattr(database, "engine", empty)
    database._reset_if_outdated()
    database.Base.metadata.create_all(empty)
    assert "model_key" in {c["name"] for c in inspect(empty).get_columns("scan_results")}

    used = old_db("used.db", True)
    monkeypatch.setattr(database, "engine", used)
    with pytest.raises(database.OutdatedDatabaseError):
        database._reset_if_outdated()


def test_training_reports_from_model_folders(make_client, tmp_path):
    cwfid_dir, we3ds_dir, eval_dir = tmp_path / "cwfid", tmp_path / "we3ds", tmp_path / "eval"
    for folder in (cwfid_dir, we3ds_dir, eval_dir):
        folder.mkdir()
    (cwfid_dir / "training_report.json").write_text(json.dumps({"dataset": "CWFID", "training": {"best_epoch": 33}}))
    (we3ds_dir / "training_report.json").write_text(json.dumps({"dataset": "WE3DS (folder)"}))
    (eval_dir / "training_we3ds.json").write_text(json.dumps({"dataset": "WE3DS (override)"}))
    models = [
        {"key": "cwfid", "label": "ML (CWFID)", "backend": "fake", "path": str(cwfid_dir)},
        {"key": "we3ds", "label": "ML (WE3DS)", "backend": "fake", "path": str(we3ds_dir)},
        {"key": "none", "label": "No folder", "backend": "fake"},
    ]
    reports = make_client(ml_models=models, evaluation_dir=str(eval_dir)).get(f"{API}/evaluation").json()["training_reports"]
    assert reports["cwfid"] == {"dataset": "CWFID", "training": {"best_epoch": 33}}  # nested data kept as is
    assert reports["we3ds"]["dataset"] == "WE3DS (override)"  # EVALUATION_DIR wins
    assert "none" not in reports
