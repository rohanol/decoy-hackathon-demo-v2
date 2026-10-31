# AGENTS.md: DeceptionGraph SOC rules for every coding assistant

D3COY PS 04. Four people, 24 hours. This file is the source of truth for the build. `docs/prd/PRD_v3.0.md` and the old master prompt are background reading only. If they say something different from this file, this file wins. Safety rules in section 6 beat everything.

Claude Code reads `CLAUDE.md`, which imports this file. Other assistants (Codex, Cursor, Gemini) read this file directly or you paste it first.

## 1. The project in six lines

- Laptop A (Kali, 192.168.77.10) attacks. Laptop B (192.168.77.20) runs the decoys and the SOC. One ethernet cable, no internet on the lab link.
- Decoys: Cowrie SSH on 2222 (`ssh-decoy-01`), Flask web decoy on 8080 (`web-decoy-01`). No third decoy.
- Flow: decoy log → adapter → `POST /api/ingest/events` → FastAPI + SQLite → rules → incidents → REST and `/ws/events` → React.
- First milestone (H4): one real SSH login from Kali visible on the dashboard with its event ID.
- The only response is a manual, previewed, 120 s block of one IP on the web decoy, with undo.
- Incident summaries are rule-generated text. An LLM summary is optional and never acts.

Demo story: SSH brute force → login → `ls` → `cat notes.txt` finds a portal password → password reused on web login → SQLi on search → `customer_data.csv` downloaded → analyst confirms the cross-decoy link → block → next request rejected → undo.

## 2. Who owns what

| Folder | Owner | What |
|---|---|---|
| `contracts/`, `backend/`, `config/scoring.yaml` | Rohan (M3) | Schemas, API, ingest, dedup, rules, scoring, incidents, links, WebSocket |
| `frontend/`, `docs/demo/` | Pashmee (M1) | Design first, then the whole React dashboard (all screens, all code), deck, demo script visuals. Rohan supplies API, types, fixtures only |
| `sensors/`, `deployment/`, `decoys/ssh/`, `decoys/policy/`, `response/` | Vedant (M2) | Network, Cowrie, log adapter, compose, preflight, blocklist and the whole block flow |
| `decoys/web/`, `analyst/`, `scenarios/`, `tests/e2e/`, `config/web_patterns.yaml`, `config/honeytokens.yaml`, `contracts/examples/payloads.json` | Prajwal (M4) | Web bait, fake data, token plants, attack patterns, rule summary, attack scripts, end-to-end runs |

Other people's folders are read-only for you. Need a change there? Tell the owner, or open a PR they review. Never resolve a merge conflict by deleting someone else's change.

## 3. Frozen interfaces (change by PR plus Rohan's OK)

| Thing | Where |
|---|---|
| Event schema, `schema_version` "1.0" | `contracts/event.schema.json` |
| Finding schema | `contracts/finding.schema.json` |
| Routes, WebSocket messages, blocklist file format | `contracts/API.md` |
| Example events for development | `contracts/examples/events_p3.json` |
| Score weights and thresholds | `config/scoring.yaml` |
| Honeytokens (hashes only) | `config/honeytokens.yaml` |
| Web attack regexes and hidden paths | `config/web_patterns.yaml` |
| Ports | 2222 and 8080 bound to 192.168.77.20. Backend 8000 and Vite 5173 bound to 127.0.0.1 |

A contract PR changes the file and its example in the same PR and says in one line what breaks. No decision documents needed.

## 4. Rules (all deterministic, all in `backend/rules/`)

| Rule | Fires when | ATT&CK | Kill-chain stage | Never claim |
|---|---|---|---|---|
| R01 | 5+ `auth_failure` on `ssh-decoy-01`, same src_ip + username, within 60 s inclusive | T1110.001 | credential_attack | account compromised |
| R02 | `command_input` in a session that had `auth_success` | T1059.004 | post_access | real execution |
| R03 | command starts with `ls` or `find` | T1083 | post_access | more than a discovery attempt |
| R04 | `synthetic_file_access` with `outcome` = "served" | T1005 | data_access | real data stolen |
| R05 | analyst confirms a cross-decoy link | none | none | same person |
| R07 | URL-decoded path or query matches any class in `config/web_patterns.yaml`; all matching classes go in `web_attack_class` | T1190 (+T1059.007 xss, +T1105 rfi) | exploit_attempt | successful exploitation |
| R08 | 5+ hidden-path requests from one src_ip in 60 s, or 10+ 404s in 60 s | T1595.003 | recon | network scan |
| R09 | honeytoken planted on one sensor is presented on the other | none | none | same person |

