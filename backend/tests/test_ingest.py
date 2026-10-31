import copy
import json
from pathlib import Path

import pytest


FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "events_p3.json"


def make_event(rid="rec-1", **over):
    ev = {
        "schema_version": "1.0", "source_record_id": rid, "sensor_id": "ssh-decoy-01",
        "event_type": "auth_failure", "occurred_at": "2026-11-01T04:30:00Z",
        "src_ip": "192.168.77.10", "src_port": 50001, "session_id": "s1",
        "lab_run_id": "run-test", "capture_mode": "replay",
        "attributes": {"username": "dg_demo", "password_sha256": "ab" * 32},
    }
    ev.update(over)
    return ev




def post(client, events):
    return client.post("/api/ingest/events", json={"events": events})


def test_accepts_and_lists(client):
    r = post(client, [make_event("a"), make_event("b")])
    assert r.status_code == 200
    assert r.json() == {"accepted": 2, "duplicates": 0, "rejected": []}
    items = client.get("/api/events").json()["items"]
    assert [i["source_record_id"] for i in items] == ["a", "b"]
    assert items[0]["event_id"].startswith("evt_") and items[0]["incident_id"] == "inc_01"


def test_dedup_on_sensor_and_source_record_id(client):
    assert post(client, [make_event("dup")]).json()["accepted"] == 1
    r = post(client, [make_event("dup"), make_event("new")]).json()
    assert r == {"accepted": 1, "duplicates": 1, "rejected": []}
    assert len(client.get("/api/events").json()["items"]) == 2
    # same record id on the other sensor is a different event
    other = make_event("dup", sensor_id="web-decoy-01", event_type="http_request")
    assert post(client, [other]).json()["accepted"] == 1


def test_dup_inside_one_batch(client):
    r = post(client, [make_event("x"), make_event("x")]).json()
    assert (r["accepted"], r["duplicates"]) == (1, 1)


def test_bad_ip_rejected(client):
    good, bad_v6, bad_text = make_event("g"), make_event("b1", src_ip="::1"), make_event("b2", src_ip="999.1.1.1")
    r = post(client, [good, bad_v6, bad_text]).json()
    assert r["accepted"] == 1
    assert [x["index"] for x in r["rejected"]] == [1, 2]
    assert all("src_ip" in x["reason"] and "ipv4" in x["reason"] for x in r["rejected"])
    assert len(client.get("/api/events").json()["items"]) == 1


def test_raw_password_rejected_and_never_stored(client):
    ev = make_event("p")
    ev["attributes"]["password"] = "hunter2"
    r = post(client, [ev]).json()
    assert r["accepted"] == 0 and r["rejected"][0]["index"] == 0
    assert "hunter2" not in json.dumps(client.get("/api/events").json())


def test_unknown_field_and_naive_time_rejected(client):
    r = post(client, [make_event("u", surprise=1), make_event("t", occurred_at="2026-11-01T04:30:00")]).json()
    assert r["accepted"] == 0 and len(r["rejected"]) == 2


def test_batch_limits(client):
    r = post(client, [make_event(f"r{i}") for i in range(101)])
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"
    big = make_event("big")
    big["attributes"]["extra"] = "x" * (1024 * 1024)
    assert post(client, [big]).status_code == 413
    bad_json = client.post("/api/ingest/events", content="not json", headers={"Content-Type": "application/json"})
    assert bad_json.status_code == 400 and bad_json.json()["error"]["code"] == "bad_request"


def test_seq_is_global_and_ordered(client):
    post(client, [make_event("a"), make_event("b", sensor_id="web-decoy-01", event_type="http_request")])
    post(client, [make_event("c", src_ip="192.168.77.11")])
    items = client.get("/api/events").json()["items"]
    assert [i["seq"] for i in items] == [1, 2, 3]
    page = client.get("/api/events?since_seq=1&limit=1").json()
    assert [i["seq"] for i in page["items"]] == [2] and page["next_seq"] == 2
    assert [i["seq"] for i in client.get("/api/events?sensor_id=web-decoy-01").json()["items"]] == [2]


def test_one_incident_per_ip_per_run(client):
    post(client, [
        make_event("a"), make_event("b"),
        make_event("c", lab_run_id="run-other"),
        make_event("d", src_ip="192.168.77.11"),
    ])
    ids = [i["incident_id"] for i in client.get("/api/events").json()["items"]]
    assert ids[0] == ids[1] and len(set(ids)) == 3


def test_health_reports_last_event_per_sensor(client):
    assert client.get("/api/health").json() == {
        "ok": True, "sensors": {"ssh-decoy-01": None, "web-decoy-01": None}}
    post(client, [make_event("a")])
    assert client.get("/api/health").json()["sensors"]["ssh-decoy-01"] == "2026-11-01T04:30:00Z"


def test_unknown_event_query_validation_uses_error_shape(client):
    r = client.get("/api/events?limit=0")
    assert r.status_code == 400 and "error" in r.json()


def test_websocket_receives_new_event(client):
    with client.websocket_connect("/ws/events") as ws:
        post(client, [make_event("ws-1")])
        msg = ws.receive_json()
        assert msg["type"] == "event" and msg["seq"] == 1
        assert msg["data"]["source_record_id"] == "ws-1"
        inc = ws.receive_json()
        assert inc["type"] == "incident" and inc["data"]["event_count"] == 1
        # a duplicate must not broadcast anything
        post(client, [make_event("ws-1"), make_event("ws-2")])
        assert ws.receive_json()["data"]["source_record_id"] == "ws-2"


def test_fixture_file_loads_cleanly(client):
    events = json.loads(FIXTURE.read_text(encoding="utf-8"))["events"]
    r = post(client, copy.deepcopy(events)).json()
    assert r["accepted"] == len(events) and r["rejected"] == []
    assert post(client, events).json()["duplicates"] == len(events)


def test_ingest_requires_json_content_type(client):
    r = client.post("/api/ingest/events", content=json.dumps({"events": [make_event("ct")]}),
                    headers={"Content-Type": "text/plain"})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_media_type"
    assert client.get("/api/events").json()["items"] == []


def test_declared_oversize_body_rejected_before_reading(client):
    r = client.post("/api/ingest/events", content=b"{}",
                    headers={"Content-Type": "application/json", "Content-Length": str(2 * 1024 * 1024)})
    assert r.status_code == 413


def test_cors_allows_the_vite_dev_server_only(client):
    ok = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_websocket_rejects_foreign_origin(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/events", headers={"Origin": "http://evil.example"}) as ws:
            ws.receive_json()
    with client.websocket_connect("/ws/events", headers={"Origin": "http://localhost:5173"}):
        pass


def test_unknown_route_uses_error_shape(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_importing_main_does_not_create_default_db():
    import importlib
    import backend.main as m
    importlib.reload(m)
    assert m._app is None
