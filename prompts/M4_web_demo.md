# M4 Web decoy, analyst summary and demo (Prajwal)

You own `decoys/web/`, `analyst/`, `scenarios/`, `tests/e2e/`, `config/web_patterns.yaml`, `config/honeytokens.yaml`, `contracts/examples/payloads.json`. Read `AGENTS.md` and `contracts/API.md` first.

Tasks in order:
1. Web decoy (Flask, `decoys/web/`, plus a `Dockerfile` running as uid 1000 on 8080). Looks like a slightly sloppy internal portal. Every response is canned. Nothing an attacker sends is executed, evaluated, used in a real query, or fetched.
   - `GET /` and `GET/POST /login`: hash the submitted password, compare with `config/honeytokens.yaml`. `svc_portal` with the right token → fake dashboard; anything else → "invalid credentials".
   - `GET /search?q=`: always a fake results page. If `q` looks like SQLi, return a fake SQL error page (that is the bait; the decision about whether it is an attack is still made by the backend).
   - `GET /download?file=`: only `customer_data.csv` is served (from `decoys/web/assets/`). Log `synthetic_file_access` with `asset_id`, `size_bytes`, `sha256`, `outcome: served`. Traversal attempts get a fake "file not found".
   - `GET /ping?host=`: fake ping output, never runs ping.
   - Hidden paths from `config/web_patterns.yaml`: `/.env` returns fake env with `BACKUP_SSH_USER=backup` and `BACKUP_SSH_PASS=DGLAB-Bkp-2210`, `/.git/HEAD` returns `ref: refs/heads/main`, `/admin` returns a fake 401, the rest 404.
   - First thing on every request: `decoys.policy.policy.check(request ip)`. If it returns an action_id, return 403 and log a `blocked_request` with `block_action_id`.
   - Log one JSON line per request to `LOG_PATH` in the ingest event shape (Vedant's adapter ships it). Put `query_redacted` with any password values replaced by `<redacted>`.
2. Keep `config/web_patterns.yaml` and `payloads.json` in sync. Add any payload you try during testing that should or should not match.
3. `analyst/summarise.py`: `summarise(incident) -> {"source": "rules", "text": ..., "cited_event_ids": [...]}`. Plain sentences built from findings, each citing evidence IDs. Uses the label wording from AGENTS.md section 7.
4. `scenarios/attack_p3.sh` (already drafted), plus `attack_p1.sh` (gobuster-style path probing + a few default logins) and `attack_p2.sh` (hydra wordlist). Every script exits unless the target is 192.168.77.20.
5. From H12: run the full demo end to end every 2 hours, log what broke, tell the owner. From H20: own the rehearsal and the 3-minute run.
