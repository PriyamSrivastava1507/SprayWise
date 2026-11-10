from tests.api.test_analyze_endpoint import error_of, post

API = "/api/v1"
BASE = {"area_ha": 2.5, "dose_l_per_ha": 2, "price_per_l": 450, "grid_rows": 8, "grid_cols": 8, "cell_threshold": 0.1}


def recalc(client, scan_id, body, save=False):
    return client.post(f"{API}/scans/{scan_id}/recalculate", params={"save": str(save).lower()}, json=body)


def test_preview_changes_numbers_but_not_the_scan(client):
    scan = post(client, {"mode": "ml", "area_ha": "2.5", "dose_l_per_ha": "2", "price_per_l": "450"}).json()
    before = scan["results"][0]
    preview = recalc(client, scan["id"], {**BASE, "grid_rows": 4, "grid_cols": 5, "cell_threshold": 0.3, "area_ha": 10})
    assert preview.status_code == 200
    r = preview.json()["results"][0]
    assert len(r["grid"]) == 4 and len(r["grid"][0]) == 5
    assert r["savings"]["blanket_litres"] == 20.0
    assert r["weed_pct"] == before["weed_pct"]  # same mask, same cover
    stored = client.get(f"{API}/scans/{scan['id']}").json()
    assert stored["params"]["grid_rows"] == 8 and stored["results"][0]["grid"] == before["grid"]


def test_save_updates_scan_exports_and_trend(client):
    scan = post(client, {"mode": "ml", "field_name": "N"}).json()
    saved = recalc(client, scan["id"], {**BASE, "grid_rows": 3, "grid_cols": 3}, save=True).json()
    assert saved["params"]["grid_rows"] == 3
    stored = client.get(f"{API}/scans/{scan['id']}").json()
    assert stored["params"]["grid_rows"] == 3 and len(stored["results"][0]["grid"]) == 3
    csv = client.get(f"{API}/scans/{scan['id']}/export/csv").text.strip().splitlines()
    assert len(csv) == 1 + 9


def test_higher_threshold_never_sprays_more(client):
    scan = post(client, {"mode": "ml"}).json()
    counts = [len(recalc(client, scan["id"], {**BASE, "cell_threshold": t}).json()["results"][0]["spray_cells"])
              for t in (0.05, 0.2, 0.5, 0.9)]
    assert counts == sorted(counts, reverse=True)


def test_compare_scan_recalculates_only_ok_results(make_client):
    client = make_client("unavailable")
    from tests.helpers import field_photo  # classical finds rows in the synthetic field
    scan = post(client, {"mode": "compare"}, content=field_photo()).json()
    out = recalc(client, scan["id"], {**BASE, "grid_rows": 4}).json()
    by = {r["method"]: r for r in out["results"]}
    assert len(by["classical"]["grid"]) == 4
    assert by["ml"]["status"] == "model_unavailable" and by["ml"]["grid"] is None


def test_errors(make_client, client):
    assert recalc(client, 999, BASE).status_code == 404
    scan = post(client).json()
    bad = recalc(client, scan["id"], {**BASE, "cell_threshold": 1.5})
    assert bad.status_code == 422 and error_of(bad)["code"] == "validation_error"

    unavailable = make_client("unavailable")
    no_ok = post(unavailable, {"mode": "compare"}, content=b"").status_code  # sanity: empty file rejected
    assert no_ok == 422
    from tests.helpers import fallow_photo
    nothing = post(unavailable, {"mode": "compare"}, content=fallow_photo()).json()
    conflict = recalc(unavailable, nothing["id"], BASE)
    assert conflict.status_code == 409 and error_of(conflict)["code"] == "conflict"
