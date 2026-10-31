# DeceptionGraph SOC: Reference PRD v3.0

**Draft for Team Research — incorporates v2.0 plus proposed additions**

Oct 31, 2026 · based on v2.0 by @Rohan

## How to read this document

This is a reference PRD for team discussion. Every item tagged **PROPOSED** can be kept, changed, or cut after research. It is a specification only; no implementation result or benchmark is claimed. Targets are tests to run.

| Tag | Meaning | What it takes to change |
|---|---|---|
| BASELINE | Confirmed in PRD v1.0 | Written change note in `docs/decisions`, reviewed by affected owners |
| PROPOSED | New in this document | Research, then keep or cut vote |
| STRETCH | Build only when ahead of schedule | Decide at milestone gate |
| PARKED | Recorded but not planned | Revisit only if a gate passes early |

Every new idea has an ID (I-01 to I-23), a plain-words explanation, and research questions in section 16 (RS-1 to RS-18). Section 15 lists every idea with keep-if and cut-if criteria.

**Sources:** PRD v1.0, teammate coding-AI master prompt (31 Oct 2026), PS 04 problem statement, and real-world research on Tanner/Snare, Cowrie TTY/HASSH, ATT&CK v18 Detection Strategies, honeytoken plausibility, OpenCanary, and LLM-driven decoys.

**Change log from v2.0:**

- R07 expanded from 3 to 5 web attack classes: SQLi, XSS, LFI, RFI, command injection.
- Findings gain `web_attack_class` multi-label and `detection_strategy_refs`.
- I-16 split into Transcript replay (Must) and Native TTY replay (Stretch).
- `connection_open` gains `hassh` as claimed client fingerprint.
- I-03 gains `plausibility_tier` and `placement_context`.
- New I-22: OpenCanary auxiliary tripwire (conditional Should).
- New I-23: LLM response generator for D2 (Stretch/Parked, strict isolation).
- New research questions RS-14 to RS-18.
- New acceptance criteria AC23 to AC27.
- Koney/K8s decoy orchestration recorded as Parked.

---

## 1. Summary and what changes from v2.0

DeceptionGraph SOC is an isolated lab where an attacker laptop’s real traffic hits fake SSH, web, and API services, and a SOC dashboard on the defender laptop turns that traffic into scored, evidence-linked incidents.

v2.0 added web exploitation, web reconnaissance, and cross-decoy proof. v3.0 strengthens detection granularity, forensic depth, mapping structure, honeytoken design, and optional auxiliary telemetry without breaking the deterministic, evidence-gated baseline.

In plain words: the attacker laptop breaks into fake machines; the SOC laptop watches, explains, and ranks what happened, and lets an analyst block the web decoy. v3.0 makes the “what happened” more precise and more auditable.

| Area | v2.0 baseline | Proposed in v3.0 | Ideas |
|---|---|---|---|
| Decoys | Cowrie SSH, fake web login, optional API decoy | Same, plus optional OpenCanary tripwire | I-04, I-22 |
| Detection | R01–R10 | R07 expanded to 5 web classes; R08 separated; R09 carries plausibility | I-01, I-02, I-03, I-08 |
| Correlation | Honeytoken reuse as strong candidate | Honeytoken plausibility context; no auto-confirm | I-03 |
| Labels | Kill-chain stages, noise-vs-targeted, bot-vs-human | HASSH claimed fingerprint; Strategy/Analytic refs | I-09, I-10 |
| Dashboard | Kill-chain bar, heatmap, noise counter, replay, metrics, isolation | Transcript replay Must; native TTY replay Stretch; HASSH shown | I-11–I-18 |
| Export | STIX, Navigator layer | Navigator comments cite Strategy/Analytic | I-12, I-14 |
| AI | Explains, never acts | Optional LLM response generator only as Stretch | I-23 |
| Evaluation | 12 baseline + S13–S20 | Add web five-class tests, HASSH stability, OpenCanary visibility | I-19 |

Unchanged from v1.0/v2.0: safety rules, offline core, SQLite with one writer, `/api` and `/ws/events` routes, manual approval for response, and “AI explains but never acts” as a baseline rule.

---

## 2. Lab topology

Two physical laptops share one private cable: Laptop A attacks, Laptop B hosts decoys and SOC, and only decoy ports on B are reachable from A.

**Baseline topology stays:** D1 SSH on TCP 2222, D2 web on TCP 8080, D3 API on TCP 8081 (PROPOSED), SOC loopback only, no uplink, no default gateway, no DNS, no Wi-Fi/Internet sharing.

**New optional component:** OpenCanary container on Laptop B, sensor ID `canary-01`, listening only on non-conflicting ports such as 2223, 8082, 8443. It must not require privileged mode. If it does, cut it.

| Item | Value | Status |
|---|---|---|
| Laptop A (attack) | Kali Linux, 192.168.77.10 | BASELINE |
| Laptop B (SOC + decoys) | Linux VM/host, 192.168.77.20 | BASELINE |
| D1 SSH decoy | TCP 2222 | BASELINE |
| D2 web decoy | TCP 8080 | BASELINE |
| D3 API decoy | TCP 8081 | PROPOSED |
| OpenCanary tripwire | Non-conflicting ports only, no privileged mode | PROPOSED (I-22) |
| SOC API/dashboard | Loopback only | BASELINE |
| Uplink | None | BASELINE |

