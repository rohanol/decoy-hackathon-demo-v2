"""Canned internal portal and schema-compatible sensor JSONL, never real queries."""

import hashlib
import hmac
import ipaddress
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode

import yaml
from flask import Flask, Response, g, request

from .policy_bridge import resolve_checker

ROOT = Path(__file__).resolve().parents[2]
ASSET = Path(__file__).parent / "assets/customer_data.csv"
BAIT_TOKEN = "DGLAB-Bkp-2210"
SENSITIVE = re.compile(r"pass|token|secret|authorization|api.?key", re.I)
# This only chooses canned bait. Backend R07 owns attack classification.
SQL_BAIT = re.compile(r"union\s+select|'\s*(?:or|and)\b|;\s*(?:drop|insert|update|delete)\b|(?:sleep|benchmark|pg_sleep)\s*\(", re.I)
PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Files / Internal Operations</title><style>
body{{font:16px system-ui;background:#edf0f3;color:#253345;max-width:850px;margin:55px auto}}
header,main{{background:white;padding:28px;margin:12px;border:1px solid #cdd3db}}
a{{color:#235e91;margin-right:20px}}input,button{{padding:10px;margin:8px}}
small{{color:#697789}}pre{{white-space:pre-wrap}}</style>
<header><small>FILES-SRV-02 · INTERNAL USE</small><h1>Operations Portal</h1>
<a href="/">Home</a><a href="/login">Login</a><a href="/search">Search</a>
<a href="/download?file=customer_data.csv">Customer export</a></header><main>{}</main></html>"""


def create_app(config=None, *, policy_check=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(
        MAX_CONTENT_LENGTH=16384,
        LOG_PATH=os.environ.get("LOG_PATH", str(ROOT / "deployment/state/web-log/web.json")),
        BLOCKLIST_PATH=os.environ.get("BLOCKLIST_PATH", str(ROOT / "deployment/state/blocklist.json")),
        HONEYTOKENS_PATH=os.environ.get("HONEYTOKENS_PATH", str(ROOT / "config/honeytokens.yaml")),
        LAB_RUN_ID=os.environ.get("LAB_RUN_ID", "run-01"),
        ATTACKER_IPS=os.environ.get("ATTACKER_IPS", "192.168.77.10"),
    )
    app.config.update(config or {})
    tokens = yaml.safe_load(Path(app.config["HONEYTOKENS_PATH"]).read_text())["tokens"]
    checker = policy_check or resolve_checker(
        app.config["BLOCKLIST_PATH"], app.config["ATTACKER_IPS"].split()
    )
    lock = threading.Lock()

    def page(body, status=200):
        return Response(PAGE.format(body), status=status, mimetype="text/html")

    def clean(value, limit):
        value = unquote(unquote(str(value)))
        for secret in sorted(g.secrets, key=len, reverse=True):
            if secret:
                value = value.replace(secret, "<redacted>")
        # Honeytoken plaintext can be supplied outside a password field.
        value = re.sub(r"DGLAB-[A-Za-z0-9_-]+", "<redacted>", value)
        return value[:limit]

    @app.before_request
    def policy_first():
        g.event_type = "http_request"
        g.attributes = {}
        g.response_class = "normal"
        g.secrets = {BAIT_TOKEN}
        # Deliberately ignore X-Forwarded-For: the lab uses the direct peer IP.
        g.src_ip = request.remote_addr
        try:
            ipaddress.IPv4Address(g.src_ip)
        except (ipaddress.AddressValueError, TypeError):
            return page("<h2>IPv4 lab connection required</h2>", 400)
        try:
            action_id = checker(g.src_ip)
        except (OSError, ValueError, KeyError, TypeError):
            return page("<h2>Portal temporarily unavailable</h2>", 503)
        if action_id:
            g.event_type = "blocked_request"
            g.response_class = "blocked"
            g.attributes["block_action_id"] = action_id
            return page("<h2>Access denied</h2>", 403)

    @app.after_request
    def record(response):
        # Even rejected/blocked form requests must not leak presented credentials
        # through another field such as User-Agent. Do not parse oversized bodies.
        if (request.mimetype == "application/x-www-form-urlencoded"
                and request.content_length is not None
                and request.content_length <= app.config["MAX_CONTENT_LENGTH"]
                and response.status_code != 413):
            for key in request.form:
                if SENSITIVE.search(key):
                    g.secrets.update(request.form.getlist(key))
        query = parse_qsl(unquote(request.query_string.decode("utf-8", "replace")), keep_blank_values=True)
        for key, value in query:
            if SENSITIVE.search(key):
                g.secrets.add(value)
        redacted = urlencode([
            (clean(key, 512), "<redacted>" if SENSITIVE.search(key) else clean(value, 4096))
            for key, value in query
        ], safe="<>/'():,; ")
        attributes = {key: clean(value, 128) if key == "username" else value for key, value in g.attributes.items()}
        attrs = {
            "method": request.method,
            "path": clean(request.path, 4096),
            "query_redacted": redacted[:4096],
            "user_agent": clean(request.headers.get("User-Agent", ""), 512),
            "status_code": response.status_code,
            "response_class": g.response_class,
            **attributes,
        }
        event = {
            "schema_version": "1.0", "source_record_id": str(uuid.uuid4()),
            "sensor_id": "web-decoy-01", "event_type": g.event_type,
            "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "src_ip": g.src_ip or "0.0.0.0", "session_id": None,
            "lab_run_id": app.config["LAB_RUN_ID"], "capture_mode": "live", "attributes": attrs,
        }
        # Invalid peers are rejected before routes; keep even rejection logs IPv4-valid.
        try:
            ipaddress.IPv4Address(event["src_ip"])
        except ipaddress.AddressValueError:
            event["src_ip"] = "0.0.0.0"
        line = (json.dumps(event, ensure_ascii=True) + "\n").encode()
        try:
            with lock:
                with open(app.config["LOG_PATH"], "ab") as stream:
                    stream.write(line)
        except OSError:
            # No success claim if evidence could not be persisted; never log raw URLs.
            response = page("<h2>Portal temporarily unavailable</h2>", 503)
            app.logger.error("Sensor log write failed; check LOG_PATH permissions")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
        return response

    @app.get("/")
    def home():
        return page("<h2>Staff resources</h2><p>Quarterly customer export is ready. Please use the portal login.</p><small>Maintenance ticket #1042 still open.</small>")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return page('<h2>Staff login</h2><form method="post"><input name="username" placeholder="Username" maxlength="128"><input name="password" type="password" placeholder="Password"><button>Sign in</button></form>')
        password = request.form.get("password", "")
        g.secrets.add(password)
        username = request.form.get("username", "")
        digest = hashlib.sha256(password.encode()).hexdigest()
        matched = next((token for token in tokens if hmac.compare_digest(token["value_sha256"], digest)), None)
        g.attributes.update(username=clean(username, 128), password_sha256=digest)
        if matched:
            g.attributes["honeytoken_id"] = matched["id"]
        valid = bool(matched and username == "svc_portal" and matched["username"] == username and matched["valid_on"] == "web-decoy-01")
        g.event_type = "auth_success" if valid else "auth_failure"
        if valid:
            return page('<h2>Staff dashboard</h2><p>Signed in to the internal portal.</p><a href="/download?file=customer_data.csv">Download customer export</a>')
        return page("<h2>Invalid credentials</h2>", 401)

    @app.get("/search")
    def search():
        if SQL_BAIT.search(unquote(unquote(request.args.get("q", "")))):
            g.response_class = "fake_error"
            return page("<h2>Database error</h2><pre>SQLSTATE[42000]: syntax error near customer_directory. Contact the administrator.</pre>", 500)
        return page('<h2>Search directory</h2><form><input name="q" placeholder="Search"><button>Search</button></form><p>Quarterly report · Customer export · Staff handbook</p>')

    @app.get("/download")
    def download():
        if request.args.get("file") != "customer_data.csv":
            return page("<h2>File not found</h2>", 404)
        data = ASSET.read_bytes()
        if request.method == "GET":
            g.event_type = "synthetic_file_access"
            g.response_class = "fake_data"
            g.attributes.update(asset_id="customer_data.csv", size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), outcome="served")
        return Response(data, mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="customer_data.csv"'})

    @app.get("/ping")
    def ping():
        return page("<h2>Connectivity tool</h2><pre>PING files-srv-02 (192.168.77.20): 56 data bytes\n64 bytes: icmp_seq=1 ttl=64 time=0.4 ms\n1 packet transmitted, 1 received</pre>")

    @app.get("/.env")
    def env_bait():
        return Response(f"APP_ENV=internal\nBACKUP_SSH_USER=backup\nBACKUP_SSH_PASS={BAIT_TOKEN}\n", mimetype="text/plain")

    @app.get("/.git/HEAD")
    def git_bait():
        return Response("ref: refs/heads/main\n", mimetype="text/plain")

    @app.get("/admin")
    def admin():
        return page("<h2>Administrator authentication required</h2>", 401)

    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(413)
    def canned_error(error):
        return page("<h2>Request unavailable</h2>", error.code)

    return app
