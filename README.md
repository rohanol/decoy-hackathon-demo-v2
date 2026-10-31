# DeceptionGraph SOC v2

> **v2 in progress.** This repo starts from the v1 hackathon code (`rohanol/decoy-hackathon-demo`, commit `fb227bb`) and turns it into a deception kit an organization runs on its own network. Read `docs/prd/V2_BRIEF.md` first. The rest of this README still describes v1 until each part is ported.

D3COY 1.0, PS 04: deception-driven threat detection and response. Two laptops, fake SSH and web services, a SOC dashboard that turns attacker traffic into scored, evidence-linked incidents, and a manual block with undo.

Start here: `AGENTS.md` (rules), then your file in `prompts/`.

| Role | Person | Prompt |
|---|---|---|
| M1 design + whole frontend + deck | Pashmee | `prompts/M1_frontend.md` |
| M2 sensors, deployment, response | Vedant | `prompts/M2_sensors_response.md` |
| M3 backend, detection, merges (no frontend code) | Rohan | `prompts/M3_backend.md` |
| M4 web decoy, summary, demo | Prajwal | `prompts/M4_web_demo.md` |

## What is in this bootstrap

Contracts, config, deployment skeleton, attack script and demo plan. No application code: that gets written during the hackathon.

```
AGENTS.md / CLAUDE.md        rules for people and coding assistants
contracts/                   event + finding schemas, API, example events, labelled web payloads
config/                      scoring weights, honeytokens (hashes), web attack regexes
deployment/                  compose for Cowrie + web decoy, Cowrie config, lab network guide, preflight
decoys/web/assets/           synthetic customer_data.csv
prompts/                     one short prompt per role
scenarios/                   P3 attack script and the demo run sheet
```

## Before the event (everyone)

- [ ] Ethernet cable, USB-ethernet adapters, extension board, hotspot.
- [ ] M2: lab link works and Cowrie logs the real Kali IP (`deployment/LAB_NETWORK.md`). Biggest risk, do it first.
- [ ] M2: pull and pin the Cowrie image. Everyone: Python 3.11, Node 20+, Docker, `pip download` / `npm install` caches warm.
- [ ] Kali: hydra, sshpass, curl, gobuster.
- [ ] Private GitHub repo, all four added, branch protection on `main` if available.
- [ ] Check the D3COY rules on prior work. This repo has no app code, but disclose it to the organisers if they ask.
- [ ] Don't burn Claude usage the day before (weekly cap).

## H0 (first 30 minutes)

1. Read the PS together. If it differs from what this repo assumes, change `AGENTS.md` first.
2. Rohan pushes this repo as the first commit. Everyone clones.
3. Each person opens Claude Code in the repo and starts with the template in `AGENTS.md` section 10.
4. Rohan sends Pashmee the fixtures and the `/openapi.json` link by about H2. Pashmee designs first, then codes the full frontend.
5. Gates: H4 SSH event on dashboard, H8 web decoy + R07/R08, H12 full demo path, H20 freeze.

## Run (Laptop B, once code exists)

```bash
# first time only: the blocklist file must exist before compose starts (Docker would create a directory instead),
# and Cowrie runs as a non-root user that needs to write its log folder
echo '{"version":0,"entries":[]}' > deployment/state/blocklist.json
chmod 777 deployment/state/cowrie-log deployment/state/web-log
docker compose -f deployment/docker-compose.yml --env-file deployment/lab.env up -d
# backend on 127.0.0.1:8000, adapter, frontend on 127.0.0.1:5173
bash deployment/preflight.sh
```

Then follow `scenarios/demo_p3.md`.
