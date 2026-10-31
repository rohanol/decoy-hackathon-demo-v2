# Backend (M3, Rohan)

FastAPI + SQLite. Takes decoy events, groups them into incidents, runs the rules, scores, links the two decoys, and serves the dashboard. Routes and shapes: `contracts/API.md`. Interactive docs while running: http://127.0.0.1:8000/docs

## Run

From `dg-soc/` (Python 3.11+):

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows. Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m backend.main            # listens on 127.0.0.1:8000 only
```

Load the sample attack (dev only) in a second terminal:

```bash
python -m backend.tools.load_fixtures
```

Fresh start for a demo run: stop the backend and delete `backend/data/dg.db*`.

## Test

```bash
python -m pytest backend -q
```

## Settings (environment variables, all optional)

| Name | Default | What |
|---|---|---|
| `DG_DB_PATH` | `backend/data/dg.db` | SQLite file |
| `DG_CONFIG_DIR` | `config/` | where `scoring.yaml`, `web_patterns.yaml`, `honeytokens.yaml` live |
| `DG_CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | browser origins allowed to call the API and open `/ws/events` |

## How it fits together

| File | Job |
|---|---|
| `main.py` | routes, WebSocket, error format |
| `models.py` | checks each incoming event against `event.schema.json`; refuses raw passwords |
| `db.py` | storage; one writer, readers only see committed data |
| `rules/rNN.py` | one rule per file, pure functions: events in, findings out |
| `scoring.py` | points per rule from `config/scoring.yaml`, cap 100, breakdown rows |
| `links.py` | `candidate` (same IP on both decoys within 5 min) and `strong_candidate` (honeytoken reuse) |
| `integrations.py` | plugs in `response/router.py` (M2) and `analyst/summarise.py` (M4) if they exist |
| `tools/load_fixtures.py` | posts a fixture file |

## Hooks teammates provide

- M2, `response/router.py`: `router` (mounted at `/api/response`), `on_event(event)` (called once per new event, after commit), optional `active_block(src_ip)` for the incident page. Until it exists, `/api/response/*` returns 503.
- M4, `analyst/summarise.py`: `summarise(incident) -> {"source", "text", "cited_event_ids"}`. Until it exists (or if it fails), the backend writes a one-line-per-finding summary.