**Assumption to confirm (RS-12):** port publishing in the chosen VM/WSL2 setup reaches the physical cable and decoys log Laptop A’s true source IP. Subnet 192.168.77.0/24 is a placeholder; use one non-conflicting private subnet in a checked-in configuration.

---

## 3. Decoys

Three baseline decoys plus one optional auxiliary tripwire.

### D1: SSH decoy (Cowrie), BASELINE

Fake Linux server that accepts one seeded login and records everything typed; nothing really runs.

- Cowrie in emulated shell mode only, never proxy mode; JSON log read by adapter; seeded account `dg_demo`.
- PROPOSED: breadcrumb file in fake home mentioning a web portal credential (I-03); richer post-compromise command labels (I-08); Transcript replay (I-16 Must); Native TTY replay (I-16 Stretch); HASSH field on `connection_open`.
- Research (RS-6, RS-15): pinned Cowrie version event coverage, fake filesystem customisation, TTY log availability, `playlog` compatibility, HASSH emission or derivation, whether successful `cat` of a fixture can be proven.

### D2: Web decoy, BASELINE with PROPOSED upgrade

Fake company login site that looks sloppy on purpose, so attackers try injection and hidden paths.

- BASELINE: separate service and origin; fake login; synthetic document endpoint; structured audit log; no shared cookies or secrets with SOC.
- PROPOSED (I-01): endpoints that look vulnerable: search/lookup form (SQLi bait), `file=` download parameter (path traversal/LFI bait), hidden paths such as `/admin`, `/backup.zip`, `/env`, `/.git/HEAD`, plus XSS and RFI bait surfaces.
- Design rule: decoy only decides which fake page to return. SOC backend does classification (R07, R08), so detection has one source of truth.
- **v3.0 addition:** R07 classifies five classes: SQLi, XSS, LFI, RFI, command injection. Findings carry `web_attack_class` as a multi-value field.

**Realism levels remain:** L1 log only, L2 emulated (recommended start), L3 sandboxed real query (needs recorded decision, conflicts with no-real-vulnerable-component rule). Research RS-1, RS-2, RS-14.

### D3: Internal API decoy (I-04), PROPOSED

Fake customer-records service that rewards a curious attacker with fake data.

- Surface: sequential IDs at `/api/users/{id}` (IDOR bait), `customer_data.csv` export, planted `.env` and `backup.zip` with fake tokens.
- Why it helps: v1.0 struggles to prove successful file read over SSH. API decoy records its own response, so verified download is direct R04 evidence.
- Data: deterministic, obviously synthetic records using reserved domains such as `example.com`.
- Build only one third decoy (RS-11). Options: API decoy (recommended), IoT panel, Redis emulator, upload portal. Cut D3 if D1+D2 vertical path is not working by H8.

### D4: OpenCanary auxiliary tripwire (I-22), PROPOSED / conditional

Low-resource Python multi-protocol honeypot.

- Purpose: provide auxiliary reconnaissance telemetry without a dedicated network sensor, partially addressing Parked I-21.
- Scope: only non-privileged modules. HTTP/SMB/SNMP-style tripwire events on non-conflicting ports. Portscan module only if it works without `NET_ADMIN`/privileged mode; otherwise omit.
- Events use sensor ID `canary-01`, provenance `auxiliary_tripwire`, and do **not** participate in R01–R10 scoring.
- Cut if: requires privileged container, interferes with D1–D3 binds, or cannot log true source IPs.

---

## 4. Detection and ATT&CK mapping

Detection stays deterministic and evidence-gated: every finding records its rule version, supporting event IDs, and a limit on what it proves.

**v3.0 mapping upgrade:** `technique_ids` remain, but findings gain `detection_strategy_refs`, for example:

```json
{
  "technique": "T1110.001",
  "strategy": "DS-T1110.001-001",
  "analytic": "A1",
  "rule_id": "R01",
  "provisional": true
}
```

If official Strategy/Analytic IDs are unavailable, use provisional team IDs and mark `provisional: true`. Navigator layer comments cite the Strategy/Analytic name.

### Rules

| Rule | Status | Trigger and evidence | ATT&CK | Does not prove |
|---|---|---|---|---|
| R01 | BASELINE | 5+ distinct failed SSH logins in inclusive 60 s window, same sensor/source/username | T1110.001 | Compromised account |
| R02 | BASELINE | Command input in authenticated Cowrie session | T1059.004 | Execution on real host |
| R03 | BASELINE | Parsed `ls` or `find` in fake shell | T1083 | More than discovery attempt |
| R04 | BASELINE | Verified synthetic asset access | T1005 / T1105 as applicable | Real data access |
| R05 | BASELINE | Confirmed cross-decoy link | — | One person or real compromise |
| R06 | STRETCH | Network scan only with network sensor | T1046 | — |
| R07 | PROPOSED (I-01) | Web exploit attempt, **five classes**: SQLi, XSS, LFI, RFI, command injection; finding has `web_attack_class` multi-label | T1190; XSS T1059.007; RFI T1105; LFI T1005 | Successful exploitation |
| R08 | PROPOSED (I-02) | Burst of hidden-path requests; labelled “web path probing”, never “scan alert” | T1595 / T1083 reconnaissance | Scan without network sensor |
| R09 | PROPOSED (I-03) | Honeytoken reuse across decoys; candidate link carries `plausibility_tier` and `placement_context` | — | One person or real compromise |
| R10 | PROPOSED (I-08) | Parsed post-compromise commands: download T1105, cron T1053.003, account listing T1087.001, account creation T1136.001 | As listed | Execution; commands only submitted to emulation |

