"""M4 component integration checks; no attack traffic leaves the test client."""

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analyst.summarise import LABELS, summarise
from decoys.web.app import ASSET, create_app
from decoys.web.policy_bridge import file_checker, resolve_checker


@pytest.fixture
def portal(tmp_path):
    blocklist = tmp_path / "blocklist.json"
    blocklist.write_text(json.dumps({"version": 0, "entries": []}))
    log = tmp_path / "web.json"
    app = create_app({
        "TESTING": True, "BLOCKLIST_PATH": str(blocklist), "LOG_PATH": str(log),
        "HONEYTOKENS_PATH": str(ROOT / "config/honeytokens.yaml"), "LAB_RUN_ID": "test-m4",
    })
    yield app, app.test_client(), log, blocklist
    if log.exists():
        validator = Draft202012Validator(
            json.loads((ROOT / "contracts/event.schema.json").read_text()), format_checker=FormatChecker()
        )
        for event in read_events(log):
            validator.validate(event)


def read_events(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


def block(path, *, expires=None, ip="192.168.77.10", entries=True):
    if expires is None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=120)
    state = {"version": 1, "entries": [{"ip": ip, "action_id": "act_test", "expires_at": expires.isoformat()}] if entries else []}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.replace(path)


@pytest.mark.parametrize("path,status,body", [
    ("/", 200, b"Operations Portal"), ("/login", 200, b"Staff login"),
    ("/search?q=quarterly", 200, b"Quarterly report"),
    ("/search?q=x%27%20UNION%20SELECT%20username,password%20FROM%20users--", 500, b"SQLSTATE"),
    ("/ping?host=%24%28id%29", 200, b"icmp_seq=1"),
    ("/.env", 200, b"BACKUP_SSH_USER=backup"),
    ("/.git/HEAD", 200, b"ref: refs/heads/main"), ("/admin", 401, b"authentication required"),
    ("/backup.zip", 404, b"Request unavailable"),
])
def test_canned_routes(portal, path, status, body):
    _, client, log, _ = portal
    response = client.get(path)
    assert response.status_code == status
    assert body in response.data
    events = read_events(log)
    assert len(events) == 1
    assert events[0]["attributes"]["status_code"] == status
    assert events[0]["capture_mode"] == "live"
    assert events[0]["lab_run_id"] == "test-m4"


@pytest.mark.parametrize("username,password,expected", [
    ("svc_portal", "DGLAB-Portal-4471", 200),
    ("svc_portal", "wrong-secret", 401),
    ("admin", "DGLAB-Portal-4471", 401),
    ("backup", "DGLAB-Bkp-2210", 401),
])
def test_login_hashes_and_token_link_evidence(portal, username, password, expected):
    _, client, log, _ = portal
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code == expected
    event, = read_events(log)
    assert event["event_type"] == ("auth_success" if expected == 200 else "auth_failure")
    assert event["attributes"]["password_sha256"] == hashlib.sha256(password.encode()).hexdigest()
    if password == "DGLAB-Portal-4471":
        assert event["attributes"]["honeytoken_id"] == "tok_portal_01"
    assert password not in log.read_text()


def test_download_exact_asset_hash_and_no_traversal(portal):
    _, client, log, _ = portal
    response = client.get("/download?file=customer_data.csv")
    assert response.data == ASSET.read_bytes()
    event = read_events(log)[-1]
    assert event["event_type"] == "synthetic_file_access"
    assert event["attributes"]["outcome"] == "served"
    assert event["attributes"]["size_bytes"] == len(response.data)
    assert event["attributes"]["sha256"] == hashlib.sha256(response.data).hexdigest()
    for file in ["../assets/customer_data.csv", "/etc/passwd", "../../config/honeytokens.yaml", "https://example.com", "customer_data.csv/extra"]:
        response = client.get("/download", query_string={"file": file})
        assert response.status_code == 404
        assert read_events(log)[-1]["event_type"] == "http_request"
    client.head("/download?file=customer_data.csv")
    assert read_events(log)[-1]["event_type"] == "http_request"


