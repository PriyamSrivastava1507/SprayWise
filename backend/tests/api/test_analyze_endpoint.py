from tests.helpers import field_photo

URL = "/api/v1/analyze"


def post(client, data=None, content=None, content_type="image/jpeg", name="field.jpg"):
    content = field_photo() if content is None else content
    return client.post(URL, files={"file": (name, content, content_type)}, data=data or {})


def error_of(response):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    return body["error"]


def test_success_shape(client):
    response = post(client, {"mode": "compare", "field_name": "North", "area_ha": "2.5"})
    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "compare"
    assert body["field"]["name"] == "North"
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")
    assert body["params"]["area_ha"] == 2.5
    assert [r["method"] for r in body["results"]] == ["classical", "ml"]
    first = body["results"][0]
    assert set(first) == {
        "method", "status", "status_detail", "model_id", "vegetation_pct", "crop_pct",
        "weed_pct", "pressure", "overlay_url", "grid", "spray_cells", "savings",
        "processing_ms",
    }
    assert set(first["savings"]) == {"blanket_cost", "spot_cost", "saved_litres", "saved_pct"}


def test_overlay_and_original_are_served(client):
    body = post(client).json()
    for url in (body["original_url"], body["results"][0]["overlay_url"]):
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")


def test_blank_optional_fields_are_ok(client):
    assert post(client, {"field_id": "", "field_name": ""}).status_code == 201


def test_defaults_when_no_params(client):
    assert post(client).json()["mode"] == "classical"


def test_wrong_content_type(client):
    response = post(client, content=b"hello", content_type="text/plain", name="a.txt")
    assert response.status_code == 422
    assert error_of(response)["code"] == "invalid_image"


def test_not_an_image(client):
    response = post(client, content=b"hello world")
    assert response.status_code == 422
    assert error_of(response)["code"] == "invalid_image"


def test_empty_file(client):
    assert post(client, content=b"").status_code == 422


def test_missing_file(client):
    response = client.post(URL, data={"mode": "classical"})
    assert response.status_code == 422
    assert error_of(response)["code"] == "validation_error"


def test_file_too_large(make_client):
    client = make_client(max_upload_mb=1)
    response = post(client, content=b"\xff\xd8" + b"0" * (1024 * 1024 + 10))
    assert response.status_code == 413
    assert error_of(response)["code"] == "file_too_large"


def test_bad_params_use_error_format(client):
    for data in ({"mode": "bogus"}, {"area_ha": "0"}, {"grid_rows": "1"}, {"area_ha": "abc"},
                 {"cell_threshold": "nan"}):
        response = post(client, data)
        assert response.status_code == 422, data
        assert error_of(response)["code"] == "validation_error"


def test_unknown_field_id(client):
    response = post(client, {"field_id": "999"})
    assert response.status_code == 404
    assert error_of(response)["code"] == "not_found"


def test_ml_mode_unavailable_is_503(make_client):
    client = make_client("unavailable")
    response = post(client, {"mode": "ml"})
    assert response.status_code == 503
    assert error_of(response)["code"] == "model_unavailable"


def test_compare_with_unavailable_model_is_partial_201(make_client):
    client = make_client("unavailable")
    response = post(client, {"mode": "compare"})
    assert response.status_code == 201
    by_method = {r["method"]: r for r in response.json()["results"]}
    assert by_method["classical"]["status"] == "ok"
    assert by_method["ml"]["status"] == "model_unavailable"
    assert by_method["ml"]["savings"]["saved_pct"] is None


def test_unknown_route_uses_error_format(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert error_of(response)["code"] == "not_found"


def test_unexpected_error_hides_details(make_client, monkeypatch):
    from app.services import analysis_service

    def boom(*_a, **_k):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(analysis_service.AnalysisService, "analyze", boom)
    response = post(make_client())
    assert response.status_code == 500
    error = error_of(response)
    assert error["code"] == "internal_error"
    assert "secret" not in error["message"]
