import os

from tests.api.test_analyze_endpoint import error_of, post

API = "/api/v1"


def media_files(client):
    root = client.app.state.settings.storage_dir
    return [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]


def test_scan_list_detail_delete(client):
    ids = [post(client, {"field_name": "North"}).json()["id"] for _ in range(3)]
    page = client.get(f"{API}/scans").json()
    assert set(page) == {"items", "total", "limit", "offset"}
    assert page["total"] == 3 and page["limit"] == 20 and page["offset"] == 0
    assert [s["id"] for s in page["items"]] == ids[::-1]  # newest first

    detail = client.get(f"{API}/scans/{ids[0]}")
    assert detail.status_code == 200 and detail.json()["id"] == ids[0]

    assert len(media_files(client)) == 6
    assert client.delete(f"{API}/scans/{ids[0]}").status_code == 204
    assert client.get(f"{API}/scans/{ids[0]}").status_code == 404
    assert len(media_files(client)) == 4  # that scan's files are gone
    assert client.get(f"{API}/scans").json()["total"] == 2


def test_scan_pagination_and_filter(client):
    a = post(client, {"field_name": "A"}).json()["field"]["id"]
    for _ in range(2):
        post(client, {"field_name": "A"})
    post(client, {"field_name": "B"})
    page = client.get(f"{API}/scans", params={"limit": 2, "offset": 1}).json()
    assert len(page["items"]) == 2 and page["total"] == 4
    only_a = client.get(f"{API}/scans", params={"field_id": a}).json()
    assert only_a["total"] == 3


def test_scan_list_validation(client):
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"field_id": "x"}):
        response = client.get(f"{API}/scans", params=params)
        assert response.status_code == 422, params
        assert error_of(response)["code"] == "validation_error"


def test_scan_not_found(client):
    for method in (client.get, client.delete):
        response = method(f"{API}/scans/999")
        assert response.status_code == 404
        assert error_of(response)["code"] == "not_found"


def test_delete_compare_scan_removes_both_overlays(client):
    scan_id = post(client, {"mode": "compare"}).json()["id"]
    assert len(media_files(client)) == 3
    client.delete(f"{API}/scans/{scan_id}")
    assert media_files(client) == []


def test_fields_crud(client):
    created = client.post(f"{API}/fields", json={"name": "  South  "})
    assert created.status_code == 201 and created.json()["name"] == "South"
    field_id = created.json()["id"]

    dup = client.post(f"{API}/fields", json={"name": "South"})
    assert dup.status_code == 409 and error_of(dup)["code"] == "conflict"

    client.post(f"{API}/fields", json={"name": "Alpha"})
    names = [f["name"] for f in client.get(f"{API}/fields").json()]
    assert names == ["Alpha", "South"]

    assert client.get(f"{API}/fields/{field_id}").json()["name"] == "South"
    assert client.get(f"{API}/fields/999").status_code == 404


def test_field_create_validation(client):
    for body in ({"name": ""}, {"name": "   "}, {"name": "x" * 121}, {}):
        assert client.post(f"{API}/fields", json=body).status_code == 422, body


def test_trend(client):
    field_id = post(client, {"field_name": "North"}).json()["field"]["id"]
    post(client, {"field_name": "North", "mode": "compare"})
    post(client, {"field_name": "North"})

    classical = client.get(f"{API}/fields/{field_id}/trend").json()
    assert classical["method"] == "classical" and classical["field"]["name"] == "North"
    assert len(classical["points"]) == 3
    stamps = [p["created_at"] for p in classical["points"]]
    assert stamps == sorted(stamps)
    assert set(classical["points"][0]) == {"scan_id", "created_at", "weed_pct", "saved_pct"}

    ml = client.get(f"{API}/fields/{field_id}/trend", params={"method": "ml"}).json()
    assert len(ml["points"]) == 1  # only the compare scan ran ML


def test_trend_skips_failed_results_and_validates(make_client):
    client = make_client("unavailable")
    field_id = post(client, {"field_name": "N", "mode": "compare"}).json()["field"]["id"]
    ml = client.get(f"{API}/fields/{field_id}/trend", params={"method": "ml"}).json()
    assert ml["points"] == []
    assert client.get(f"{API}/fields/{field_id}/trend", params={"method": "x"}).status_code == 422
    assert client.get(f"{API}/fields/999/trend").status_code == 404
