# API contract v1.0

Backend: `http://127.0.0.1:8000`. All JSON snake_case, timestamps RFC 3339 UTC. Errors: `{"error": {"code": "not_found", "message": "..."}}`. No auth (SOC is loopback only).

## Ingest (adapter only)

`POST /api/ingest/events`

```json
{ "events": [ <event.schema.json>, ... ] }
```

Max 100 events or 1 MiB. Response:

```json
{ "accepted": 3, "duplicates": 1, "rejected": [ { "index": 2, "reason": "src_ip: not an ipv4" } ] }
```

Dedup key `(sensor_id, source_record_id)`. A duplicate is not an error.

## Reads

| Route | Returns |
|---|---|
| `GET /api/events?incident_id=&sensor_id=&since_seq=&limit=200` | `{ "items": [Event], "next_seq": 123 }`. Event = ingest fields + `event_id`, `seq`, `ingested_at`, `incident_id` |
| `GET /api/incidents` | `{ "items": [IncidentSummary] }` newest first |
| `GET /api/incidents/{incident_id}` | `Incident` (below) |
| `GET /api/incidents/{incident_id}/transcript?session_id=` | `{ "session_id", "lines": [ { "event_id", "occurred_at", "kind": "login_failed|login_ok|command|close", "text" } ] }` |
| `GET /api/links` | `{ "items": [Link] }` |
| `GET /api/stats/overview` | `{ "raw_events", "incidents", "low_priority_incidents", "findings_by_rule": {"R01": 2}, "first_alert_seconds": 4.2 }` |
| `GET /api/incidents/{incident_id}/export` | Incident JSON, attachment, no password hashes |
| `GET /api/health` | `{ "ok": true, "sensors": { "ssh-decoy-01": "2026-11-01T05:00:00Z", "web-decoy-01": null } }` last event time per sensor |

IncidentSummary:

```json
{ "incident_id": "inc_01", "src_ip": "192.168.77.10", "lab_run_id": "run-01", "score": 65, "severity": "high",
  "stages_observed": ["credential_attack", "post_access"], "first_seen": "...", "last_seen": "...", "event_count": 42 }
```

Incident = IncidentSummary plus:

```json
{
  "findings": [ <finding.schema.json> ],
  "score_breakdown": [ { "rule_id": "R01", "points": 25, "counted": true, "reason": "first R01" } ],
  "links": [ Link ],
  "sessions": [ { "session_id": "a1b2", "sensor_id": "ssh-decoy-01", "started_at": "...", "commands": 4 } ],
  "summary": { "source": "rules", "text": "...", "cited_event_ids": ["evt_..."] },
  "active_block": null
}
```

Link:

```json
{ "link_id": "lnk_01", "from_event_id": "evt_a", "to_event_id": "evt_b", "from_sensor": "ssh-decoy-01", "to_sensor": "web-decoy-01",
  "kind": "candidate | strong_candidate", "basis": "same src_ip within 5 min | honeytoken tok_portal_01",
  "status": "open | confirmed | rejected", "decided_at": null, "rationale": null }
```

## Analyst actions

`POST /api/links/{link_id}/decision`  body `{ "decision": "confirm" | "reject", "rationale": "min 5 chars" }`. Confirm makes R05 (and R09 if strong_candidate) count. Reversible with another decision.

## Response (router lives in `response/`, mounted by backend at `/api/response`)

| Route | Body | Returns |
|---|---|---|
| `POST /api/response/preview` | `{ "incident_id", "ttl_seconds": 120 }` | `{ "preview_id", "target_ip", "scope": "web-decoy-01 only", "ttl_seconds", "expires_at" }` preview valid 60 s. 400 if target is not an allowed lab IP |
| `POST /api/response/apply` | `{ "preview_id", "reason": "min 5 chars", "confirm": true }` | `{ "action_id", "status": "applied", "until": "..." }` |
| `POST /api/response/{action_id}/revoke` | `{}` | `{ "action_id", "status": "revoked" }` |
| `GET /api/response/actions` | | `{ "items": [ { "action_id", "target_ip", "status": "applied|verified|expired|revoked", "reason", "created_at", "until", "verified_by_event_id" } ] }` |

`verified` means a `blocked_request` event with matching `block_action_id` arrived. The UI shows "verified" only then.

Allowed targets: exactly the IPs in `deployment/lab.env` `ATTACKER_IPS` (default `192.168.77.10`). Never `192.168.77.20`, `127.0.0.1`, or a range.

## Blocklist file (response writes, web decoy reads)

`deployment/state/blocklist.json`, written atomically (write tmp, rename). Web decoy mounts it read-only and reads it on every request through `decoys/policy/policy.py: check(ip) -> action_id | None`.

```json
{ "version": 3, "entries": [ { "ip": "192.168.77.10", "action_id": "act_01", "expires_at": "2026-11-01T05:12:00Z" } ] }
```

Expired entries are ignored by `check()`. A blocked request gets HTTP 403 and the web decoy logs a `blocked_request` event with `attributes.block_action_id`.

## WebSocket `/ws/events`

Server pushes after each DB commit:

```json
{ "seq": 124, "type": "event | finding | incident | link | action", "data": { ... } }
```

`data` is the same shape as the REST object (`incident` sends IncidentSummary). Messages arrive in commit order.

`seq` always means the newest event `seq` when the message was sent. How to apply each type:

| `type` | Apply when | How |
|---|---|---|
| `event` | `seq` > the last event `seq` you have | append to the feed |
| `finding` | always | replace the finding with the same `finding_id` (points and `pending_confirmation` change when a link is decided) |
| `link` | always | replace the link with the same `link_id` |
| `incident` | always | replace the summary with the same `incident_id`; if that incident's page is open, re-fetch `GET /api/incidents/{id}` (a rejected link removes its R05 finding, and there is no delete message) |
| `action` | reserved, not sent yet | poll `GET /api/response/actions` for block status |

A `finding`, `link` or `incident` message often has the same `seq` as the event before it, and an analyst decision sends messages without any new event, so never drop those three types by `seq`.

On connect and on every reconnect: open the socket, then load the snapshot (`GET /api/events` for the feed, whose `next_seq` is your last event `seq`, plus `GET /api/incidents` and `GET /api/links`), then apply messages as above.