### Labels, not findings, and never scored

- **Noise vs targeted (I-09):** hypothesis with signals. Noise-like: one decoy, generic usernames/paths, fast repetitive. Targeted-like: used planted breadcrumb, touched several decoys, followed seeded trail.
- **Bot vs human (I-10):** from command gaps, claimed SSH client string, and **HASSH claimed fingerprint** when available. Always shown as claimed or inferred.
- Tool names such as sqlmap, hydra, gobuster appear only from explicit User-Agent or client metadata, labelled claimed.

**Kill-chain labels:** Web exploit attempt maps to Exploitation attempt. Web path probing maps to Reconnaissance and is named “web path probing”. Installation and Command and Control stay not observed.

Research RS-9: which signals are defensible in a lab where all traffic is ours.

---

## 5. Correlation and honeytoken breadcrumbs

Correlation stays conservative: sessions are exact, cross-decoy links start as candidates, and only an analyst turns a candidate into a confirmed link.

**Baseline rules:** session = sensor ID + source session ID; missing IDs use five-minute heuristic bucket marked `grouping_basis=heuristic`. R01 may span sessions and links to a credential-attempt incident keyed by sensor/source/username. Same source IP within five minutes gives a dashed candidate edge only. Analyst confirmation records rationale, creates parent investigation, keeps child IDs, and can be reversed.

### Honeytoken breadcrumb chain (I-03), PROPOSED

Plant a fake credential in one decoy. If it shows up in another decoy, the attacker followed our trail, which is stronger than sharing an IP.

1. Token registry fixture lists each token: ID, where planted, where valid, **`plausibility_tier`**, **`placement_context`**.
2. Sensor or adapter compares presented credential with registry and sets `attributes.honeytoken_id`. Credential value is never stored.
3. When token planted in one decoy appears on another, backend creates strong-candidate link carrying both event IDs.
4. Analyst confirms or rejects as usual. R05 scores only after confirmation.

**v3.0 addition:** `plausibility_tier` values: `obvious`, `moderate`, `high`. `placement_context` examples: “SSH home `notes.txt`”, “D2 `.env` backup”, “D3 CSV export comment”. R09 candidate UI displays “token reuse detected (moderate plausibility)”. This does **not** auto-confirm.

| State | Display | Score effect |
|---|---|---|
| Exact same sensor session | Solid edge | Findings score normally |
| Same IP and time window | Dashed candidate edge | None |
| Token reuse across decoys | Dashed strong-candidate edge with token label and plausibility | R09 once, after confirmation |
| Analyst confirmed with rationale | Confirmed edge with operator/time | R05 once |
| Rejected or ambiguous | Rejected edge in audit only | None |

Research RS-4, RS-5: token design, detecting note read when SSH read success cannot be proven, whether token links may auto-confirm (default no), avoiding double counting R05 and R09, and how plausibility affects false-positive rate.

---

## 6. Risk scoring

Transparent 0–100 triage index. v1.0 weights unchanged; each new rule is a separate category counted once per investigation.

| Rule | Weight | Counted | Status |
|---|---|---|---|
| R01 repeated SSH guessing | 25 | Once after threshold | BASELINE |
| R02 command in emulated shell | 15 | Once | BASELINE |
| R03 discovery attempt | 10 | Once | BASELINE |
| R04 verified synthetic asset access | 30 | Once across all decoys | BASELINE |
| R05 confirmed cross-decoy link | 15 | Once | BASELINE |
| R06 network scan | 5 | Only with network sensor | STRETCH |
| R07 web exploit attempt | 15 | Once | PROPOSED |
| R08 web path probing | 5 | Once | PROPOSED |
| R09 honeytoken reuse | 15 | Once after confirmation | PROPOSED |
| R10 post-compromise command labels | 10 | Once for any listed category | PROPOSED |

Severity thresholds unchanged: low 0–24, medium 25–49, high 50–79, critical 80–100. Baseline max 95. With all proposed rules raw sum 140, capped at 100. Duplicates, repeated payloads, extra sessions, containment events never add points.

**Worked example (Option A, v1.0 weights kept):**

| Step | Evidence | Points | Total | Severity |
|---|---|---|---|---|
| 1 | Five failed SSH logins in 60 s (R01) | +25 | 25 | Medium |
| 2 | Shell command after seeded login (R02) | +15 | 40 | Medium |
| 3 | `ls` in fake shell (R03) | +10 | 50 | High |
| 4 | Planted token used on web login (R09) | +15 | 65 | High |
| 5 | SQLi payload on web decoy (R07) | +15 | 80 | Critical |
| 6 | Analyst confirms cross-decoy link (R05) | +15 | 95 | Critical |
| 7 | Verified `customer_data.csv` download (R04) | +30, capped | 100 | Critical |

