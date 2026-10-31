import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.config import load_config
from backend.rules import evaluate_incident, r01, r02, r03, r04, r07, r08

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config()
T0 = datetime(2026, 11, 1, 4, 30, 0, tzinfo=timezone.utc)
_n = 0


def ev(sensor="ssh-decoy-01", etype="auth_failure", at=0, session="s1", **attrs):
    """Stored-event dict as the rules see it (event_id and seq added)."""
    global _n
    _n += 1
    return {
        "event_id": f"evt_{_n:04d}", "seq": _n, "sensor_id": sensor, "event_type": etype,
        "occurred_at": (T0 + timedelta(seconds=at)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "src_ip": "192.168.77.10", "session_id": session, "attributes": attrs,
    }


def fails(offsets, user="dg_demo"):
    return [ev(at=t, username=user) for t in offsets]


# ---- R01 boundaries: 4 no, 5 yes, 5 spread over 61 s no, 60 s inclusive yes ----
def test_r01_four_failures_no():
    assert r01.evaluate(fails([0, 1, 2, 3]), CFG) == []


def test_r01_five_failures_yes():
    out = r01.evaluate(fails([0, 1, 2, 3, 4]), CFG)
    assert len(out) == 1 and out[0]["rule_id"] == "R01"
    assert out[0]["technique_ids"] == ["T1110.001"] and len(out[0]["evidence_event_ids"]) == 5


def test_r01_five_over_61s_no():
    assert r01.evaluate(fails([0, 15, 30, 45, 61]), CFG) == []


def test_r01_five_in_exactly_60s_yes():
    assert len(r01.evaluate(fails([0, 15, 30, 45, 60]), CFG)) == 1


def test_r01_different_usernames_do_not_pool():
    mixed = fails([0, 1, 2], "root") + fails([3, 4], "admin")
    assert r01.evaluate(mixed, CFG) == []


def test_r01_ignores_web_sensor():
    web = [ev(sensor="web-decoy-01", etype="auth_failure", at=t, username="x") for t in range(5)]
    assert r01.evaluate(web, CFG) == []


def test_r01_arrival_order_does_not_matter():
    events = fails([0, 1, 2, 3, 4])
    assert len(r01.evaluate(list(reversed(events)), CFG)) == 1


# ---- R02 / R03 ----
def test_r02_command_after_login_yes():
    es = [ev(etype="auth_success", at=0), ev(etype="command_input", at=2, command="whoami")]
    out = r02.evaluate(es, CFG)
    assert len(out) == 1 and out[0]["technique_ids"] == ["T1059.004"]
    assert out[0]["evidence_event_ids"] == [e["event_id"] for e in es]


def test_r02_command_without_login_no():
    assert r02.evaluate([ev(etype="command_input", command="whoami")], CFG) == []


def test_r02_login_in_other_session_no():
    es = [ev(etype="auth_success", session="a"), ev(etype="command_input", session="b", command="id")]
    assert r02.evaluate(es, CFG) == []


@pytest.mark.parametrize("cmd", ["ls", "ls -la", "  find / -name x", "LS"[:0] + "ls\t-l"])
def test_r03_discovery_yes(cmd):
    assert len(r03.evaluate([ev(etype="command_input", command=cmd)], CFG)) == 1


@pytest.mark.parametrize("cmd", ["cat notes.txt", "lsof", "whoami", "echo ls", "findmnt"])
def test_r03_other_commands_no(cmd):
    assert r03.evaluate([ev(etype="command_input", command=cmd)], CFG) == []


# ---- R04 ----
def test_r04_served_yes_denied_no():
    served = ev("web-decoy-01", "synthetic_file_access", outcome="served", asset_id="customer_data.csv")
    denied = ev("web-decoy-01", "synthetic_file_access", outcome="denied", asset_id="customer_data.csv")
    assert len(r04.evaluate([served], CFG)) == 1
    assert r04.evaluate([denied], CFG) == []


# ---- R07 against Prajwal's labelled vectors ----
VECTORS = json.loads((ROOT / "contracts" / "examples" / "payloads.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", VECTORS["positive"], ids=lambda c: c["input"][:40])
def test_r07_positive_vectors_match_their_classes(case):
    assert set(case["classes"]) <= set(r07.classify(case["input"], CFG))


@pytest.mark.parametrize("text", VECTORS["negative"])
def test_r07_negative_vectors_match_nothing(text):
    assert r07.classify(text, CFG) == []


def web(path, query=None, etype="http_request", **attrs):
    a = {"method": "GET", "path": path, **attrs}
    if query is not None:
        a["query_redacted"] = query
    return ev("web-decoy-01", etype, session=None, **a)


def test_r07_finding_shape_and_techniques():
    out = r07.evaluate([web("/search", "q=%3Cscript%3Ealert(1)%3C%2Fscript%3E")], CFG)
    assert len(out) == 1 and out[0]["web_attack_class"] == ["xss"]
    assert out[0]["technique_ids"] == ["T1190", "T1059.007"] and out[0]["stage"] == "exploit_attempt"


def test_r07_multiple_classes_and_rfi_technique():
    out = r07.evaluate([web("/ping", "host=127.0.0.1;cat /etc/passwd")], CFG)
    assert out[0]["web_attack_class"] == ["lfi", "cmd_injection"]
    rfi = r07.evaluate([web("/download", "file=http://192.168.77.10/shell.txt")], CFG)
    assert "T1105" in rfi[0]["technique_ids"]


def test_r07_blocked_request_never_fires():
    blocked = web("/search", "q=' OR '1'='1", etype="blocked_request", block_action_id="act_1")
    assert r07.evaluate([blocked], CFG) == []


def test_r07_plus_encoded_query_from_fixture_style():
    assert r07.evaluate([web("/search", "q=x%27+UNION+SELECT+username%2Cpassword+FROM+users--")], CFG)


def test_r07_clean_request_no():
    assert r07.evaluate([web("/search", "q=quarterly+report")], CFG) == []


# ---- R08 ----
def probes(offsets, path="/admin"):
    return [_timed(web(path), t) for t in offsets]


def _timed(e, at):
    e["occurred_at"] = (T0 + timedelta(seconds=at)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return e


def test_r08_five_hidden_paths_yes_four_no():
    assert len(r08.evaluate(probes([0, 1, 2, 3, 4]), CFG)) == 1
    assert r08.evaluate(probes([0, 1, 2, 3]), CFG) == []


def test_r08_spread_over_61s_no():
    assert r08.evaluate(probes([0, 15, 30, 45, 61]), CFG) == []


def test_r08_mixed_hidden_paths_count_together():
    es = [_timed(web(p), i) for i, p in enumerate(["/admin", "/.env", "/backup.zip", "/wp-admin", "/.git/HEAD"])]
    assert len(r08.evaluate(es, CFG)) == 1


def test_r08_ten_404s_yes_nine_no():
    def nf(n):
        return [_timed(web(f"/nope{i}", status_code=404), i) for i in range(n)]
    assert len(r08.evaluate(nf(10), CFG)) == 1
    assert r08.evaluate(nf(9), CFG) == []


def test_r08_normal_pages_no():
    es = [_timed(web("/login", status_code=200), i) for i in range(10)]
    assert r08.evaluate(es, CFG) == []


# ---- engine ----
def test_finding_ids_are_stable_and_schema_complete():
    inc = {"incident_id": "inc_01", "src_ip": "192.168.77.10"}
    es = fails([0, 1, 2, 3, 4])
    a, b = evaluate_incident(inc, es, CFG), evaluate_incident(inc, es, CFG)
    assert a == b and a[0]["finding_id"].startswith("fnd_")
    required = {"finding_id", "rule_id", "rule_version", "incident_id", "src_ip", "technique_ids",
                "stage", "label", "limitation", "evidence_event_ids"}
    assert required <= set(a[0]) and "key" not in a[0]


# ---- end to end through the API ----


def raw(rid, sensor="ssh-decoy-01", etype="auth_failure", at=0, **attrs):
    return {
        "schema_version": "1.0", "source_record_id": rid, "sensor_id": sensor, "event_type": etype,
        "occurred_at": (T0 + timedelta(seconds=at)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "src_ip": "192.168.77.10", "session_id": "s1", "lab_run_id": "run-t",
        "capture_mode": "replay", "attributes": attrs,
    }


def test_rules_run_after_each_insert_and_broadcast(client):
    with client.websocket_connect("/ws/events") as ws:
        for i in range(4):
            client.post("/api/ingest/events", json={"events": [raw(f"f{i}", at=i, username="u")]})
        assert client.app.state.db.list_findings("inc_01") == []
        client.post("/api/ingest/events", json={"events": [raw("f4", at=4, username="u")]})
        db_findings = client.app.state.db.list_findings("inc_01")
        assert [f["rule_id"] for f in db_findings] == ["R01"]
        types = []
        while True:
            m = ws.receive_json()
            types.append(m["type"])
            if m["type"] == "finding":
                assert m["data"]["rule_id"] == "R01"
                break
        assert "finding" in types
    # same batch again: duplicates, no new finding
    r = client.post("/api/ingest/events", json={"events": [raw("f4", at=4, username="u")]}).json()
    assert r["duplicates"] == 1 and len(client.app.state.db.list_findings("inc_01")) == 1
    assert client.app.state.db.incident_summary("inc_01")["stages_observed"] == ["credential_attack"]


def test_fixture_run_produces_expected_rules_once(client):
    fixture = json.loads((ROOT / "contracts" / "examples" / "events_p3.json").read_text(encoding="utf-8"))
    for _ in range(2):  # second post is all duplicates and must change nothing
        client.post("/api/ingest/events", json=fixture)
    db = client.app.state.db
    rules = [f["rule_id"] for f in db.list_findings("inc_01")]
    assert len(rules) == len(set(rules))  # each rule once for this fixture
    assert {"R01", "R02", "R03", "R04", "R07"} <= set(rules)
    assert db.incident_summary("inc_01")["stages_observed"] == [
        "credential_attack", "exploit_attempt", "post_access", "data_access"]
    # the blocked_request fixture event is evidence for nothing
    blocked_ids = {i["event_id"] for i in db.list_events()["items"] if i["event_type"] == "blocked_request"}
    cited = {e for f in db.list_findings("inc_01") for e in f["evidence_event_ids"]}
    assert blocked_ids and not (blocked_ids & cited)


# ---- v2 rule improvements ----
from backend.rules._util import normalize_path, normalize_url  # noqa: E402


@pytest.mark.parametrize("cmd", ["cd /tmp; ls -la", "whoami && find / -name '*.txt'", "/bin/ls -la",
                                 "sudo ls /root", "sudo -u root find /home", "id || ls", "cat x | ls"])
def test_r03_chained_and_full_path_commands_yes(cmd):
    assert len(r03.evaluate([ev(etype="command_input", command=cmd)], CFG)) == 1


@pytest.mark.parametrize("cmd", ["lsblk", "echo ls; whoami", "cat notes.txt && whoami", "findmnt -l",
                                 "grep ls file", "sudo lsof"])
def test_r03_chained_other_commands_no(cmd):
    assert r03.evaluate([ev(etype="command_input", command=cmd)], CFG) == []


@pytest.mark.parametrize("text,cls", [
    ("/search?q=1%27%20UNION%0ASELECT%201", "sqli"),                              # newline evasion
    ("/search?q=1'%09UNION%09%09SELECT%201", "sqli"),                              # tabs
    ("/download?file=%25252e%25252e%25252f%25252e%25252e%25252fetc%25252fpasswd", "lfi"),  # triple encoded
    ("/download?file=..%2F..%2Fetc%2Fpasswd%00.png", "lfi"),                       # null byte
])
def test_r07_evasion_variants_still_match(text, cls):
    assert cls in r07.classify(text, CFG)


def test_normalize_url_stops_when_stable():
    assert normalize_url("%2541") == "a"          # %2541 -> %41 -> A -> a
    assert normalize_url("q=a+b%20%20c") == "q=a b c"
    assert normalize_url("100%") == "100%"        # not an escape; left alone


@pytest.mark.parametrize("path,expected", [
    ("/admin/login.php", True), ("//admin", True), ("/ADMIN/./", True), ("/wp-admin/install.php", True),
    ("/%61dmin", True), ("/.git/config", True),
    ("/administration-guide", False), ("/adminx", False), ("/login", False), ("/", False),
])
def test_r08_hidden_path_matching(path, expected):
    assert r08.is_hidden(path, CFG.hidden_paths) is expected


def test_normalize_path():
    assert normalize_path("//Admin/./login.php/?x=1") == "/admin/login.php"
    assert normalize_path("/") == "/"


def test_r08_counts_subpaths_of_hidden_paths():
    es = [_timed(web(p), i) for i, p in enumerate(
        ["/admin/login.php", "/admin/config.php", "/wp-admin/install.php", "//.env", "/.git/HEAD"])]
    assert len(r08.evaluate(es, CFG)) == 1


def test_r01_mentions_login_accepted_after_guessing():
    es = fails([0, 1, 2, 3, 4]) + [ev(etype="auth_success", at=14, username="dg_demo")]
    out = r01.evaluate(es, CFG)[0]
    assert out["label"].endswith("the decoy accepted a login for this user 10 s later")
    assert out["evidence_event_ids"][-1] == es[-1]["event_id"] and len(out["evidence_event_ids"]) == 6
    assert "compromised" in out["limitation"]  # still says what it does not prove


@pytest.mark.parametrize("extra", [
    lambda: ev(etype="auth_success", at=14, username="someone_else"),   # other user
    lambda: ev(etype="auth_success", at=65, username="dg_demo"),        # 61 s after last failure
])
def test_r01_unrelated_or_late_login_not_mentioned(extra):
    out = r01.evaluate(fails([0, 1, 2, 3, 4]) + [extra()], CFG)[0]
    assert "accepted" not in out["label"] and len(out["evidence_event_ids"]) == 5


def test_r01_login_kept_in_evidence_when_capped():
    es = fails(list(range(55))) + [ev(etype="auth_success", at=56, username="dg_demo")]
    out = r01.evaluate(es, CFG)[0]
    assert len(out["evidence_event_ids"]) == 50 and out["evidence_event_ids"][-1] == es[-1]["event_id"]


def test_changed_rules_carry_version_2():
    assert r01.evaluate(fails([0, 1, 2, 3, 4]), CFG)[0]["rule_version"] == "R01@2"
    assert r03.evaluate([ev(etype="command_input", command="ls")], CFG)[0]["rule_version"] == "R03@2"
    assert r07.evaluate([web("/s", "q=' OR '1'='1")], CFG)[0]["rule_version"] == "R07@2"
    assert r02.evaluate([ev(etype="auth_success"), ev(etype="command_input", at=1, command="id")],
                        CFG)[0]["rule_version"] == "R02@1"