Scoring: each rule counts once per incident, weights from `config/scoring.yaml`, cap 100. R05 and R09 count only after the analyst confirms the link. Duplicates and `blocked_request` events never add points. One incident per src_ip per `lab_run_id`.

Links: same src_ip on both sensors within 5 min = `candidate`. Honeytoken reuse = `strong_candidate`. Only the analyst sets `confirmed` or `rejected`.

## 5. Must ship / do not build

Must ship, in this order:
1. H4: SSH event visible (dashboard if ready, otherwise `/docs` or `GET /api/events`).
2. H8: web decoy with bait, R07, R08.
3. H12: R01 to R09, scoring, links, confirm button, full demo path working once.
4. Dashboard: live feed, incident page (evidence + score breakdown), attack graph (dashed candidate, solid confirmed), kill-chain bar, noise counter, SSH transcript replay, block button.
5. Block flow: preview → approve with reason → web decoy returns 403 → `blocked_request` shows up → undo or 120 s expiry.
6. Rule-based incident summary.
7. H20 feature freeze. Demo runs clean from a fresh start using `scenarios/demo_p3.md`.

Do not build: OpenCanary, a third decoy, LLM decoy responses, native TTY replay, HASSH, STIX, Navigator export, Detection Strategy refs, bot-vs-human, isolation panel, latency or precision/recall reports, login/CSRF for the SOC, outbox tables, Kafka, Elastic, Postgres, Redis, Kubernetes.

If ahead at H16, ask the team first, then maybe: R10 (wget/crontab/useradd labels), ATT&CK heatmap, LLM summary (needs API credit; Claude Pro does not include API).

## 6. Safety (never break)

- Lab cable only. Laptop B has Wi-Fi off and no default route during runs.
- Attack scripts hardcode 192.168.77.20 and exit if given anything else.
- Cowrie in emulated shell mode only. No privileged containers, no Docker socket mounted.
- Never execute, eval, shell out with, or fetch anything an attacker sends. Decoys return canned responses only.
- Store sha256 of presented passwords and tokens, never the values.
- Fake secrets use the `DGLAB-` prefix. Fake people use `example.com` emails.
- Escape all attacker text in the UI (React default; never `dangerouslySetInnerHTML`).
- Block exact lab IPs only. Never 192.168.77.20, 127.0.0.1 or a range.

## 7. Labels must match evidence

Say "command submitted to emulated shell", "synthetic file served", "web attack attempt", "candidate link". Never "attacker isolated", "compromised", "exploited", "identified".

## 8. Git

- Private repo. Nobody pushes to `main`. Branch `m3/ingest`, `m1/live-feed` and so on.
- Commits `feat: ...`, `fix: ...`, `test: ...`, `docs: ...`, `chore: ...`.
- PR under about 300 lines, title `[M3] ingest: dedup by source_record_id`. One review from whoever consumes it, then squash-merge.
- `git pull --rebase origin main` and run your tests before opening a PR.
- Merge at least every 2 hours. After H20 only fixes and docs.
- Never commit `.env`, keys, `.db` files, pcaps or raw logs.

## 9. Code rules

- Python 3.11, FastAPI, Pydantic v2, SQLite WAL with one writer. React + TypeScript (Vite, strict).
- snake_case JSON, RFC 3339 UTC timestamps, backend issues `event_id`, `finding_id`, `incident_id`, `link_id`, `action_id`.
- Errors: `{"error": {"code": "...", "message": "..."}}`.
- Parameterised SQL. Bound input sizes as in the schema.
- Every rule gets one positive and one negative test. Other code gets a test where it is cheap.
- Fixtures only in dev mode. Nothing fake on the demo path.
- Pin dependencies. No new heavy dependency without telling the team.

## 10. Prompting your assistant

1. One task per session. Use the template below.
2. Ask for a short plan and file list first, approve it, then let it code.
3. Run the thing after each step and paste real output back. Paste exact errors.
4. Never accept invented results: ask "what did you actually run?"
5. You must be able to explain your part to judges in two sentences.

```
ROLE = [M1 | M2 | M3 | M4]   NAME = [name]   BRANCH = [m3/topic]
TASK = [one sentence]
MAY TOUCH = [folders]
INPUTS = [fixtures, samples, routes]
HOURS LEFT = [n]
Read AGENTS.md and prompts/<ROLE>.md. Plan in under 10 lines, list files, wait for my OK.
```

## 11. Handoff (end of every task, paste in PR)

1. What works now.
2. Files changed, new config names (no secret values).
3. Example input and output.
4. Commands actually run and their results. Checks not run.
5. Known gaps and what the next person needs to do.