Decision RS-8: Option A recommended (keep weights, accept saturation); Option B rebalance all to sum 100 (requires rewriting AC03/AC08 examples). Keep weights in versioned configuration, never change to make demo dramatic.

---

## 7. Events, backend, and API

v1.0/v2.0 contract does not change: new modules add optional attributes and sensor IDs, not new event types or incompatible routes.

**Baseline pipeline:** sensor log → adapter (checkpoint, bounded spool, redaction, stable `source_record_id`) → `POST /api/ingest/events` → validation/dedup → SQLite WAL one writer → rules/correlation/risk → durable outbox → REST/WebSocket → React. Events immutable; findings/incidents/links versioned.

**Fixed conventions:** `/api` and `/ws/events` as in v1.0 plus auth, ingest, heartbeat, incident update, correlation decision, analyze, response preview/apply/revoke. `snake_case` JSON, RFC 3339 UTC, `schema_version 1.0`, backend-issued IDs, shared fixtures in `contracts/`. Limits: 100 records or 1 MiB per request, 16 KiB per record, 4 KiB for commands/paths.

**Sensor IDs:** `ssh-decoy-01`, `web-decoy-01` (BASELINE), `api-decoy-01` (PROPOSED), `canary-01` (PROPOSED, auxiliary).

**New optional fields inside `attributes`:**

| Field | On event types | Meaning | Idea |
|---|---|---|---|
| `method`, `path`, `query_redacted`, `user_agent`, `status_code` | `http_request` | Request metadata | I-01, I-02 |
| `response_class` | `http_request` | `normal`, `fake_error`, `fake_data`, `blocked`, `llm_generated` | I-01, I-23 |
| `web_attack_class` | `http_request` | Multi-value: `sqli`, `xss`, `lfi`, `rfi`, `cmd_injection` | I-01 |
| `honeytoken_id` | `auth_failure`, `auth_success`, `http_request` | Registry ID; value never stored | I-03 |
| `honeytoken_plausibility` | same | `obvious`, `moderate`, `high` | I-03 |
| `asset_id`, `direction`, `size_bytes`, `sha256`, `outcome` | `synthetic_file_access`, `file_transfer` | D3 download is direct success evidence | I-04 |
| `client_version` | `connection_open` | Claimed SSH client string | I-10 |
| `hassh` | `connection_open` | Claimed SSH client fingerprint | I-10 |
| `detection_strategy_refs` | findings | Strategy/Analytic references | I-12 |
| `provenance` | auxiliary events | `auxiliary_tripwire` for OpenCanary | I-22 |

**Proposed additive routes (each needs change note and review by M1/M3):**

- `GET /api/stats/overview`: raw event count, incident count, noise ratio, technique counts, stage by source, time to first alert (I-11, I-12, I-13, I-17).
- `GET /api/incidents/{id}/export?format=json|stix|attack-layer`; default JSON (I-12, I-14).

Research RS-13: check whether existing endpoints already supply what new components need, so no new route is required.

---

## 8. Dashboard

Keeps v1.0 views and adds six small components plus v3.0 forensic upgrades.

**BASELINE views:** Overview, Live Events, Incident Investigation, Attack Graph, Source Profiles, Sensor Health, Response Center, with loading/empty/error/stale/disconnected/replay states, LIVE/REPLAY label on every screen, escaped attacker text, every number derived from API. Frontend never calculates risk or decides block worked.

| Component | What it shows | Data | Idea |
|---|---|---|---|
| Kill-chain progress bar | Per source: Recon, Credential attack, Exploit attempt, Post-access, Data access; unobserved greyed | Findings + stage labels | I-11 |
| ATT&CK heatmap | Techniques observed grouped by tactic; click opens evidence; comments cite Strategy/Analytic | `technique_ids`, `detection_strategy_refs` | I-12 |
| Noise-reduction counter | N raw events → M incidents, K low-priority noise | Stats route | I-13 |
| SSH session replay | **Transcript replay** from stored command events; **Native TTY replay** only when Cowrie TTY volume available (Stretch); HASSH shown as claimed fingerprint | Command events, TTY logs, `hassh` | I-16 |
| Time metrics | Time to first alert, attacker dwell time per source | Event timestamps | I-17 |
| Isolation panel | Pass/fail per boundary check | Preflight report from M2 | I-18 |

Build kill-chain bar and noise counter first. Truthful labels stay: “command submitted to emulated shell”, “synthetic file served”, “source profile”, never “attacker isolated” for a web block.

Research RS-13: data paths for replay and isolation panel; RS-15: TTY availability.

---

## 9. AI analyst and manual response

AI explains existing findings and never acts; only response is manual, previewed, time-limited block on web decoy, as in v1.0.

**Baseline AI:** input frozen incident revision; output structured JSON where every claim cites supplied event IDs. 20 s timeout then labelled Rule summary fallback. Prompt injection hidden in logs tested. AI cannot change scores, confirm links, or call response executor. Core demo works offline.

