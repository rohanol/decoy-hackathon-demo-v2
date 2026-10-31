# M4 web decoy

All responses are canned. This service never runs commands, executes SQL, reads
an attacker-selected file or fetches an attacker-selected URL. It only serves the
fixed synthetic CSV. Request bodies are limited to 16 KiB. The portal has no real
authenticated session; a correct planted portal password shows a fake dashboard.

## Development and tests

From `dg-soc/`, use Python 3.11:

```bash
python3.11 -m venv /tmp/dg-m4-venv
/tmp/dg-m4-venv/bin/pip install -r decoys/web/requirements-dev.txt
/tmp/dg-m4-venv/bin/python -m pytest tests/e2e -q
```

In the prepared cloud environment, the interpreter is
`/workspace/.venvs/dg-soc/bin/python`. The tests use Flask's local test client and
temporary files, exercise real route/logging/policy code and validate emitted
events against the frozen schema. They do not send attack traffic over a network.

To start locally for development, prepare a separate state directory without
overwriting any existing blocklist:

```bash
mkdir -p /tmp/dg-m4-state
test -e /tmp/dg-m4-state/blocklist.json || printf '%s\n' '{"version":0,"entries":[]}' > /tmp/dg-m4-state/blocklist.json
LOG_PATH=/tmp/dg-m4-state/web.json \
BLOCKLIST_PATH=/tmp/dg-m4-state/blocklist.json \
LAB_RUN_ID=local-dev \
/workspace/.venvs/dg-soc/bin/gunicorn --bind 127.0.0.1:8080 --workers 1 --threads 4 'decoys.web.app:create_app()'
```

Use your own venv's `gunicorn` outside the cloud environment. Do not expose the
decoy on a public interface. For the physical lab, use the existing Compose file
and its exact `192.168.77.20:8080` mapping after M2's preflight passes.

## Configuration and integration

| Variable | Default / meaning |
| --- | --- |
| `LOG_PATH` | `deployment/state/web-log/web.json` under `dg-soc`; parent must exist and be writable |
| `BLOCKLIST_PATH` | `deployment/state/blocklist.json`; must contain valid state before requests |
| `HONEYTOKENS_PATH` | `config/honeytokens.yaml`; Compose supplies `/config/honeytokens.yaml` |
| `LAB_RUN_ID` | `run-01`; M2 must pass the shared current run ID to the container |
| `ATTACKER_IPS` | Space-separated exact lab IPs, default `192.168.77.10` |

Each request produces exactly one ingest-shaped JSON line with a fresh
`source_record_id`, `sensor_id=web-decoy-01`, UTC time and `capture_mode=live`.
POST login emits `auth_success` or `auth_failure` and a SHA-256 password digest;
matching planted credentials add `honeytoken_id`. A successful GET of the CSV
emits `synthetic_file_access` with `outcome=served`, byte length and SHA-256.
HEAD requests do not claim a file was served. Blocked requests emit only
`blocked_request` with `block_action_id`. All other requests emit `http_request`.
Backend/adapter assign incident IDs and apply rules; the decoy never scores.

The direct peer IPv4 address is authoritative; forwarded headers are ignored.
`query_redacted` retains attack text but redacts password/token/secret fields and
planted values. Passwords are not written in plaintext. Gunicorn access logging
is off so raw URLs do not bypass JSONL redaction. Do not enable access logging or
Flask debug mode in the lab. A failed log write returns 503, so fix permissions
before the demo.

Before routing, the service calls `decoys.policy.policy.check(ip)` if available.
Because M2's module is absent in this bootstrap, `policy_bridge.py` supplies an
M4-local compatibility reader for the existing blocklist contract. It rereads the
file on each request, ignores expired entries and only honors explicitly allowed
lab targets. Missing or malformed state returns 503. No response actions, policy
writes or SOC API endpoints are implemented here. M2 can inject their checker via
`create_app(policy_check=...)` or make the canonical module importable.

The Docker build context is `decoys/web`; the image runs as UID/GID 1000, one
Gunicorn worker and four threads. Compose supplies the honeytoken configuration
and writable log mount. For a managed cloud build, pass the trusted CA bundle:

```bash
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t dg-web-decoy:m4 decoys/web
python tests/e2e/smoke_web_container.py
```

See `scenarios/M4_HANDOFF.md` for the remaining M2/M3 connections and lab checks.