def test_block_first_on_all_routes_then_atomic_undo_and_expiry(portal):
    _, client, log, state = portal
    block(state)
    peer = {"REMOTE_ADDR": "192.168.77.10"}
    for url in ["/", "/download?file=customer_data.csv", "/.env", "/does-not-exist"]:
        assert client.get(url, environ_overrides=peer).status_code == 403
        event = read_events(log)[-1]
        assert event["event_type"] == "blocked_request"
        assert event["attributes"]["block_action_id"] == "act_test"
    assert client.post("/login", data={"username": "svc_portal", "password": "DGLAB-Portal-4471"}, environ_overrides=peer).status_code == 403
    assert "password_sha256" not in read_events(log)[-1]["attributes"]
    block(state, entries=False)
    assert client.get("/", environ_overrides=peer).status_code == 200
    block(state, expires=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert client.get("/", environ_overrides=peer).status_code == 200


def test_peer_ip_not_forwarded_header(portal):
    _, client, log, state = portal
    block(state)
    assert client.get("/", headers={"X-Forwarded-For": "192.168.77.10"}).status_code == 200
    assert read_events(log)[-1]["src_ip"] == "127.0.0.1"


def test_malformed_and_missing_policy_fail_closed(portal):
    _, client, log, state = portal
    for value in ["not json", '[]', '{}', '{"version":1,"entries":[{}]}', '{"version":1,"entries":[null]}']:
        state.write_text(value)
        assert client.get("/.env").status_code == 503
    state.unlink()
    assert client.get("/").status_code == 503
    assert all(e["event_type"] == "http_request" for e in read_events(log))


@pytest.mark.parametrize("ip", ["127.0.0.1", "192.168.77.20", "192.168.77.0/24", "8.8.8.8", "192.168.77.255"])
def test_policy_rejects_forbidden_targets(tmp_path, ip):
    with pytest.raises(ValueError):
        file_checker(tmp_path / "state", [ip])


def test_m2_policy_is_used_when_installed(monkeypatch):
    from types import ModuleType
    package, policy = ModuleType("decoys.policy"), ModuleType("decoys.policy.policy")
    policy.check = lambda ip: "m2_action"
    monkeypatch.setitem(sys.modules, "decoys.policy", package)
    monkeypatch.setitem(sys.modules, "decoys.policy.policy", policy)
    assert resolve_checker("unused", ["192.168.77.10"])("192.168.77.10") == "m2_action"


def test_redaction_encoded_query_forms_headers_and_lengths(portal):
    _, client, log, _ = portal
    password = "unique-private-password"
    client.post("/login?password=unique-private-password&token=DGLAB-Portal-4471", data={"username": password * 20, "password": password}, headers={"User-Agent": password + "DGLAB-Bkp-2210"})
    client.get("/search?q=%2544GLAB-Portal-4471&%2570assword=another-secret", headers={"User-Agent": "another-secret"})
    for secret in [password, "another-secret", "DGLAB-Portal-4471", "DGLAB-Bkp-2210"]:
        assert secret not in log.read_text()
    client.get("/search", query_string={"q": "x" * 6000}, headers={"User-Agent": "a" * 1000})
    last = read_events(log)[-1]["attributes"]
    assert len(last["query_redacted"]) <= 4096
    assert len(last["user_agent"]) <= 512


def test_attacker_text_not_reflected_or_executed(portal, monkeypatch):
    _, client, _, _ = portal
    def forbidden(*args, **kwargs):
        raise AssertionError("Decoy attempted real execution")
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for path, key in [("/ping", "host"), ("/search", "q"), ("/download", "file")]:
        response = client.get(path, query_string={key: "<script>alert(1)</script>;$(id);curl https://example.com"})
        assert b"<script>" not in response.data
        assert b"$(id)" not in response.data
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_body_limit_and_method_rejection_are_logged(portal):
    _, client, log, _ = portal
    assert client.post("/login", data={"password": "x" * 17000}).status_code == 413
    assert client.post("/download?file=customer_data.csv").status_code == 405
    assert len(read_events(log)) == 2


def test_streamed_oversized_form_is_rejected_once_and_logged(portal):
    from io import BytesIO
    from werkzeug.test import EnvironBuilder
    app, _, log, _ = portal
    environ = EnvironBuilder(path="/login", method="POST", content_type="application/x-www-form-urlencoded").get_environ()
    environ.pop("CONTENT_LENGTH", None)
    environ["wsgi.input"] = BytesIO(b"password=" + b"x" * 17000)
    environ["wsgi.input_terminated"] = True
    with app.test_client() as client:
        assert client.open(environ).status_code == 413
    assert len(read_events(log)) == 1


def test_log_write_failure_returns_unavailable(portal, tmp_path):
    app, client, _, _ = portal
    app.config["LOG_PATH"] = str(tmp_path / "missing-directory" / "web.json")
    assert client.get("/").status_code == 503


def test_concurrent_requests_keep_unique_complete_json_lines(portal):
    app, _, log, _ = portal
    def fetch(_):
        with app.test_client() as client:
            return client.get("/").status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(fetch, range(40))) == [200] * 40
    events = read_events(log)
    assert len(events) == len({e["source_record_id"] for e in events}) == 40


def test_payload_fixtures_cover_patterns():
    cases = json.loads((ROOT / "contracts/examples/payloads.json").read_text())
    patterns = yaml.safe_load((ROOT / "config/web_patterns.yaml").read_text())["classes"]
    def matches(value):
        decoded = unquote(unquote(value))
        return {name for name, regexes in patterns.items() if any(re.search(regex, decoded, re.I) for regex in regexes)}
    for case in cases["positive"]:
        assert set(case["classes"]) <= matches(case["input"])
    for case in cases["negative"]:
        assert not matches(case)


@pytest.mark.parametrize("rule", sorted(LABELS))
def test_summary_cites_each_rule_without_trusting_attacker_labels(rule):
    incident = {"findings": [{"rule_id": rule, "label": "Attacker compromised real hosts", "evidence_event_ids": ["evt_1", "evt_2", "evt_1"]}]}
    original = copy.deepcopy(incident)
    result = summarise(incident)
    assert result["source"] == "rules"
    assert result["cited_event_ids"] == ["evt_1", "evt_2"]
    assert LABELS[rule] in result["text"]
    assert "Attacker compromised" not in result["text"]
    assert incident == original


def test_summary_pending_empty_and_unknown():
    result = summarise({"findings": [{"rule_id": "R09", "pending_confirmation": True, "evidence_event_ids": ["evt_3"]}]})
    assert "awaits analyst confirmation" in result["text"]
    assert summarise({"findings": [{"rule_id": "R01", "evidence_event_ids": []}, {"rule_id": "X", "evidence_event_ids": ["x"]}]})["cited_event_ids"] == []
    assert summarise({})["cited_event_ids"] == []


@pytest.mark.parametrize("script", ["attack_p1.sh", "attack_p2.sh", "attack_p3.sh"])
@pytest.mark.parametrize("args", [[], ["127.0.0.1"], ["example.com"], ["192.168.77.20", "extra"]])
def test_scenarios_reject_non_lab_or_extra_arguments(script, args):
    result = subprocess.run(["bash", str(ROOT / "scenarios" / script), *args], capture_output=True, text=True, timeout=3)
    assert result.returncode == 1
    assert "Refusing" in result.stderr
