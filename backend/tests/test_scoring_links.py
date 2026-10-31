from datetime import datetime, timedelta, timezone

import pytest

from backend.config import load_config
from backend.scoring import severity_for

CFG = load_config()
T0 = datetime(2026, 11, 1, 4, 30, 0, tzinfo=timezone.utc)
_n = 0


def raw(sensor="ssh-decoy-01", etype="auth_failure", at=0, session="s1", src_ip="192.168.77.10", **attrs):
    global _n
    _n += 1
    return {
        "schema_version": "1.0", "source_record_id": f"rec-{_n}", "sensor_id": sensor, "event_type": etype,
        "occurred_at": (T0 + timedelta(seconds=at)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "src_ip": src_ip, "session_id": session, "lab_run_id": "run-t", "capture_mode": "replay",
        "attributes": attrs,
    }


def webreq(at, path, query=None, etype="http_request", **attrs):
    a = {"method": "GET", "path": path, **attrs}
    if query is not None:
        a["query_redacted"] = query
    return raw("web-decoy-01", etype, at=at, session=None, **a)




def send(client, *events):
    r = client.post("/api/ingest/events", json={"events": list(events)})
    assert r.status_code == 200 and not r.json()["rejected"], r.text
    return r.json()


def incident(client, inc="inc_01"):
    return client.get(f"/api/incidents/{inc}").json()


def score(client, inc="inc_01"):
    return incident(client, inc)["score"]


def strong_link(client):
    return next(l for l in client.get("/api/links").json()["items"] if l["kind"] == "strong_candidate")


def decide(client, link_id, decision, rationale="checked the evidence"):
    return client.post(f"/api/links/{link_id}/decision", json={"decision": decision, "rationale": rationale})


def run_demo_until_token(client):
    send(client, *[raw(at=i, username="dg_demo", password_sha256="ab" * 32) for i in range(5)])
    assert score(client) == 25
    send(client, raw(etype="auth_success", at=20, session="sess01", username="dg_demo"),
         raw(etype="command_input", at=22, session="sess01", command="whoami"))
    assert score(client) == 40
    send(client, raw(etype="command_input", at=25, session="sess01", command="ls -la"))
    assert score(client) == 50
    send(client, raw(etype="command_input", at=30, session="sess01", command="cat notes.txt"))
    send(client, webreq(70, "/login", "username=svc_portal&password=<redacted>", method="POST",
                        honeytoken_id="tok_portal_01", username="svc_portal"))
    assert score(client) == 50  # R09 waits for confirmation


# ---- task 4: the demo path order ----
def test_demo_path_scores_25_40_50_65_95_100(client):
    run_demo_until_token(client)
    inc = incident(client)
    r09 = next(f for f in inc["findings"] if f["rule_id"] == "R09")
    assert r09["pending_confirmation"] is True and r09["points"] == 0

    send(client, webreq(80, "/search", "q=x%27+UNION+SELECT+username%2Cpassword+FROM+users--"))
    assert score(client) == 65 and incident(client)["severity"] == "high"

    assert decide(client, strong_link(client)["link_id"], "confirm").status_code == 200
    inc = incident(client)
    assert inc["score"] == 95 and inc["severity"] == "critical"
    assert {"R05", "R09"} <= {r["rule_id"] for r in inc["score_breakdown"] if r["counted"]}

    send(client, webreq(90, "/download", "file=customer_data.csv", status_code=200),
         raw("web-decoy-01", "synthetic_file_access", at=90, session=None,
             asset_id="customer_data.csv", outcome="served"))
    inc = incident(client)
    assert inc["score"] == 100
    r04 = next(r for r in inc["score_breakdown"] if r["rule_id"] == "R04")
    assert r04["points"] == 5 and r04["counted"] and "capped" in r04["reason"]
    # every finding has exactly one explaining row
    assert sorted(r["finding_id"] for r in inc["score_breakdown"]) == sorted(f["finding_id"] for f in inc["findings"])
    assert sum(r["points"] for r in inc["score_breakdown"]) == 100


def test_reject_after_confirm_is_reversible(client):
    run_demo_until_token(client)
    link = strong_link(client)["link_id"]
    decide(client, link, "confirm")
    assert score(client) == 80
    rejected = decide(client, link, "reject", "wrong call, different actor").json()
    assert rejected["status"] == "rejected" and rejected["rationale"] == "wrong call, different actor"
    inc = incident(client)
    assert inc["score"] == 50
    assert "R05" not in {f["rule_id"] for f in inc["findings"]}
    assert next(f for f in inc["findings"] if f["rule_id"] == "R09")["pending_confirmation"] is True


def test_confirming_plain_candidate_adds_r05_only(client):
    send(client, raw(at=0, username="u"), webreq(100, "/login"))
    link = client.get("/api/links").json()["items"][0]
    assert link["kind"] == "candidate" and link["status"] == "open"
    decide(client, link["link_id"], "confirm")
    rows = incident(client)["score_breakdown"]
    assert [(r["rule_id"], r["points"]) for r in rows if r["counted"]] == [("R05", 15)]


def test_each_rule_counts_once(client):
    send(client, webreq(0, "/search", "q=' OR '1'='1"), webreq(5, "/search", "q=<script>alert(1)</script>"))
    rows = incident(client)["score_breakdown"]
    assert [r["counted"] for r in rows] == [True, False]
    assert rows[1]["reason"] == "R07 already counted for this incident" and score(client) == 15


def test_blocked_request_adds_no_points(client):
    send(client, webreq(0, "/search", "q=' OR '1'='1", etype="blocked_request",
                        status_code=403, block_action_id="act_1"))
    assert score(client) == 0 and incident(client)["findings"] == []


def test_duplicates_change_nothing(client):
    evs = [raw(at=i, username="dg_demo") for i in range(5)]
    send(client, *evs)
    before = incident(client)
    assert send(client, *evs)["duplicates"] == 5
    assert incident(client) == before


@pytest.mark.parametrize("value,expected", [(0, "low"), (24, "low"), (25, "medium"),
                                            (49, "medium"), (50, "high"), (79, "high"), (80, "critical")])
def test_severity_thresholds(value, expected):
    assert severity_for(value, CFG) == expected


# ---- task 5: links ----
def test_candidate_needs_both_sensors_within_300s(client):
    send(client, raw(at=0, username="u"), webreq(301, "/login"))
    assert client.get("/api/links").json()["items"] == []
    send(client, webreq(300, "/"))
    items = client.get("/api/links").json()["items"]
    assert len(items) == 1 and items[0]["basis"] == "same src_ip within 5 min"


def test_strong_link_from_planted_sensor(client):
    run_demo_until_token(client)
    link = strong_link(client)
    assert link["from_sensor"] == "ssh-decoy-01" and link["to_sensor"] == "web-decoy-01"
    assert link["basis"] == "honeytoken tok_portal_01" and link["status"] == "open"
    cat = [e for e in client.get("/api/events").json()["items"]
           if e["attributes"].get("command") == "cat notes.txt"][0]
    assert link["from_event_id"] == cat["event_id"]  # the shell command that read the bait file


def test_token_on_planting_sensor_is_not_r09(client):
    # tok_backup_01 is planted on the web decoy; presenting it there is not reuse (PRD S17)
    send(client, webreq(0, "/login", honeytoken_id="tok_backup_01"))
    assert incident(client)["findings"] == []
    assert all(l["kind"] != "strong_candidate" for l in client.get("/api/links").json()["items"])


def test_decision_validation(client):
    run_demo_until_token(client)
    lid = strong_link(client)["link_id"]
    short = decide(client, lid, "confirm", "ok")
    assert short.status_code == 400 and short.json()["error"]["code"] == "bad_request"
    assert decide(client, lid, "maybe").status_code == 400
    assert decide(client, lid, "confirm", "    ok    ").status_code == 400  # spaces do not count
    missing = decide(client, "lnk_nope", "confirm")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_websocket_gets_link_and_decision_updates(client):
    with client.websocket_connect("/ws/events") as ws:
        send(client, raw(at=0, username="u"), webreq(10, "/login"))
        types = [ws.receive_json()["type"] for _ in range(3)]
        assert types == ["event", "event", "link"]
        assert ws.receive_json()["type"] == "incident"
        lid = client.get("/api/links").json()["items"][0]["link_id"]
        decide(client, lid, "confirm")
        msg = ws.receive_json()
        assert msg["type"] == "link" and msg["data"]["status"] == "confirmed"
        assert ws.receive_json()["data"]["rule_id"] == "R05"


# ---- task 6: reads ----
def test_incident_list_newest_first_and_detail_shape(client):
    run_demo_until_token(client)
    send(client, raw(at=200, username="u", src_ip="192.168.77.11"))
    items = client.get("/api/incidents").json()["items"]
    assert [i["incident_id"] for i in items] == ["inc_02", "inc_01"]  # newest activity first
    inc = incident(client, "inc_01")
    assert {"findings", "score_breakdown", "links", "sessions", "summary", "active_block"} <= set(inc)
    assert inc["active_block"] is None and inc["summary"]["source"] == "rules"
    # Whichever summariser runs (M4's analyst/summarise.py or the fallback), it cites real evidence.
    event_ids = {e["event_id"] for e in client.get("/api/events?limit=1000").json()["items"]}
    assert inc["summary"]["text"] and set(inc["summary"]["cited_event_ids"]) <= event_ids
    assert inc["summary"]["cited_event_ids"]
    sess = {s["session_id"]: s for s in inc["sessions"]}
    assert sess["sess01"]["commands"] == 3 and sess["sess01"]["sensor_id"] == "ssh-decoy-01"
    assert client.get("/api/incidents/inc_99").status_code == 404


def test_transcript(client):
    run_demo_until_token(client)
    t = client.get("/api/incidents/inc_01/transcript").json()
    assert t["session_id"] == "sess01"
    assert [(l["kind"], l["text"]) for l in t["lines"]] == [
        ("login_ok", "login accepted for user 'dg_demo'"),
        ("command", "whoami"), ("command", "ls -la"), ("command", "cat notes.txt")]
    s1 = client.get("/api/incidents/inc_01/transcript?session_id=s1").json()
    assert {l["kind"] for l in s1["lines"]} == {"login_failed"} and "ab" * 32 not in str(s1)
    assert client.get("/api/incidents/inc_01/transcript?session_id=nope").status_code == 404


def test_stats_overview(client):
    run_demo_until_token(client)
    send(client, raw(at=0, username="x", src_ip="192.168.77.12"))
    s = client.get("/api/stats/overview").json()
    assert s["raw_events"] == 11 and s["incidents"] == 2 and s["low_priority_incidents"] == 1
    assert s["findings_by_rule"] == {"R01": 1, "R02": 1, "R03": 1, "R09": 1}
    assert isinstance(s["first_alert_seconds"], float) and s["first_alert_seconds"] >= 0


def test_stats_empty(client):
    assert client.get("/api/stats/overview").json() == {
        "raw_events": 0, "incidents": 0, "low_priority_incidents": 0,
        "findings_by_rule": {}, "first_alert_seconds": None}


def test_export_has_no_password_hashes(client):
    run_demo_until_token(client)
    r = client.get("/api/incidents/inc_01/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="inc_01.json"'
    body = r.json()
    assert len(body["events"]) == 10 and "Simulated lab data" in body["note"]
    assert "password_sha256" not in r.text and "ab" * 32 not in r.text


# ---- task 7: response hooks ----
def test_response_placeholder_until_m2_lands(client):
    r = client.post("/api/response/preview", json={"incident_id": "inc_01", "ttl_seconds": 120})
    assert r.status_code == 503 and r.json()["error"]["code"] == "response_unavailable"


def test_on_event_hook_called_once_per_new_event(client):
    seen = []
    client.app.state.hooks._on_event = lambda ev: seen.append(ev["event_id"])
    evs = [raw(at=0, username="u"), raw(at=1, username="u")]
    send(client, *evs)
    send(client, *evs)  # duplicates: no second call
    assert len(seen) == 2


def test_on_event_failure_never_breaks_ingest(client):
    def boom(ev):
        raise RuntimeError("bug in response module")
    client.app.state.hooks._on_event = boom
    assert send(client, raw(at=0, username="u"))["accepted"] == 1


def test_analyst_summary_used_when_present_and_fallback_on_error(client):
    send(client, *[raw(at=i, username="u") for i in range(5)])
    hooks = client.app.state.hooks
    hooks._summarise = lambda inc: {"source": "rules", "text": "custom", "cited_event_ids": []}
    assert incident(client)["summary"]["text"] == "custom"
    hooks._summarise = lambda inc: 1 / 0
    assert incident(client)["summary"]["text"].startswith("Repeated SSH password guessing")
    hooks._summarise = None  # M4 module absent
    assert incident(client)["summary"]["text"].startswith("Repeated SSH password guessing")


def test_websocket_seq_rule_from_api_md(client):
    """contracts/API.md: seq = newest event seq at send time; finding/link/incident reuse it,
    and a decision sends messages with no new event."""
    with client.websocket_connect("/ws/events") as ws:
        send(client, raw(at=0, username="u"), webreq(10, "/login"))
        msgs = [ws.receive_json() for _ in range(4)]
        assert [m["type"] for m in msgs] == ["event", "event", "link", "incident"]
        last_event_seq = msgs[1]["seq"]
        assert msgs[0]["seq"] < last_event_seq
        assert all(m["seq"] == last_event_seq for m in msgs[2:])  # same seq: never drop these by seq
        decide(client, msgs[2]["data"]["link_id"], "confirm")
        after = [ws.receive_json() for _ in range(3)]
        assert [m["type"] for m in after] == ["link", "finding", "incident"]
        assert all(m["seq"] == last_event_seq for m in after)  # no new event, same seq
        assert after[2]["data"]["score"] == 15