**Baseline response:** only `block_source_web` and `revoke_block`. Preview expires 60 s; default TTL 120 s (range 30–300 s). Approval needs reason, fresh preview, expected incident revision; apply idempotent. Verification needs matching blocked-request event. Undo/expiry keep audit history. Targets exact lab IPs, never ranges, defender, gateway, or management addresses.

**PROPOSED:** firewall snippet (I-15) shown as copy-paste nftables rule labelled recommended, not applied; built only from validated lab IP. Prompt updates may mention honeytoken reuse or web exploit attempts only when citing events, and must present noise-vs-targeted as hypothesis. Block stays web-decoy only.

**STRETCH (I-23):** controlled LLM response generator for D2, isolated read-only container, no outbound network, no SOC credentials. LLM only generates HTTP response body; never executes input; response labelled `response_class: llm_generated`; never counts as R04. Requires prompt-injection and isolation proof before demo. Otherwise Parked.

---

## 10. Exports and threat intelligence

Sanitised JSON is BASELINE; STIX 2.1 and ATT&CK Navigator layer are PROPOSED.

| Export | Status | Contents | Research/limits |
|---|---|---|---|
| Incident JSON | BASELINE | Manifest, rule/mapping versions, score components, audit trail, LIVE/REPLAY labels; no secrets | Already in v1.0 |
| STIX 2.1 bundle (I-14) | PROPOSED | Indicators for observed source IPs/paths, attack-pattern objects for technique IDs, observed-data/relationships, lab/simulated marker | Private lab IPs demonstrate format only; check `stix2` library and validator (RS-10) |
| ATT&CK Navigator layer (I-12) | PROPOSED | Observed techniques with comments linking to rules **and Strategy/Analytic names** | Check current layer format and test import (RS-10, RS-17) |

All exports sanitised: no passwords/session tokens, escaped text, honeytoken IDs but never values. Every file states simulated lab origin.

---

## 11. Safety and isolation

v1.0/v2.0 safety rules do not loosen; new modules add specific risks.

**BASELINE rules:** operate only in authorised isolated lab; no scanning campus/public systems, no public honeypot, no production data/credentials, no autonomous response. From Laptop A only decoy ports reachable; management off that network. Decoys no route to Internet/database/management. Non-root services, no privileged containers, no Docker socket, no shared real credentials. Captured commands/files never executed; attacker URLs never fetched; passwords/tokens redacted before storage. Cowrie emulated only. Responses use exact lab IP allowlists.

**New risks and mitigations:**

| Risk | Module | Mitigation |
|---|---|---|
| Emulated vulnerability becomes real | I-01 L3 | Start at L2. If L3 built: read-only in-memory data, SQLite authorizer denying ATTACH/PRAGMA/writes, query timeout, separate container no network, recorded decision |
| Decoy used as pivot | I-04 D3 | No outbound route, no SOC/real credentials in any decoy, planted `.env` fake tokens only |
| Fake secrets look real | I-03, I-04 | Obvious lab prefixes, never real key formats, kept only in fixtures |
| Fake data resembles real people | I-04 | Deterministic synthetic generator, reserved domains such as `example.com` |
| Hostile uploads stored | I-07 | Hash and size only, private quarantine, never opened/executed |
| Extra port widens exposure | I-04 | Add 8081 to firewall allowlist, bind check, AC01 proof |
| Response feedback loop | I-15 | Blocked-request/controller events never add score or trigger actions |
| OpenCanary requires privileged mode | I-22 | Omit portscan module if privileged; use only non-privileged modules; cut if it interferes with D1–D3 |
| LLM response leaks or executes input | I-23 Stretch | Separate container, no outbound network, no SOC credentials, read-only prompt, `llm_generated` label, never R04, prompt-injection tests |

If any isolation check fails, stop scenario and fix environment before any traffic.

---

## 12. Attack scenarios, personas, and evaluation

Evaluation uses labelled scenario runs and scripted Kali personas; precision and recall reported from counts and misses listed, never broad accuracy.

**BASELINE scenarios (v1.0, 12):** quiet connection, maintenance probe, four failures, five failures, different usernames, directory discovery, unsuccessful file read, successful synthetic file access, two-decoy candidate, confirmed lab relationship, unrelated NAT clients, approved containment with undo. Plus inert upload/download capability test.

**PROPOSED scenarios:**

| ID | Scenario | Expected |
|---|---|---|
| S13 | SQLi, traversal, XSS, RFI, and command-injection probes on web decoy | R07 fires for each class; `web_attack_class` multi-label |
| S14 | Burst of hidden-path requests | R08 fires |
| S15 | One missing page | No R08 (negative test) |
| S16 | Token planted over SSH, then used on web login | R09 + strong-candidate link; no auto-confirm |
| S17 | Token used on decoy where planted | No R09 (negative test) |
| S18 | `wget`, `crontab`, `cat /etc/passwd`, `useradd` in fake shell | R10 labels; nothing executes |
| S19 | Sequential `/api/users/{id}`, then CSV download | R04 through verified API response |
| S20 | Mixed run of all three personas | Distinct severity outcomes |
| S21 | Benign search input and normal file download | No R07; AC23 negative test |
| S22 | Same attacker returns with same HASSH but different claimed client version | Source Profile shows same HASSH as claimed fingerprint, not identity |
| S23 | OpenCanary tripwire hit on non-decoy port | Auxiliary event with `provenance: auxiliary_tripwire`, no score change |

