# DeceptionGraph v2 — Backend plan

Status: draft, 31 Oct 2026. Owner: Rohan (M3). This plans the **backend** for the v2 re-scope.
It is a plan, not built code. v1 (`rohanol/decoy-hackathon-demo`) stays untouched; this
lives in `rohanol/decoy-hackathon-demo-v2`. Project brief: `docs/prd/V2_BRIEF.md`.

---

## 1. What changed, in one line

v1 was a **two-laptop lab demo**. v2 is a **deployable deception sensor kit** an organization
installs inside its own network with one `docker compose up`, plus a SOC dashboard for the
security team. Same core idea, product-shaped.

Reference products (for the pitch, not for copying code): Thinkst Canary, MITRE engage. The
selling point stays: **a decoy has no legitimate users, so a hit is almost never a false alarm.**
We watch for direct intrusions instead of sifting millions of real events.

---

## 2. What we ship (the four pieces)

| Piece | What it is | Owner |
|---|---|---|
| **Decoys** | 2 containers: SSH decoy (Cowrie) + fake internal web portal | Prajwal (web), Vedant (SSH) |
| **Log adapter** | Reads each decoy's logs, classifies the attack, normalises to our event schema, ships to the backend | Vedant |
| **Backend** | Ingest → rules → incidents → scoring → cross-decoy links → read API + live stream | **Rohan (this doc)** |
| **SOC dashboard** | Detailed view + a simplified at-a-glance view for the security team | Pashmee (M1) |

All four ship together behind **one Compose file**. The backend's job is to be the stable centre:
everything feeds it, the dashboard reads from it.

---

## 3. The biggest architectural change: no lab assumptions

v1 hardcoded the lab: one `lab_run_id`, a fixed attacker IP (`192.168.77.10`), fixed decoy IPs.
In a real org network none of that holds. The backend changes accordingly:

1. **Every source is suspect.** A decoy has no real users, so we do **not** keep an
   "expected attacker IP" list and we do **not** gate on it. Any `src_ip` that touches a decoy
   opens or extends an incident. (This deletes a whole class of v1 config and the gateway-IP
   edge cases.)
2. **`lab_run_id` → `deployment_id` + `site`.** Each install has a stable deployment id and an
   optional human site label ("HQ-DMZ", "finance-vlan"). Events carry it; incidents group by
   `(deployment_id, src_ip)`.
3. **`capture_mode`** stays (`live` / `replay`) so we can still replay a recorded incident for a
   demo without it ever reading as live.
4. **Real volumes, real time.** Retention, pagination and a size cap on stored attacker text all
   become real requirements, not nice-to-haves.

These are backend-owned and touch `contracts/` — so they are **contract PRs** (AGENTS.md §3) and
need sign-off from every owner before merge. That is also how we avoid teammate collisions:
the schema change lands first, everyone rebases on it.

---

## 4. Backend architecture

Keep the v1 stack: **FastAPI + Pydantic + SQLite (WAL, single writer)**. It is small, fast,
offline, and fits "one container." No Kafka, no Postgres, no cloud — same constraint as v1
(AGENTS.md §4). The flow:

```
decoy logs ─► log adapter ─► POST /api/ingest/events
                                    │
                        ┌───────────▼───────────┐
                        │ ingest: validate,      │
                        │ dedup (source_record_id),
                        │ redact secrets,        │
                        │ assign event_id + seq  │
                        └───────────┬───────────┘
                                    ▼
                        group into incident (deployment_id, src_ip)
                                    ▼
                        run rules R01..R09 (+ new web rules) → findings
                                    ▼
                        scoring (config-driven weights, capped)
                                    ▼
                        cross-decoy links (honeytoken reuse)
                                    ▼
                 persist ──► outbox ──► /ws/events live push ──► dashboard
```

### 4.1 Reused from v1 (keep, adjust configs)
- `backend/main.py` routes, `db.py` schema, `models.py`, `scoring.py`, `links.py`,
  `rules/r01..r09`, the outbox + `/ws/events` stream.
- `config/scoring.yaml`, `config/web_patterns.yaml`, `config/honeytokens.yaml` — versioned config,
  never hardcoded.

### 4.2 Changed
- Ingest: drop the attacker-IP gate; add per-deployment grouping; enforce a stored-size cap on
  attacker-controlled strings (commands, paths, query) so a flood can't bloat the DB.
- Schema: `lab_run_id` → `deployment_id` + optional `site`. Bump `schema_version` to `"2.0"`.
- Incidents keyed on `(deployment_id, src_ip)`.

### 4.3 New
- **Deployments table**: one row per installed kit (id, site label, first_seen, last_seen,
  decoy health). Lets one backend serve several decoy hosts, and powers a multi-site dashboard.
