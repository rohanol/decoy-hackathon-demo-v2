# M3 Backend and detection (Rohan)

You do NOT write frontend code: Pashmee owns the whole `frontend/` folder. Your job for her: by about H2 send her the `/openapi.json` link (or a TypeScript types file) and `contracts/examples/events_p3.json`, keep API shapes stable, and answer her questions fast. Review her PRs for API usage only.

You own `contracts/`, `backend/`, `config/scoring.yaml`, and you merge PRs. Read `AGENTS.md`, everything in `contracts/`, and `config/`.

Stack: Python 3.11, FastAPI, Pydantic v2, stdlib `sqlite3` in WAL mode, one writer (a single asyncio task or a lock around writes). No ORM needed.

Tasks in order:
1. H0 to H1: confirm the contracts with the team, then freeze them. Run on 127.0.0.1:8000.
2. Ingest `POST /api/ingest/events`: validate against the Pydantic model of `event.schema.json`, dedup on `(sensor_id, source_record_id)`, assign `event_id` and a global `seq`, assign `incident_id` (one per src_ip per lab_run_id), commit, then broadcast on `/ws/events`. `GET /api/events`, `/api/health`. **H4 target: a real Cowrie event goes through this and shows up in `/docs` or `GET /api/events`, then in Pashmee's feed.**
3. Rules in `backend/rules/`, one file per rule, each a pure function over the incident's events returning findings. Run after every insert. R01 boundary tests: 4 failures in 60 s no, 5 yes, 5 spread over 61 s no, duplicates change nothing. R07 test: load `contracts/examples/payloads.json`, every positive matches its classes, every negative matches nothing. Prajwal owns the regexes in `config/web_patterns.yaml`; you own the code that applies them (URL-decode twice, lowercase).
4. Scoring from `config/scoring.yaml`: each rule once per incident, R05/R09 only after confirmation, cap 100, `score_breakdown` explains every row. Test the demo path order gives 25 (R01), 40 (R02), 50 (R03), 65 (R07), 95 (confirm adds R05 + R09), 100 (R04, capped). R09 sits at 0 points with `pending_confirmation: true` until the confirm.
5. Links: candidate (same src_ip on both sensors within 300 s), strong_candidate (honeytoken planted on one sensor shows up on the other). `POST /api/links/{id}/decision`.
6. `GET /api/incidents`, `/api/incidents/{id}` with findings, breakdown, links, sessions, rule-based summary (call Prajwal's `analyst.summarise(incident)`), `/transcript`, `/api/stats/overview`, `/export`.
7. Mount Vedant's `response.router` at `/api/response` and call his `on_event()` hook for each ingested event.

Never: let `blocked_request` add points, store raw passwords, bind beyond 127.0.0.1, invent IDs in tests you did not run.