**Kali personas (I-19):** scripts only run against lab address and refuse any other target.

| Persona | Behaviour | Typical tools | Expected dashboard result |
|---|---|---|---|
| P1 Bot scanner | Fast path probing, default creds, no shell | gobuster/ffuf, hydra | Low–medium; R08, R01; noise-like |
| P2 Credential stuffer | Wordlist logins on SSH/web, no breadcrumb | hydra | Medium; R01 |
| P3 Targeted human | Slow; reads note, reuses token, SQLi, downloads data | ssh, curl, sqlmap | Critical; R09, R07, R04; targeted-like |

**Metrics:** precision = TP/(TP+FP), recall = TP/(TP+FN) per scenario, with scenario count and positive definition. Report N/A when denominator zero. p50/p95/max for event-to-finding and backend-to-browser latency on recorded hardware. Time to first alert and attacker dwell time per source. Incorrectly confirmed links counted separately from correctly surfaced candidates. Live and replay never mixed in one claim.

---

## 13. Roles and ownership

Folder ownership as in v1.0; new tasks assigned below; names at kickoff.

| Role | Owns | New tasks |
|---|---|---|
| M1 Frontend/UX | `frontend/` | Kill-chain bar, ATT&CK heatmap, noise counter, transcript replay, native TTY replay (Stretch), time metrics, isolation panel, strong-candidate edge style, HASSH display, plausibility label |
| M2 Security/sensors | `sensors/`, `decoys/`, `deployment/` | L2 emulated endpoints, D3 API decoy, token registry/plants/plausibility fields, Cowrie breadcrumb file, TTY volume access (Stretch), HASSH verification, port 8081 allowlist, OpenCanary non-privileged setup, preflight report, target checks in persona scripts |
| M3 Backend/detection | `backend/`, `contracts/` | R07 five-class classifier, R08 separation, R09 plausibility-aware candidate links, R10, `detection_strategy_refs`, stats route, STIX and Navigator exporters (with Strategy comments), config-driven weights |
| M4 AI/response/integration | `analyst/`, `response/`, `scenarios/`, `tests/e2e/`, `docs/` | Persona scripts, S13–S23, AI prompt updates, firewall snippet, LLM isolation tests if I-23 explored, evaluation report, clean-start rehearsal |

Any contract change needs short written note in `docs/decisions`, updated schema/example, and review by affected owners before merge. One focused branch per role; merge early.

---

## 14. Milestones and decision gates

24-hour plan keeps v1.0 order and adds gates. Hours count from actual start; if hours differ, scale phases but keep gates.

1. **G1 at H1, freeze:** schema v1.0, ports, weights as configuration, fixture IDs fixed; team votes keep/cut on every idea in section 15; roles assigned.
2. **G2 at H4, vertical path:** one real SSH interaction appears in dashboard with evidence ID. If slips past H6, drop every Should and If-ahead idea.
3. **G3 at H12, idea cut-off:** both baseline decoys live and R01–R05 pass tests. Only Must ideas may still start; anything half-built finished or cut by H16.
4. **G4 at H20, feature freeze:** no new features; only load measurement, isolation proof, clean-start rehearsal, demo script.

Cut order if behind: chart polish, native TTY replay, STIX, extra personas, D3, OpenCanary, firewall snippet, LLM experiment. Must ideas go last. Keep evidence graph, JSON export, rule-summary fallback, honest unavailable states; never fake live telemetry.

---

## 15. Idea register

Every idea appears once with keep-if and cut-if; set Team decision column during discussion. Tiers: Must, Should, If ahead, Parked. Effort: L under 2 hours, M 2–6 hours, H over 6 hours.