- **IDOR / fake-endpoint rule** (web): a hit on a planted endpoint like `/api/orders/{id}`,
  `/admin`, `/backup.zip`, or a hidden path from `web_patterns.yaml` becomes a finding. Pure
  pattern match on the path the adapter already sends; no new attacker interaction.
- **Honeytoken bait tracking** (the chosen bait model): the web decoy serves small, realistic
  decoy files (fake `customer_export.csv`, `backup.zip`, a config with planted creds) each
  carrying a honeytoken. Downloading one, or **reusing** a planted credential on the SSH decoy,
  raises a high-confidence finding and a **cross-decoy link** (R05/R09 already model this — we
  generalise them beyond the single lab token). This is the near-zero-false-positive signal, and
  it does no harm to anyone's device.
- **Dashboard summary endpoints**: a compact `/api/summary` for the "simplified, easy" view
  (counts, top incidents, decoy health) separate from the detailed per-incident reads, so M1 can
  build both the simple and detailed views cheaply.

### 4.4 Explicitly out of scope (safety boundary)
- **No destructive or retaliatory payloads.** No file designed to exhaust disk/RAM or crash a
  visitor's machine, no "hack-back", no fetching or executing anything an intruder submits. The
  value is the *signal* (a tracked bait was touched), never damage to the toucher — who may be a
  scanner, a researcher, or one of us. This keeps us inside the law and inside the project's own
  honesty rules.
- Decoys stay emulated and isolated; the backend/SOC is never reachable from the decoy network;
  passwords and tokens are redacted before storage (AGENTS.md §5). All unchanged from v1.

---

## 5. The log adapter (backend's upstream contract)

Vedant owns the adapter; the backend owns the **contract** it must meet. The adapter:
1. Tails each decoy's log (Cowrie JSON, web decoy JSON).
2. Classifies: event type, and for web, the attack class (SQLi / XSS / LFI / RFI / cmd-injection /
   IDOR / probing) from `web_patterns.yaml`.
3. Normalises to `contracts/event.schema.json` v2, hashes/removes any password, keeps a byte
   checkpoint so a restart never re-sends or loses lines.
4. POSTs batches to `/api/ingest/events`.

**On the "AI-based adapter" idea:** keep the deterministic rule/pattern classifier as the source
of truth — it's what the score and the labels cite. An AI layer can be added later as *optional
enrichment only* (a plain-English attack summary, a guess at the attacker's goal), clearly marked
`source: "llm"`, never feeding the score and never a label we present as proven. That matches v1's
"claim only what the evidence proves" and the dashboard's existing `[rules]` vs `[llm]` source
chip. It is not needed for the first working version.

---

## 6. API surface (v2)

Keep every v1 route (ingest, events, incidents, incident detail, transcript, export, links,
link decision, stats/overview, health, `/ws/events`). Add:

| Route | Purpose |
|---|---|
| `GET /api/deployments` | installed kits + decoy health, for multi-site and the simple view |
| `GET /api/summary` | compact numbers for the simplified dashboard |
| (schema) `deployment_id`, `site` on events/incidents | replaces `lab_run_id` |

No route is renamed or removed without a contract PR. Errors keep the v1 shape
(`{"error":{code,message,request_id,details}}`).

---

## 7. Build order (so it runs early and nobody blocks)

1. **Contract PR**: event schema v2 (`deployment_id`/`site`, `schema_version:"2.0"`), the new web
   rule ids, the two new endpoints. Merge first; everyone rebases.
2. **Ingest + grouping** without the attacker-IP gate; size cap; deployments table. Backend runs
   on fixtures.
3. **Rules**: port R01–R09, add IDOR/fake-endpoint rule, generalise honeytoken linking.
4. **Summary + deployments endpoints** for M1's simple view.
5. **Compose**: backend as a service in the one-command stack, with a persistent volume and a
   retention setting.
6. Tests per rule/endpoint incl. a negative case (AGENTS.md §4), then an end-to-end replay.

Every step: run the app/tests, paste real output. No invented results.

---

## 8. Open questions for the team
1. `deployment_id` — generated by the backend on first contact from a decoy, or set in each
   install's `.env`? (Lean: set in `.env`, so a reinstall keeps its identity.)
2. Retention: how long do we keep raw events vs keep the incident summary? (Lean: raw events
   N days, incidents kept.)
3. Multi-site in one backend now, or one backend per site for the demo? (Lean: build the schema
   for multi-site, demo with one.)
4. Who owns `web_patterns.yaml` for the new IDOR/hidden-path entries — Prajwal writes patterns,
   Rohan wires the rule? (Mirrors the v1 R07 split.)
