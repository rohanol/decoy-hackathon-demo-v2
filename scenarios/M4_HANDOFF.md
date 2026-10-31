# M4 handoff — Prajwal

## Implemented

- Flask portal: login, canned SQL error bait, safe synthetic CSV download, canned
  ping, hidden-path bait, one schema-compatible redacted JSONL record per request.
- Policy-first blocking with action IDs; expiration and atomic file replacement
  are exercised in component tests. Failed/missing state returns 503.
- `analyst.summarise.summarise(incident)` returns deterministic rules-only text
  with evidence IDs, preserving pending link confirmation and evidence limits.
- P1 path probes/default logins, P2 fixed six-password SSH guessing, and P3 demo.
  Every script rejects any target other than `192.168.77.20` and extra arguments.
  P3 pauses for link confirmation, verifies 403 after block and 200 after undo.

Changed files are under `decoys/web/`, `analyst/`, `tests/e2e/`, and `scenarios/`,
plus minimal web-service wiring in `deployment/docker-compose.yml`, authorized
as part of the requested connecting work. Frozen schemas, scoring, M1 frontend,
M2 policy/response code and M3 backend are unchanged. Existing web patterns and
payload fixtures remain in sync and tested.
Configuration variables and development commands are in `decoys/web/README.md`.

Example: POST `/login` with the planted portal credential produces HTTP 200 and
`auth_success`, `password_sha256`, and `honeytoken_id=tok_portal_01`; the plaintext
password is absent from logs. GET `/download?file=customer_data.csv` emits
`synthetic_file_access` with the fixed asset's digest. No backend-assigned IDs are
invented by the sensor.

## Connections for other owners

**M2:** ship each `LOG_PATH` JSONL record unchanged through the web adapter to
`POST /api/ingest/events`. The adapter must preserve `source_record_id` for dedup.
Compose now passes `LAB_RUN_ID` and `ATTACKER_IPS` from shared lab.env. Make log directories UID-1000
writable and initialize an empty blocklist without overwriting an active one.
Provide `decoys.policy.policy.check` in the web image (current build context
contains only `decoys/web`), or review/use the documented file-contract bridge.

**M2 blocklist mount:** Compose now mounts the containing state directory
read-only at `/state`, preserving `/state/blocklist.json`. The previous single-file
bind mount could retain an old inode after atomic replacement. M2 should review
this wiring and verify block, revoke and expiry against the full lab stack.

**M3:** call `from analyst.summarise import summarise` when constructing the
Incident response; pass findings with their canonical evidence IDs and
`pending_confirmation`. R07/R08 remain backend responsibilities; a fake SQL
error is only bait, not a claim of successful exploitation. Consume web
`auth_success`/`auth_failure` events and honeytoken IDs for cross-decoy links.

**M1:** display backend incident summary text using ordinary escaped React text.

## Required lab verification

Checks actually run in the cloud environment:

- `python -m pytest tests/e2e -q`: 51 passed. Includes schema validation of
  emitted events, all supplied positive/negative web payloads, safe routes,
  credential hashing/redaction, policy expiry/revoke, summaries and script guards.
- `docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t dg-web-decoy:m4 decoys/web`: passed with TLS verification enabled.
- `python tests/e2e/smoke_web_container.py`: passed real loopback HTTP requests
  through Gunicorn in the image, schema-valid JSONL, fixed CSV digest, UID 1000,
  read-only root, dropped capabilities and visibility of atomic state replacement.
  The temporary container is removed at the end of the check.
- Compose configuration checks verify shared run/IP variables and the read-only
  state-directory mount; `bash -n` passes for all three scripts.

No attack script has been run against the lab yet. There are no full-system
backend/dashboard test results at this stage.

The full sensor → adapter → backend → dashboard path cannot be verified until
the other owners' components exist. Do not treat Flask component tests as that
full end-to-end run. The two-laptop isolated cable lab and real source IP are also
required; no scenario attack script is run in the cloud environment.

Once those components exist, follow `scenarios/demo_p3.md` and run P3 on Laptop A.
Check R01/R02/R03, token strong-candidate link, R07, analyst-confirmed R05/R09,
R04 CSV evidence, preview/apply, verified blocked event, undo, then expiry after
120 s. Rehearse three fresh starts, capture the demo by H22, and log failures
with event IDs and owner. Fixing other owners' code requires their review.