| ID | Idea | Tier | Effort | Keep if | Cut if | Team decision |
|---|---|---|---|---|---|---|
| I-01 | Fake-vulnerable web decoy with **five classes** (SQLi, XSS, LFI, RFI, cmd injection) | Must | M | L2 prototype gives plausible responses to manual payloads by H8; five-class classifier passes AC23 | Cannot be made safe, or tests show nothing useful | Undecided |
| I-02 | Web path probing detection R08 | Must | L | Burst and single missing page separate cleanly | Thresholds cannot tell scan from curiosity | Undecided |
| I-03 | Honeytoken breadcrumb chain, R09, **plausibility metadata** | Must | M | Reuse detectable without storing secrets; plausibility improves analyst context | Reuse cannot be detected reliably, or double counts with R05 | Undecided |
| I-04 | D3 internal API decoy | Should | M | Vertical path works by H8 and reuses D2 code | G2 slips, or D2 not stable by H8 | Undecided |
| I-05 | D3 option: IoT panel | If ahead | M | Chosen over I-04 | I-04 chosen | Undecided |
| I-06 | D3 option: Redis emulator | If ahead | M | Chosen over I-04 | I-04 chosen, or protocol work runs long | Undecided |
| I-07 | D3 option: upload portal | If ahead | M | Chosen over I-04 | Uploads cannot be kept inert | Undecided |
| I-08 | Richer post-compromise command labels R10 | Should | L | Existing parser handles them | Needs new shell parser | Undecided |
| I-09 | Noise-vs-targeted hypothesis label | Should | M | Personas separate in tests | Signals unconvincing when all traffic is ours | Undecided |
| I-10 | Bot-vs-human hint, **including HASSH claimed fingerprint** | If ahead | L | Command timing and HASSH logged reliably | Timing/HASSH unavailable | Undecided |
| I-11 | Kill-chain progress bar | Must | L | Stage labels derive from findings | Stages cannot be derived from API data | Undecided |
| I-12 | ATT&CK heatmap and Navigator layer **with Strategy/Analytic comments** | Should | L | `technique_ids` and `detection_strategy_refs` on findings; layer imports | Layer fails to import | Undecided |
| I-13 | Noise-reduction counter | Should | L | Stats route works | Stats route not ready | Undecided |
| I-14 | STIX 2.1 export | If ahead | M | Validator passes | STIX library unreliable | Undecided |
| I-15 | Firewall snippet, recommendation only | If ahead | L | Exact nftables syntax verified | Syntax unverified or suggests auto-apply | Undecided |
| I-16 | Session replay: **Transcript Must; Native TTY Stretch** | Must / Stretch | M | Transcript works from command events; TTY volume available for Stretch | Transcript data insufficient; TTY unavailable | Undecided |
| I-17 | Time metrics | Should | L | Event timestamps reliable | Timestamps missing | Undecided |
| I-18 | Isolation panel | Should | M | Preflight report available | Data path undecided | Undecided |
| I-19 | Scripted Kali personas | Should | M | Scripts refuse non-lab targets | Scripts cannot enforce target check | Undecided |
| I-20 | Progressive deception | Parked | — | — | — | Parked |
| I-21 | Network scan detection R06 | Parked | — | — | — | Parked |
| I-22 | **OpenCanary auxiliary tripwire** | Should / conditional | M | Non-privileged modules work, true source IP logged, no interference with D1–D3 | Requires privileged mode or interferes with binds | Undecided |
| I-23 | **LLM response generator for D2** | Stretch / Parked | H | Isolation and prompt-injection tests pass; only then experiment | Cannot guarantee no execution/no outbound | Undecided |

---

## 16. Deep research agenda

Answers decide keep/cut. Run items needed by H4 first because they gate contracts and ports. Each answer ends as a short note in `docs/decisions` with evidence.

- **RS-1, RS-2:** Web payload normalisation; Snare/Tanner prior art; sqlmap reactions to L2; whether L3 can be locked down.
- **RS-4, RS-5:** Honeytoken design (unique per run, believable, safe), detecting note read when SSH read success cannot be proven, whether token links may auto-confirm (default no), avoiding R05/R09 double counting, **and how `plausibility_tier` affects false-positive rate**.
- **RS-6:** Pinned Cowrie version: which events logged, fake filesystem customisation, TTY logs, whether successful `cat` of fixture can be proven.
- **RS-7, RS-17:** ATT&CK technique IDs verification; **v18 Detection Strategy/Analytic ID availability and provisional ID policy**.
- **RS-8:** Scoring Option A vs B.
- **RS-9:** Which signals are defensible when all traffic is ours.
- **RS-10:** `stix2` library and validator; Navigator layer format version and import test.
- **RS-11:** Which third decoy to build.
- **RS-12:** VM/WSL2 port publishing reaches physical cable; true source IP logging.
- **RS-13:** Whether existing endpoints already supply what new components need; data paths for replay and isolation panel.
- **RS-14 (new):** Tanner-style five-class web regex false-positive rate on this lab’s benign traffic; encoding normalisation rules.
- **RS-15 (new):** Pinned Cowrie version native TTY log availability, `playlog` compatibility, HASSH emission or derivation.
- **RS-16 (new):** OpenCanary visibility under Docker/WSL2, true source IP logging, whether non-privileged modules suffice, and whether portscan module requires privileged mode.
- **RS-18 (new):** If I-23 explored, whether LLM responses measurably change attacker behaviour and whether isolation holds under prompt injection.

---

## 17. Open decisions and risks

| # | Decision | Default if undecided | Decide by |
|---|---|---|---|
| 1 | Build third decoy, and which | API decoy I-04 | G1 |
| 2 | Realism level for web vulnerabilities | L2 emulated | G1 |
| 3 | Add port 8081 to allowlist/AC01 | Yes, only if D3 built | G1 |
| 4 | Scoring Option A or B | Option A | G1 |
| 5 | New stats route or derive from existing | Add `GET /api/stats/overview` | G1 |
| 6 | Token links auto-confirm | No, analyst confirms | G1 |
| 7 | Real build hours and G3 cut-off | H12 of 24 | G1 |
| 8 | Defender runtime | Tested Linux VM | G1 |
| 9 | Extend web block to D3 | No | G3 |
| 10 | AI provider | Rule-summary fallback only | G3 |
| 11 (new) | OpenCanary included, and which modules | Include only if non-privileged and no interference | G3 |
| 12 (new) | LLM response experiment | Parked unless all Must/Should stable and isolation proven | G3 |

**Risks:** scope too large for 24 hours → incomplete demo; mitigation: gates, cut order, Must ideas only. New: five-class web classifier increases false positives → mitigate with labelled negative tests and AC23. OpenCanary privileged requirement → cut if privileged. LLM experiment scope creep → keep Stretch/Parked.

---

## 18. Parked ideas and out of scope

**Parked:**

- Progressive deception (I-20): deeper fake files after stage; needs per-attacker state; adds little to demo.
- Network scan detection (I-21, R06): needs network collector; web path probing R08 covers reconnaissance instead; OpenCanary may partially substitute if non-privileged.
- **Koney/Kubernetes decoy orchestration (new):** future multi-service, multi-instance, stage-aware decoy deployment. Explicitly not in 24-hour plan.

**Out of scope:** public honeypot or scanning campus/external networks; exploitation of real services, running real vulnerable software, executing uploads/captured commands; production credentials/data, enterprise firewall changes, automatic host isolation; autonomous AI response, model training, calibrated threat probabilities, IP reputation for private addresses; full T-Pot/Elastic/Security Onion installation; automatically applying firewall snippet; **auto-confirming honeytoken links**; **full SOAR automation**; **TAXII live push**; **UEBA anomaly scoring** in 24-hour version.

---

## 19. Acceptance criteria

v1.0/v2.0 criteria AC01–AC22 stand. AC23–AC27 added only for kept ideas; each needs recorded proof before done.

| ID | Pass condition | Proof and owner | Status |
|---|---|---|---|
| AC01 | Only lab decoy ports reachable from Kali; no production route or decoy pivot | Route/bind/firewall record + boundary tests; M2 | BASELINE |
| AC02 | Live SSH interaction reaches stored evidence and React without mocks | Event ID across source log, API, browser; M2/M3/M1 | BASELINE |
| AC03 | Five failures trigger R01, four do not, duplicates do not change score | Boundary/replay test report; M3 | BASELINE |
| AC04 | Every ATT&CK/stage label has rule, evidence, limitation; no scan alert without network sensor | Mapping validation + negative test; M3 | BASELINE |
| AC05 | Both decoys produce genuine events; synthetic file metadata inspectable | SSH/web IDs, inert file hash, fixture manifest; M2 | BASELINE |
| AC06 | Same IP alone stays candidate; confirmation creates parent; NAT test avoids false confirmed link | Graph screenshots + relationship audit; M3/M1 | BASELINE |
| AC07 | Source profile and lab auxiliary telemetry shown with provenance | Profile export + explicit production not checked; M2/M3 | BASELINE |
| AC08 | Risk components reproduce worked example and stay stable on retries | Deterministic fixture output; M3 | BASELINE |
| AC09 | AI citations resolve; invalid output falls back; AI changes no detection/response | Validation + prompt-injection results; M4 | BASELINE |
| AC10 | Fresh manual approval applies web-only block; next request rejected; TTL/undo restore access | Action ID, policy revision, request evidence; M4/M2 | BASELINE |
| AC11 | Reconnect restores missed IDs; stale/offline state accurate | Socket interruption test + UI evidence; M1/M3 | BASELINE |
| AC12 | Measured load/freshness meet targets or shortfall documented | Hardware + percentile report; M4 | BASELINE |
| AC13 | Export traceable, secret-free, LIVE/REPLAY labels | Sanitised JSON + evidence manifest; M3/M4 | BASELINE |
| AC14 | Another teammate completes demo from README | Clean-start rehearsal signed off by non-owner; all | BASELINE |
| AC15 | Each signature class in labelled payload set fires R07; benign inputs do not; decoy never executes input | Payload test report; M2/M3 | PROPOSED |
| AC16 | Burst of hidden paths fires R08; one missing page does not; finding labelled web path probing | S14/S15; M3/M4 | PROPOSED |
| AC17 | Token reuse on another decoy creates strong-candidate link and R09; same-decoy reuse does not; no credential value stored | S16/S17 + storage check; M2/M3 | PROPOSED |
| AC18–AC22 | As in v2.0 for D3, firewall snippet, STIX, personas, replay | As v2.0 | PROPOSED |
| **AC23** | R07 fires for SQLi, XSS, LFI, RFI, and command injection in labelled payload set; benign search/download do not; decoy never executes input | Payload test report + negative tests; M2/M3 | PROPOSED |
| **AC24** | Native TTY replay, if built, traceable to Cowrie logs; HASSH labelled claimed fingerprint; no identity claim | Log trace + UI label; M2/M1 | PROPOSED / STRETCH |
| **AC25** | Every finding’s Strategy/Analytic reference resolves in mapping catalogue; Navigator layer imports with comments | Mapping validation + import test; M3 | PROPOSED |
| **AC26** | OpenCanary events carry `auxiliary_tripwire` provenance, do not affect score, require no privileged container, and do not interfere with D1–D3 | Event audit + container config + bind test; M2/M3 | PROPOSED |
| **AC27** | LLM response generator, if explored, passes isolation and prompt-injection tests and never produces R04-scoring evidence | Isolation proof + test report; M4/M2 | STRETCH |